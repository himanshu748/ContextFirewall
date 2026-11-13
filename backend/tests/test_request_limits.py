"""Reject oversized requests before invoking graph, vector, or LLM work."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main, mcp_server
from app.models import (
    AuditRequest,
    PackRequest,
    RecordedSession,
    RememberRequest,
)


@pytest.mark.parametrize("request_model", [AuditRequest, PackRequest])
@pytest.mark.parametrize("payload", [
    {"query": ""},
    {"query": "q" * 4097},
    {"query": "valid", "top_k": 0},
    {"query": "valid", "top_k": 51},
])
def test_recall_request_rejects_out_of_bounds_values(request_model, payload):
    with pytest.raises(ValidationError):
        request_model(**payload)


@pytest.mark.parametrize("payload", [
    {"text": ""},
    {"text": "a" * 16385},
    {"text": "valid", "kind": "unknown"},
    {"text": "valid", "subject": "s" * 513},
])
def test_remember_request_rejects_out_of_bounds_values(payload):
    with pytest.raises(ValidationError):
        RememberRequest(**payload)


@pytest.mark.parametrize("field,max_items", [("events", 1000), ("memories", 500)])
def test_session_lists_have_explicit_caps(field, max_items):
    data = {"session_id": "test", "task": "test"}
    data[field] = ([{"kind": "decision", "content": "test"}] if field == "events" else [{}]) * (max_items + 1)
    with pytest.raises(ValidationError):
        RecordedSession(**data)


@pytest.mark.parametrize("path", ["/pack", "/audit"])
def test_rest_recall_rejects_invalid_top_k_before_core(path):
    client = TestClient(main.app)
    result = client.post(path, json={"query": "query", "top_k": 51})
    assert result.status_code == 422
    assert "top_k" in str(result.json())


@pytest.mark.parametrize("path", ["/graph", "/activity"])
@pytest.mark.parametrize("limit", [0, -1, 2001])
def test_rest_list_limits_are_bounded(path, limit):
    client = TestClient(main.app)
    result = client.get(path, params={"limit": limit})
    assert result.status_code == 422
    assert "limit" in str(result.json())


def test_mcp_pack_rejects_large_top_k_without_core_call(monkeypatch):
    core = AsyncMock()
    monkeypatch.setattr(mcp_server, "_build_pack", core)
    with pytest.raises(ValidationError):
        asyncio.run(mcp_server.get_trusted_context("query", top_k=51))
    core.assert_not_awaited()


def test_mcp_remember_rejects_invalid_kind_without_core_call(monkeypatch):
    core = AsyncMock()
    monkeypatch.setattr(mcp_server, "_remember_fact", core)
    with pytest.raises(ValidationError):
        asyncio.run(mcp_server.remember("text", kind="unknown"))
    core.assert_not_awaited()
