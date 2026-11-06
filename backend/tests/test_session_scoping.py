"""Session ids are caller-chosen, so they can collide across namespaces."""
from __future__ import annotations

import asyncio

import app.cognee_runtime.graph as graph

DEMO_SID = "taskflow-onboarding"

NODES = [
    # Public demo session; its events predate per-event namespace tags.
    ("demo-sess", {"type": "AgentSession", "session_id": DEMO_SID, "task": "demo", "namespace": "demo"}),
    ("demo-e1", {"type": "SessionEvent", "session_id": DEMO_SID, "event_id": f"{DEMO_SID}:e0", "content": "demo step", "ordinal": 0}),
    # Another tenant reuses the public demo's session id.
    ("evil-sess", {"type": "AgentSession", "session_id": DEMO_SID, "task": "spoof", "namespace": "evil"}),
    ("evil-e1", {"type": "SessionEvent", "session_id": DEMO_SID, "event_id": f"{DEMO_SID}:e0", "content": "injected", "namespace": "evil", "ordinal": 0}),
    # Two tenants share a session id; acme's legacy event has no tag or edge.
    ("acme-sess", {"type": "AgentSession", "session_id": "s1", "task": "acme", "namespace": "acme"}),
    ("acme-e1", {"type": "SessionEvent", "session_id": "s1", "event_id": "s1:e0", "content": "acme secret plan", "ordinal": 0}),
    ("globex-sess", {"type": "AgentSession", "session_id": "s1", "task": "globex", "namespace": "globex"}),
    ("globex-e1", {"type": "SessionEvent", "session_id": "s1", "event_id": "s1:e0", "content": "globex event", "namespace": "globex", "ordinal": 0}),
    # Unique session id: a legacy event with no tag and no edge stays visible to its owner.
    ("solo-sess", {"type": "AgentSession", "session_id": "solo", "task": "solo", "namespace": "acme"}),
    ("solo-e1", {"type": "SessionEvent", "session_id": "solo", "event_id": "solo:e0", "content": "solo event", "ordinal": 0}),
]
EDGES = [("demo-e1", "demo-sess", "session")]


def _patch(monkeypatch):
    async def fake_get_graph():
        return None, list(NODES), list(EDGES)

    monkeypatch.setattr(graph, "_get_graph", fake_get_graph)


def _timeline(monkeypatch, sid, namespaces):
    _patch(monkeypatch)
    return [e["content"] for e in asyncio.run(graph.session_timeline(sid, namespaces=namespaces))]


def test_colliding_tenant_cannot_inject_into_public_demo_timeline(monkeypatch):
    assert _timeline(monkeypatch, DEMO_SID, None) == ["demo step"]
    assert _timeline(monkeypatch, DEMO_SID, {"demo", "public"}) == ["demo step"]


def test_colliding_tenant_cannot_read_demo_or_other_tenant_events(monkeypatch):
    assert _timeline(monkeypatch, DEMO_SID, {"evil"}) == ["injected"]
    assert _timeline(monkeypatch, "s1", {"globex"}) == ["globex event"]


def test_ambiguous_legacy_event_is_hidden_from_everyone(monkeypatch):
    # acme's untagged, unlinked event shares "s1" with globex: it can't be attributed.
    assert _timeline(monkeypatch, "s1", {"acme"}) == []
    assert "acme secret plan" not in _timeline(monkeypatch, "s1", {"globex"})


def test_unambiguous_legacy_event_stays_visible(monkeypatch):
    assert _timeline(monkeypatch, "solo", {"acme"}) == ["solo event"]
    assert _timeline(monkeypatch, "solo", {"globex"}) == []


def test_graph_view_attributes_events_by_owner(monkeypatch):
    _patch(monkeypatch)
    ids = {n["id"] for n in asyncio.run(graph.graph_view(namespaces=None))["nodes"]}
    assert ids == {"demo-sess", "demo-e1"}
    ids = {n["id"] for n in asyncio.run(graph.graph_view(namespaces={"globex"}))["nodes"]}
    assert ids == {"globex-sess", "globex-e1"}
    ids = {n["id"] for n in asyncio.run(graph.graph_view(namespaces={"acme"}))["nodes"]}
    assert ids == {"acme-sess", "solo-sess", "solo-e1"}


def test_session_event_counts_are_per_namespace(monkeypatch):
    _patch(monkeypatch)
    counts = {(s["session_id"], s["task"]): s["event_count"] for s in asyncio.run(graph.list_sessions(namespaces={"demo", "evil", "acme", "globex"}))}
    assert counts[(DEMO_SID, "demo")] == 1
    assert counts[(DEMO_SID, "spoof")] == 1
    assert counts[("s1", "globex")] == 1
    assert counts[("s1", "acme")] == 0
    assert counts[("solo", "solo")] == 1


def test_ingest_tags_session_events_with_namespace():
    from app.cognee_runtime.ingest import build_nodes

    nodes, _ = build_nodes({"session_id": "s1", "task": "t", "events": [{"kind": "note", "content": "x"}]}, "acme")
    events = [n for n in nodes if type(n).__name__ == "SessionEvent"]
    assert events and all(e.namespace == "acme" for e in events)
