from __future__ import annotations

import asyncio

import pytest

import app.identity as identity_module
from app.identity import (
    Identity,
    InvalidApiKeyError,
    KeyStoreUnavailableError,
    bearer_token,
    hash_api_key,
    llm_checks_allowed,
    looks_like_api_key,
    resolve_identity,
)


def test_anonymous_callers_cannot_spend_the_host_inference_budget():
    assert llm_checks_allowed(Identity(kind="apikey")) is True
    assert llm_checks_allowed(Identity(kind="admin")) is True
    assert llm_checks_allowed(Identity(kind="anon")) is False


def test_hash_api_key_is_stable_sha256_hex():
    h = hash_api_key("cf_live_abc")
    assert h == hash_api_key("cf_live_abc")
    assert len(h) == 64
    assert h != hash_api_key("cf_live_abd")


def test_bearer_token_parsing():
    assert bearer_token("Bearer cf_live_x") == "cf_live_x"
    assert bearer_token("bearer cf_live_x") == "cf_live_x"
    assert bearer_token("Token cf_live_x") is None
    assert bearer_token("cf_live_x") is None
    assert bearer_token("Bearer ") is None
    assert bearer_token(None) is None


def test_looks_like_api_key():
    assert looks_like_api_key("cf_live_deadbeef")
    assert not looks_like_api_key("sk-123")
    assert not looks_like_api_key(None)


def test_resolve_identity_anonymous_is_demo_read_only(monkeypatch):
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)
    ident = asyncio.run(resolve_identity(None))
    assert ident.kind == "anon"
    assert ident.can_write is False
    assert ident.read_namespaces == {"demo"}


def test_resolve_identity_admin_token(monkeypatch):
    monkeypatch.setenv("CF_WRITE_TOKEN", "admin-secret")
    ident = asyncio.run(resolve_identity("Bearer admin-secret"))
    assert ident.kind == "admin"
    assert ident.can_write is True
    assert ident.allow_demo_write is False
    assert ident.namespace == "public"
    assert ident.read_namespaces == {"demo", "public"}


def test_resolve_identity_unknown_key_when_no_store(monkeypatch):
    # No DB_HOST -> no key store configured (dev profile) -> an api-key-shaped
    # token still resolves to anonymous: there is nothing to check it against.
    # (With a store configured, the same key is a 401 — see the tests below.)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)
    ident = asyncio.run(resolve_identity("Bearer cf_live_unknown"))
    assert ident.kind == "anon"
    assert ident.can_write is False


# --- #45: a presented key must never silently downgrade to anonymous --------
#
# The tests below fake the asyncpg pool so the store-backed paths of
# resolve_identity run without a database.


class _FakeConn:
    """Minimal stand-in for an asyncpg connection over cf_api_keys."""

    def __init__(self, row=None, error: Exception | None = None):
        self._row = row
        self._error = error
        self.queries: list[str] = []

    async def fetchrow(self, query, *args):
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return self._row

    async def execute(self, *args):
        return "UPDATE 1"


class _FakeAcquire:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


def _use_fake_store(monkeypatch, conn: _FakeConn):
    async def fake_get_pool():
        return _FakePool(conn)

    monkeypatch.setattr(identity_module, "_get_pool", fake_get_pool)
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)


def test_valid_key_resolves_to_its_namespace(monkeypatch):
    _use_fake_store(monkeypatch, _FakeConn(row={"namespace": "acct_42"}))
    ident = asyncio.run(resolve_identity("Bearer cf_live_valid"))
    assert ident.kind == "apikey"
    assert ident.namespace == "acct_42"
    assert ident.can_write is True
    assert ident.read_namespaces == {"acct_42"}


def test_unknown_key_raises_401(monkeypatch):
    # The store answers but has no row for this key hash.
    _use_fake_store(monkeypatch, _FakeConn(row=None))
    with pytest.raises(InvalidApiKeyError) as excinfo:
        asyncio.run(resolve_identity("Bearer cf_live_unknown"))
    assert excinfo.value.status_code == 401


def test_revoked_key_raises_401(monkeypatch):
    # Revoked keys are filtered by the lookup query itself, so a revoked key
    # looks exactly like an unknown one — and must get the same 401.
    conn = _FakeConn(row=None)
    _use_fake_store(monkeypatch, conn)
    with pytest.raises(InvalidApiKeyError) as excinfo:
        asyncio.run(resolve_identity("Bearer cf_live_revoked"))
    assert excinfo.value.status_code == 401
    assert "revoked_at is null" in conn.queries[0]


def test_store_error_raises_503(monkeypatch):
    # The store is configured but the lookup blows up (connection loss,
    # missing migration): surface a 503, never anonymous demo data.
    _use_fake_store(monkeypatch, _FakeConn(error=RuntimeError("connection lost")))
    with pytest.raises(KeyStoreUnavailableError) as excinfo:
        asyncio.run(resolve_identity("Bearer cf_live_anything"))
    assert excinfo.value.status_code == 503


def test_store_pool_failure_raises_503(monkeypatch):
    async def broken_get_pool():
        raise RuntimeError("cannot connect to the key store")

    monkeypatch.setattr(identity_module, "_get_pool", broken_get_pool)
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)
    with pytest.raises(KeyStoreUnavailableError) as excinfo:
        asyncio.run(resolve_identity("Bearer cf_live_anything"))
    assert excinfo.value.status_code == 503
