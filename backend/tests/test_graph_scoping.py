"""Tenant isolation of the graph view and of cognified (Cognee-derived) nodes."""
from __future__ import annotations

import asyncio
import sys
import types

import app.cognee_runtime.graph as graph
import app.cognee_runtime.ingest as ingest

NODES = [
    ("demo-sess", {"type": "AgentSession", "session_id": "demo-1", "task": "demo task", "namespace": "demo"}),
    ("demo-evt", {"type": "SessionEvent", "session_id": "demo-1", "content": "demo event"}),
    ("demo-chunk", {"type": "DocumentChunk", "text": "demo transcript", "belongs_to_set": ["cf_ns_demo"]}),
    ("acme-sess", {"type": "AgentSession", "session_id": "acme-1", "task": "acme task", "namespace": "acme"}),
    ("acme-evt", {"type": "SessionEvent", "session_id": "acme-1", "content": "acme private event"}),
    ("acme-chunk", {"type": "DocumentChunk", "text": "acme private transcript", "belongs_to_set": ["cf_ns_acme"]}),
    ("acme-entity", {"type": "Entity", "name": "acme-internal-service", "belongs_to_set": ["cf_ns_acme"]}),
    ("acme-rule", {"type": "Rule", "text": "acme rule", "belongs_to_set": ["coding_agent_rules_acme"]}),
    ("shared-entity", {"type": "Entity", "name": "postgres", "belongs_to_set": ["cf_ns_demo", "cf_ns_acme"]}),
    ("legacy-chunk", {"type": "DocumentChunk", "text": "untagged transcript from any tenant"}),
    ("legacy-entity", {"type": "Entity", "name": "untagged-entity"}),
    ("orphan-evt", {"type": "SessionEvent", "session_id": "missing", "content": "orphan event"}),
]
EDGES = [
    ("demo-evt", "demo-sess", "session"),
    ("acme-chunk", "acme-entity", "contains"),
    ("demo-chunk", "acme-entity", "contains"),
    ("demo-chunk", "shared-entity", "contains"),
    ("acme-chunk", "shared-entity", "contains"),
    ("legacy-chunk", "demo-chunk", "contains"),
]


def _view(monkeypatch, namespaces):
    async def fake_get_graph():
        return None, list(NODES), list(EDGES)

    monkeypatch.setattr(graph, "_get_graph", fake_get_graph)
    data = asyncio.run(graph.graph_view(namespaces=namespaces))
    return {n["id"] for n in data["nodes"]}, {(e["source"], e["target"]) for e in data["edges"]}


def test_anonymous_graph_view_shows_only_demo(monkeypatch):
    ids, edges = _view(monkeypatch, None)
    assert ids == {"demo-sess", "demo-evt", "demo-chunk"}
    assert edges == {("demo-evt", "demo-sess")}


def test_demo_reader_never_sees_other_tenants_or_untagged_nodes(monkeypatch):
    ids, _ = _view(monkeypatch, {"demo", "public"})
    assert ids == {"demo-sess", "demo-evt", "demo-chunk"}


def test_tenant_sees_only_its_own_nodes(monkeypatch):
    ids, edges = _view(monkeypatch, {"acme"})
    assert ids == {"acme-sess", "acme-evt", "acme-chunk", "acme-entity", "acme-rule"}
    assert edges == {("acme-chunk", "acme-entity")}


def test_entity_shared_by_two_namespaces_needs_access_to_both(monkeypatch):
    ids, edges = _view(monkeypatch, {"demo", "acme"})
    assert "shared-entity" in ids
    assert {("demo-chunk", "shared-entity"), ("acme-chunk", "shared-entity")} <= edges
    for readers in (None, {"demo"}, {"demo", "public"}, {"acme"}):
        ids, edges = _view(monkeypatch, readers)
        assert "shared-entity" not in ids
        assert not any("shared-entity" in e for e in edges)


# The same entity name extracted in two namespaces maps to one node id. How the
# second write lands depends on the graph adapter in cognee 1.2.2:
#   Neo4j    unions belongs_to_set (``apoc.coll.toSet``) and merges other props;
#   Ladybug  (local default) replaces the whole property blob on MATCH.
def _second_write(adapter: str, first: dict, second: dict) -> dict:
    if adapter == "neo4j":
        merged = {**first, **second}
        merged["belongs_to_set"] = sorted(set(first["belongs_to_set"]) | set(second["belongs_to_set"]))
        return merged
    return dict(second)


