from __future__ import annotations

import asyncio

from app.identity import (
    bearer_token,
    hash_api_key,
    looks_like_api_key,
    resolve_identity,
)


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
    # No DB_HOST -> no key store -> an api-key-shaped token resolves to anonymous.
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("CF_WRITE_TOKEN", raising=False)
    ident = asyncio.run(resolve_identity("Bearer cf_live_unknown"))
    assert ident.kind == "anon"
    assert ident.can_write is False
