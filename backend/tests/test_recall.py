from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import cognee.infrastructure.databases.graph as graph_module
import cognee.infrastructure.databases.vector as vector_module
import pytest

import app.cognee_runtime.recall as recall_module


def _memory(node_id: str, subject: str) -> dict:
    return {
        "node_id": node_id,
        "memory_id": f"{node_id}:m0",
        "text": "unrelated text",
        "subject": subject,
        "namespace": "demo",
    }


class _EmptyVectorEngine:
    def search(self, **_kwargs):
        return []


class _FailingVectorEngine:
    def search(self, **_kwargs):
        raise RuntimeError("index unavailable")


class _RankedVectorEngine:
    def search(self, **_kwargs):
        return [SimpleNamespace(id="n1")]


class _ForeignIdsVectorEngine:
    def search(self, **_kwargs):
        return [SimpleNamespace(id="node-from-another-namespace")]


def _install(monkeypatch, engine):
    async def fake_load_graph_memories(namespaces=None):
        return {
            "n1": _memory("n1", "deployment"),
            "n2": _memory("n2", "billing"),
            "n3": _memory("n3", "deployment"),
        }

    monkeypatch.setattr(recall_module, "configure_cognee", lambda: {})
    monkeypatch.setattr(recall_module, "_load_graph_memories", fake_load_graph_memories)
    monkeypatch.setattr(vector_module, "get_vector_engine", lambda: engine)


def test_no_vector_hits_returns_no_unrelated_memories(monkeypatch):
    _install(monkeypatch, _EmptyVectorEngine())
    result = asyncio.run(recall_module.recall_memory_candidates("deploy to production"))
    assert result == []


def test_vector_error_is_logged_and_does_not_expand_results(monkeypatch, caplog):
    _install(monkeypatch, _FailingVectorEngine())
    with caplog.at_level(logging.WARNING, logger=recall_module.__name__):
        result = asyncio.run(recall_module.recall_memory_candidates("deploy to production"))
    assert result == []
    assert "vector search failed" in caplog.text


def test_ranked_hits_still_include_same_subject_peers(monkeypatch):
    _install(monkeypatch, _RankedVectorEngine())
    result = asyncio.run(recall_module.recall_memory_candidates("deploy to production"))
    assert [record["node_id"] for record in result] == ["n1", "n3"]


def test_unknown_vector_ids_do_not_dump_the_graph(monkeypatch):
    _install(monkeypatch, _ForeignIdsVectorEngine())
    result = asyncio.run(recall_module.recall_memory_candidates("deploy to production"))
    assert result == []


class _PagedVectorEngine:
    def __init__(self, ids):
        self.ids = ids
        self.limits = []

    def search(self, *, limit, **_kwargs):
        self.limits.append(limit)
        return [SimpleNamespace(id=nid) for nid in self.ids[:limit]]


def test_overfetch_finds_authorized_record_below_foreign_hits(monkeypatch):
    engine = _PagedVectorEngine([f"foreign-{i}" for i in range(12)] + ["n1"])
    _install(monkeypatch, engine)

    result = asyncio.run(
        recall_module.recall_memory_candidates("deploy", top_k=1, namespaces={"demo"})
    )
    assert [record["node_id"] for record in result] == ["n1", "n3"]
    assert engine.limits == [1, 2, 4, 8, 16]


def test_overfetch_caps_search_without_leaking_foreign_ids(monkeypatch, caplog):
    engine = _PagedVectorEngine([f"foreign-{i}" for i in range(200)] + ["n1"])
    _install(monkeypatch, engine)

    with caplog.at_level(logging.WARNING, logger=recall_module.__name__):
        result = asyncio.run(recall_module.recall_memory_candidates("deploy", top_k=1))
    assert result == []
    assert engine.limits == [1, 2, 4, 8, 16]
    assert "rank cap 16" in caplog.text
    assert "foreign-" not in caplog.text


def test_overfetch_stops_when_index_is_exhausted(monkeypatch):
    engine = _PagedVectorEngine(["foreign-a", "foreign-b"])
    _install(monkeypatch, engine)

    result = asyncio.run(recall_module.recall_memory_candidates("deploy", top_k=1))
    assert result == []
    assert engine.limits == [1, 2, 4]


def test_zero_top_k_never_queries_global_index(monkeypatch):
    engine = _PagedVectorEngine(["n1"])
    _install(monkeypatch, engine)

    result = asyncio.run(recall_module.recall_memory_candidates("deploy", top_k=0))
    assert result == []
    assert engine.limits == []


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("trust_score", "not-a-number"),
        ("trust_score", ""),
        ("trust_score", "NaN"),
        ("trust_score", float("inf")),
        ("trust_score", -0.1),
        ("trust_score", 1.1),
        ("trust_score", True),
        ("trust_score", None),
        ("reinforcement_count", "oops"),
        ("reinforcement_count", ""),
        ("reinforcement_count", "NaN"),
        ("reinforcement_count", float("inf")),
        ("reinforcement_count", -1),
        ("reinforcement_count", 1.5),
        ("reinforcement_count", True),
        ("reinforcement_count", None),
    ],
)
def test_load_graph_memories_skips_invalid_legacy_metadata(monkeypatch, caplog, field, invalid):
    class FakeGraphEngine:
        async def get_graph_data(self):
            bad = {
                "type": "Memory", "namespace": "demo", "text": "private-bad-memory",
                "trust_score": 0.75, "reinforcement_count": 2,
            }
            bad[field] = invalid
            valid = {
                "type": "Memory", "namespace": "demo", "text": "permitted",
                "trust_score": 0.75, "reinforcement_count": 0,
            }
            foreign = {"type": "Memory", "namespace": "other", "text": "foreign"}
            return [("bad-id", bad), ("good-id", valid), ("foreign-id", foreign)], []

    async def get_graph_engine():
        return FakeGraphEngine()

    monkeypatch.setattr(graph_module, "get_graph_engine", get_graph_engine)
    with caplog.at_level(logging.WARNING, logger=recall_module.__name__):
        records = asyncio.run(recall_module._load_graph_memories({"demo"}))

    assert list(records) == ["good-id"]
    assert records["good-id"]["trust_score"] == 0.75
    assert records["good-id"]["reinforcement_count"] == 0
    assert "bad-id" in caplog.text
    assert "private-bad-memory" not in caplog.text
    assert "foreign" not in caplog.text