def test_same_entity_written_by_two_namespaces_never_leaks_across_them():
    from app.cognee_runtime.recall import in_namespace

    acme = {"type": "Entity", "name": "billing-db", "description": "acme notes", "belongs_to_set": ["cf_ns_acme"]}
    globex = {"type": "Entity", "name": "billing-db", "description": "globex notes", "belongs_to_set": ["cf_ns_globex"]}

    union = _second_write("neo4j", acme, globex)
    assert not in_namespace(union, {"acme"})
    assert not in_namespace(union, {"globex"})
    assert not in_namespace(union, {"demo", "public"})

    # Last writer wins: tag and content are both globex's, so only globex sees it.
    replaced = _second_write("ladybug", acme, globex)
    assert replaced["description"] == "globex notes"
    assert in_namespace(replaced, {"globex"})
    assert not in_namespace(replaced, {"acme"})
    assert not in_namespace(replaced, None)


def test_conflicting_namespace_tags_are_rejected_not_first_wins():
    from app.cognee_runtime.recall import effective_namespace, in_namespace

    for tags in (["cf_ns_acme", "cf_ns_globex"], ["cf_ns_globex", "cf_ns_acme"],
                 ["coding_agent_rules_acme", "cf_ns_globex"], ["cf_ns_acme", "coding_agent_rules"]):
        props = {"type": "Entity", "belongs_to_set": tags}
        assert effective_namespace(props) is None
        assert not in_namespace(props, {"acme"})
        assert not in_namespace(props, {"globex"})
        assert not in_namespace(props, None)


def test_ingest_tags_cognified_nodes_with_namespace(monkeypatch):
    calls = {}

    async def fake_add(data, dataset_name=None, node_set=None, **kwargs):
        calls["add"] = {"dataset_name": dataset_name, "node_set": node_set}

    async def fake_cognify(datasets=None, **kwargs):
        calls["cognify"] = datasets

    async def fake_add_data_points(nodes, *args, **kwargs):
        calls["data_points"] = len(nodes)

    fake_cognee = types.SimpleNamespace(add=fake_add, cognify=fake_cognify)
    fake_storage = types.ModuleType("cognee.tasks.storage")
    fake_storage.add_data_points = fake_add_data_points
    monkeypatch.setitem(sys.modules, "cognee", fake_cognee)
    monkeypatch.setitem(sys.modules, "cognee.tasks.storage", fake_storage)
    monkeypatch.setattr(ingest, "configure_cognee", lambda: None)

    session = {
        "session_id": "acme-1",
        "task": "t",
        "repo": {"name": "r"},
        "events": [{"kind": "note", "content": "hello"}],
        "memories": [{"text": "a fact", "subject": "s"}],
    }
    res = asyncio.run(ingest.ingest_session(session, cognify=True, namespace="acme"))
    assert res["cognified"] is True
    assert calls["add"]["node_set"] == ["cf_ns_acme"]

    other = dict(session, session_id="globex-1", memories=[{"text": "a fact", "subject": "s"}])
    asyncio.run(ingest.ingest_session(other, cognify=True, namespace="globex"))
    assert calls["add"]["node_set"] == ["cf_ns_globex"]


def test_count_nodes_filters_tenant_counts_and_cross_namespace_edges(monkeypatch):
    nodes = NODES + [
        ("demo-memory", {"type": "Memory", "namespace": "demo", "source_session_id": "demo-1"}),
        ("other-demo-memory", {"type": "Memory", "namespace": "demo", "source_session_id": "other-demo"}),
        ("tenant-memory", {"type": "Memory", "namespace": "acme", "source_session_id": "acme-1"}),
    ]
    edges = EDGES + [
        ("demo-memory", "demo-sess", "belongs"),
        ("tenant-memory", "acme-sess", "belongs"),
        ("demo-memory", "tenant-memory", "cross-tenant"),
    ]

    async def fake_get_graph():
        return None, nodes, edges

    monkeypatch.setattr(graph, "_get_graph", fake_get_graph)
    public = asyncio.run(graph.count_nodes(namespaces={"demo"}))
    assert public["Memory"] == 2
    assert public["AgentSession"] == 1
    assert public["SessionEvent"] == 1
    assert public["_edges"] == 2
    assert public.get("Rule", 0) == 0

    sample = asyncio.run(graph.count_nodes(namespaces={"demo"}, source_session_id="demo-1"))
    assert sample["Memory"] == 1
    assert sample["_edges"] == 0

    tenant = asyncio.run(graph.count_nodes(namespaces={"acme"}))
    assert tenant["Memory"] == 1
    assert tenant["Rule"] == 1
    assert tenant["_edges"] == 2

    global_counts = asyncio.run(graph.count_nodes())
    assert global_counts["Memory"] == 3
    assert global_counts["_edges"] == len(edges)
