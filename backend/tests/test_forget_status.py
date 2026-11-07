"""Regression tests for /forget HTTP status codes.

A failed forget used to return HTTP 200 with a ForgetResponse whose "status"
field said not_found / forbidden / error. Clients checking res.ok treated a
failed deletion as a success. The body is kept so the console still shows its
message.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(monkeypatch):
    async def allow(_authorization):
        return SimpleNamespace(can_write=True, namespace="tenant_a", allow_demo_write=False)

    monkeypatch.setattr(main, "resolve_identity", allow)
    monkeypatch.setattr(main, "log_activity", lambda *_args, **_kwargs: None)
    # Not used as a context manager: the Cognee/MCP lifespan must not start.
    return TestClient(main.app)


@pytest.mark.parametrize(
    "status, expected",
    [("forgotten", 200), ("not_found", 404), ("forbidden", 403), ("error", 500),
     ("unexpected", 500)],
)
def test_failed_forget_returns_a_failing_status(client, monkeypatch, status, expected):
    async def fake_forget(memory_id, **_kwargs):
        return {
            "memory_id": memory_id,
            "status": status,
            "message": "forget %s" % status,
        }

    monkeypatch.setattr(main, "forget_memory", fake_forget)
    res = client.post("/forget", json={"memory_id": "s1:m0", "reason": "test"})
    assert res.status_code == expected
    assert res.json() == {
        "memory_id": "s1:m0",
        "status": status,
        "message": "forget %s" % status,
    }


def test_forget_without_write_permission_is_still_401(client, monkeypatch):
    async def deny(_authorization):
        return SimpleNamespace(can_write=False, namespace="tenant_a", allow_demo_write=False)

    monkeypatch.setattr(main, "resolve_identity", deny)
    res = client.post("/forget", json={"memory_id": "s1:m0"})
    assert res.status_code == 401
