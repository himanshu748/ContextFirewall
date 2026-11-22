"""REST read endpoints must not substitute demo data for invalid stored keys."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import identity, main


def test_invalid_key_blocks_pack_before_demo_recall(monkeypatch):
    class MissingRowPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def fetchrow(self, *_args):
            return None

    async def pool():
        return MissingRowPool()

    async def do_not_recall(*_args, **_kwargs):
        raise AssertionError("Must not retrieve demo memory with invalid credentials")

    monkeypatch.setattr(identity, "_get_pool", pool)
    monkeypatch.setattr(main, "build_pack", do_not_recall)
    response = TestClient(main.app).post(
        "/pack",
        json={"query": "deployment instructions"},
        headers={"Authorization": "Bearer cf_live_revoked"},
    )
    assert response.status_code == 401
    assert response.json()["detail"].startswith("Invalid or revoked")


def test_key_store_outage_blocks_pack_before_demo_recall(monkeypatch):
    async def fail_pool():
        raise OSError("private-connection-secret")

    async def do_not_recall(*_args, **_kwargs):
        raise AssertionError("Must not retrieve demo memory during verification outage")

    monkeypatch.setattr(identity, "_get_pool", fail_pool)
    monkeypatch.setattr(main, "build_pack", do_not_recall)
    response = TestClient(main.app).post(
        "/pack",
        json={"query": "deployment instructions"},
        headers={"Authorization": "Bearer cf_live_existing"},
    )
    assert response.status_code == 503
    assert "private-connection-secret" not in response.text
