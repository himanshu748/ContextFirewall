"""Ensure anonymous health and sample seeding never read tenant-wide counts."""
from __future__ import annotations

import asyncio
import json

from app import main as api


def test_health_reads_only_demo_counts(monkeypatch):
    requests = []

    async def fake_counts(**kwargs):
        requests.append(kwargs)
        return {"Memory": 2, "_edges": 1}

    monkeypatch.setattr(api, "configure_cognee", lambda: "test")
    monkeypatch.setattr(api, "count_nodes", fake_counts)

    response = asyncio.run(api.health())
    assert requests == [{"namespaces": {"demo"}}]
    assert response.counts == {"Memory": 2, "_edges": 1}


def test_demo_seeding_checks_memory_from_bundled_session_only(tmp_path, monkeypatch):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"session_id": "demo-original"}), encoding="utf-8")
    monkeypatch.setattr(api, "DEMO_SESSION", sample)
    requests = []

    async def empty_demo(**kwargs):
        requests.append(kwargs)
        return {"Memory": 0}

    monkeypatch.setattr(api, "count_nodes", empty_demo)
    assert asyncio.run(api._demo_already_seeded()) is False
    assert requests == [{"namespaces": {"demo"}, "source_session_id": "demo-original"}]

    async def seeded_demo(**kwargs):
        return {"Memory": 8}

    monkeypatch.setattr(api, "count_nodes", seeded_demo)
    assert asyncio.run(api._demo_already_seeded()) is True
