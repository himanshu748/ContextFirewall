from __future__ import annotations

import asyncio
import logging

from app.cognee_runtime import graph


def _patch_graph(monkeypatch, nodes, edges=None):
    async def fake_get_graph():
        return object(), nodes, edges or []

    monkeypatch.setattr(graph, "_get_graph", fake_get_graph)


def test_graph_view_filters_namespace_before_limit(monkeypatch):
    other_nodes = [
        (f"other-{index}", {"type": "Memory", "namespace": "other"})
        for index in range(1000)
    ]
    tenant_nodes = [
        (f"tenant-{index}", {"type": "Memory", "namespace": "tenant"})
        for index in range(10)
    ]
    _patch_graph(monkeypatch, other_nodes + tenant_nodes)

    result = asyncio.run(graph.graph_view(limit=400, namespaces={"tenant"}))

    assert {node["id"] for node in result["nodes"]} == {
        f"tenant-{index}" for index in range(10)
    }
    assert result["truncated"] is False


def test_graph_view_truncates_to_typed_recent_nodes(monkeypatch):
    nodes = [
        ("untyped-new", {"namespace": "tenant", "created_at": "2026-10-24T00:00:00Z"}),
        (
            "typed-old",
            {
                "type": "Memory",
                "namespace": "tenant",
                "created_at": "2020-01-01T00:00:00Z",
            },
        ),
        (
            "typed-new",
            {
                "type": "Rule",
                "namespace": "tenant",
                "created_at": "2026-10-23T00:00:00Z",
            },
        ),
        (
            "typed-oldest",
            {
                "type": "Repo",
                "namespace": "tenant",
                "created_at": "2019-01-01T00:00:00Z",
            },
        ),
    ]
    _patch_graph(
        monkeypatch,
        nodes,
        [
            ("typed-old", "typed-new", "selected"),
            ("typed-new", "untyped-new", "truncated"),
        ],
    )

    result = asyncio.run(graph.graph_view(limit=2, namespaces={"tenant"}))

    assert {node["id"] for node in result["nodes"]} == {"typed-old", "typed-new"}
    assert result["truncated"] is True
    assert result["edges"] == [
        {"source": "typed-old", "target": "typed-new", "label": "selected"}
    ]


def test_graph_view_hides_exception_details_and_logs_exception(monkeypatch, caplog):
    async def failing_get_graph():
        raise RuntimeError("neo4j.internal: credential=private")

    monkeypatch.setattr(graph, "_get_graph", failing_get_graph)

    with caplog.at_level(logging.ERROR, logger=graph.__name__):
        result = asyncio.run(graph.graph_view())

    assert result["error"] == "Graph data is temporarily unavailable."
    assert result["truncated"] is False
    assert "credential=private" not in str(result)
    assert "neo4j.internal" in caplog.text
