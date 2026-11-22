"""Return honest, non-disclosing HTTP errors for backend write and reset failures."""
from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main


def test_healthz_is_cheap_and_does_not_touch_storage(monkeypatch):
    def fail_configuration():
        raise AssertionError("liveness must not configure storage")

    async def fail_scan(**_kwargs):
        raise AssertionError("liveness must not scan the graph")

    monkeypatch.setattr(main, "configure_cognee", fail_configuration)
    monkeypatch.setattr(main, "count_nodes", fail_scan)
    response = TestClient(main.app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_uses_storage_backed_demo_health(monkeypatch):
    observed = []

    async def counts(*, namespaces):
        observed.append(namespaces)
        return {"Memory": 3}

    monkeypatch.setattr(main, "configure_cognee", lambda: {"graph": "test"})
    monkeypatch.setattr(main, "count_nodes", counts)
    response = TestClient(main.app).get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "profile": {"graph": "test"}, "counts": {"Memory": 3}}
    assert observed == [{"demo"}]


@pytest.fixture
def client(monkeypatch):
    async def allow(_authorization):
        return SimpleNamespace(can_write=True, namespace="tenant", allow_demo_write=False)

    monkeypatch.setattr(main, "resolve_identity", allow)
    monkeypatch.setattr(main, "log_activity", lambda *_args, **_kwargs: None)
    return TestClient(main.app)


@pytest.mark.parametrize(
    ("endpoint", "body", "function"),
    [
        ("/remember", {"text": "safe placeholder"}, "remember_fact"),
        ("/ingest", {"session": {"session_id": "s1", "task": "test"}, "cognify": False},
         "ingest_session"),
    ],
)
def test_backend_write_exception_is_500_without_private_details(
    client, monkeypatch, caplog, endpoint, body, function
):
    async def fail(*_args, **_kwargs):
        raise RuntimeError("private-connection-string")

    monkeypatch.setattr(main, function, fail)
    with caplog.at_level(logging.ERROR, logger=main.__name__):
        response = client.post(endpoint, json=body)

    assert response.status_code == 500
    assert "private-connection-string" not in response.text
    assert "private-connection-string" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_admin_reset_prune_failure_is_not_reported_as_success(
    client, monkeypatch, caplog
):
    async def fail_prune():
        raise RuntimeError("private-db-credential")

    async def prune_system(**_kwargs):
        raise AssertionError("Should not prune system after data prune fails")

    monkeypatch.setenv("CF_ADMIN_TOKEN", "synthetic-admin-token")
    monkeypatch.setattr(main, "configure_cognee", lambda: None)
    monkeypatch.setitem(
        sys.modules, "cognee",
        SimpleNamespace(prune=SimpleNamespace(
            prune_data=fail_prune, prune_system=prune_system
        )),
    )
    with caplog.at_level(logging.ERROR, logger=main.__name__):
        response = client.post(
            "/reset", headers={"X-Admin-Token": "synthetic-admin-token"}
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to reset memory."
    assert "private-db-credential" not in response.text
    assert "private-db-credential" not in caplog.text
    assert "RuntimeError" in caplog.text
