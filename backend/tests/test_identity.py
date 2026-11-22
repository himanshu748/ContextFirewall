from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
import app.identity as identity

from app.identity import (
    Identity,
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
    # A missing key store is an outage, not permission to substitute demo data.
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setattr(identity, "_pool", None)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_identity("Bearer cf_live_unknown"))
    assert exc.value.status_code == 503
    assert "temporarily unavailable" in exc.value.detail


class _FakeKeyPool:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.key_hash = None

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def fetchrow(self, query, key_hash):
        self.query = query
        self.key_hash = key_hash
        return self.row

    async def execute(self, *_args):
        return "UPDATE 1"


def test_resolve_identity_valid_key_scopes_reads_to_private_namespace(monkeypatch):
    pool = _FakeKeyPool({"namespace": "tenant-a"})

    async def get_pool():
        return pool

    monkeypatch.setattr(identity, "_get_pool", get_pool)
    ident = asyncio.run(resolve_identity("Bearer cf_live_example"))
    assert ident.kind == "apikey"
    assert ident.read_namespaces == {"tenant-a"}
    assert ident.can_write
    assert pool.key_hash == hash_api_key("cf_live_example")
    assert "revoked_at is null" in pool.query.lower()


@pytest.mark.parametrize("raw_key", ["cf_live_unknown", "cf_live_revoked"])
def test_unknown_or_revoked_key_returns_401(monkeypatch, raw_key):
    # Both an absent key row and a revoked key return no row under the
    # database query's revoked_at-is-null predicate.
    async def get_pool():
        return _FakeKeyPool(None)

    monkeypatch.setattr(identity, "_get_pool", get_pool)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_identity("Bearer " + raw_key))
    assert exc.value.status_code == 401
    assert "invalid or revoked" in exc.value.detail.lower()


def test_key_store_error_returns_503_without_leaking_exception(monkeypatch, caplog):
    async def fail_pool():
        raise RuntimeError("database-password-not-for-logs")

    monkeypatch.setattr(identity, "_get_pool", fail_pool)
    with caplog.at_level("ERROR", logger=identity.__name__):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(resolve_identity("Bearer cf_live_example"))
    assert exc.value.status_code == 503
    assert "database-password-not-for-logs" not in str(exc.value.detail)
    assert "database-password-not-for-logs" not in caplog.text


def test_invalid_non_api_bearer_token_is_not_anonymous(monkeypatch):
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_identity("Bearer wrong-token"))
    assert exc.value.status_code == 401
