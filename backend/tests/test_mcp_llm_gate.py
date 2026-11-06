"""Hosted MCP tools must apply the same LLM gate as the REST API."""
from __future__ import annotations

import asyncio

import pytest

import app.mcp_server as mcp_server
from app.identity import Identity


def _ident(kind: str) -> Identity:
    return Identity(kind=kind, namespace="acme", can_write=kind != "anon", read_namespaces={"acme"})


@pytest.mark.parametrize("kind,expected", [("anon", False), ("apikey", True), ("admin", True)])
def test_mcp_read_tools_gate_llm_checks_on_identity(monkeypatch, kind, expected):
    seen = {}

    async def fake_identity():
        return _ident(kind)

    async def fake_build_pack(task, **kwargs):
        seen["pack"] = kwargs.get("use_llm")
        return {"audit": {"passed_count": 0, "blocked_count": 0}, "pack_markdown": ""}

    async def fake_audit(task, **kwargs):
        seen["audit"] = kwargs.get("use_llm")
        return {"candidates": [], "passed_count": 0, "blocked_count": 0}

    monkeypatch.setattr(mcp_server, "_ctx_identity", fake_identity)
    monkeypatch.setattr(mcp_server, "_build_pack", fake_build_pack)
    monkeypatch.setattr(mcp_server, "_audit_memories", fake_audit)
    monkeypatch.setattr(mcp_server, "log_activity", lambda *a, **k: None)

    asyncio.run(mcp_server.get_trusted_context("deploy"))
    asyncio.run(mcp_server.audit_context("deploy"))
    assert seen == {"pack": expected, "audit": expected}
