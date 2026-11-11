from __future__ import annotations

import asyncio

import cognee.infrastructure.databases.graph as graph_module
import cognee.infrastructure.databases.vector as vector_module

import app.cognee_runtime.forget as forget_module


class _FakeEngine:
    """In-memory stand-in for the Cognee graph engine."""

    def __init__(self, nodes):
        self._nodes = nodes
        self.deleted: list[str] = []
        self.graph_reads = 0

    async def get_graph_data(self):
        self.graph_reads += 1
        return list(self._nodes), []

    async def delete_node(self, node_id):
        self.deleted.append(str(node_id))


def _node(node_id: str, memory_id: str, namespace: str):
    return (node_id, {"memory_id": memory_id, "namespace": namespace, "type": "Memory"})


def _install(monkeypatch, engine: _FakeEngine):
    async def fake_get_graph_engine():
        return engine

    monkeypatch.setattr(graph_module, "get_graph_engine", fake_get_graph_engine)
    monkeypatch.setattr(forget_module, "configure_cognee", lambda: {})
    # No vector engine: graph deletion alone must still report "forgotten".
    monkeypatch.setattr(vector_module, "get_vector_engine", lambda: object())


def test_each_tenant_forgets_its_own_node_despite_id_collision(monkeypatch):
    # Same memory_id in two namespaces; tenant_a's node was inserted first.
    # Before #13 the lookup returned tenant_a's node and tenant_b got
    # "forbidden" — unable to delete its OWN memory.
    engine = _FakeEngine([_node("node-a", "s1:m0", "tenant_a"), _node("node-b", "s1:m0", "tenant_b")])
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("s1:m0", allowed_namespaces={"tenant_b"}))
    assert res["status"] == "forgotten"
    assert engine.deleted == ["node-b"]


def test_insertion_order_does_not_matter(monkeypatch):
    engine = _FakeEngine([_node("node-b", "s1:m0", "tenant_b"), _node("node-a", "s1:m0", "tenant_a")])
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("s1:m0", allowed_namespaces={"tenant_b"}))
    assert res["status"] == "forgotten"
    assert engine.deleted == ["node-b"]


def test_demo_node_does_not_shadow_own_node(monkeypatch):
    engine = _FakeEngine([_node("node-demo", "s1:m0", "demo"), _node("node-b", "s1:m0", "tenant_b")])
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("s1:m0", allowed_namespaces={"tenant_b"}))
    assert res["status"] == "forgotten"
    assert engine.deleted == ["node-b"]


def test_other_tenants_node_is_never_deleted(monkeypatch):
    engine = _FakeEngine([_node("node-a", "s1:m0", "tenant_a")])
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("s1:m0", allowed_namespaces={"tenant_b"}))
    missing = asyncio.run(forget_module.forget_memory("no-such-memory", allowed_namespaces={"tenant_b"}))
    assert res == {**missing, "memory_id": "s1:m0"}
    assert "tenant_a" not in str(res)
    assert engine.deleted == []
    assert engine.graph_reads == 2  # One lookup for each ID; neither enters deletion.


def test_demo_memory_still_reports_immutable_without_deletion(monkeypatch):
    engine = _FakeEngine([_node("node-demo", "demo:m0", "demo")])
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("demo:m0", allowed_namespaces={"tenant_b"}))
    assert res["status"] == "forbidden"
    assert res["message"] == "Demo memories are immutable."
    assert engine.deleted == []


def test_foreign_memory_is_indistinguishable_from_missing_with_restricted_scope(monkeypatch):
    engine = _FakeEngine([_node("node-a", "private:m0", "tenant_a")])
    _install(monkeypatch, engine)
    foreign = asyncio.run(forget_module.forget_memory("private:m0", allowed_namespaces={"tenant_b"}))
    missing = asyncio.run(forget_module.forget_memory("missing:m0", allowed_namespaces={"tenant_b"}))
    assert foreign["status"] == missing["status"] == "not_found"
    assert foreign["message"] == missing["message"]
    assert engine.deleted == []
    assert engine.graph_reads == 2


def test_default_scope_can_forget_a_non_demo_memory(monkeypatch):
    engine = _FakeEngine([_node("node-a", "private:m0", "tenant_a")])
    _install(monkeypatch, engine)
    result = asyncio.run(forget_module.forget_memory("private:m0"))
    assert result["status"] == "forgotten"
    assert engine.deleted == ["node-a"]


def test_lookup_matches_on_memory_id_and_namespace(monkeypatch):
    engine = _FakeEngine([_node("node-a", "s1:m0", "tenant_a"), _node("node-b", "s1:m0", "tenant_b")])
    _install(monkeypatch, engine)
    node_id, _ = asyncio.run(forget_module._find_memory_node_id("s1:m0", {"tenant_b"}))
    assert node_id == "node-b"
    node_id, _ = asyncio.run(forget_module._find_memory_node_id("s1:m0", {"tenant_a"}))
    assert node_id == "node-a"


class _FakeGraphEngine:
    """In-memory graph engine that also carries edges (for cleanup tests)."""

    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges
        self.deleted: list[str] = []

    async def get_graph_data(self):
        return list(self._nodes), list(self._edges)

    async def delete_node(self, node_id):
        self.deleted.append(str(node_id))

    async def delete_nodes(self, node_ids):
        self.deleted.extend(str(n) for n in node_ids)


def _memory(node_id: str, memory_id: str, namespace: str, session_id: str):
    return (
        node_id,
        {
            "memory_id": memory_id,
            "namespace": namespace,
            "type": "Memory",
            "source_session_id": session_id,
        },
    )


def _session(node_id: str, session_id: str, namespace: str):
    return (node_id, {"session_id": session_id, "namespace": namespace, "type": "AgentSession"})


def _event(node_id: str, session_id: str):
    # SessionEvent carries no namespace of its own; it inherits its session's.
    return (node_id, {"session_id": session_id, "type": "SessionEvent"})


def _shared_session_graph():
    """Two tenants, one shared session_id (session ids are caller-chosen).

    Tenant A has session/event nodes but NO Memory node left; tenant B's last
    memory points at the shared session via source_session_id.
    """
    nodes = [
        _session("sess-a", "shared-s", "tenant_a"),
        _event("evt-a", "shared-s"),
        _session("sess-b", "shared-s", "tenant_b"),
        _event("evt-b", "shared-s"),
        _memory("mem-b", "shared-s:m0", "tenant_b", "shared-s"),
    ]
    edges = [("evt-a", "sess-a", "session"), ("evt-b", "sess-b", "session")]
    return nodes, edges


def test_forget_as_b_removes_only_bs_orphans_when_session_id_is_shared(monkeypatch):
    # Regression test requested on PR #61: forgetting B's last memory must
    # remove only B's memory and B's orphaned session/events — never A's,
    # even though both tenants share the same session_id.
    nodes, edges = _shared_session_graph()
    engine = _FakeGraphEngine(nodes, edges)
    _install(monkeypatch, engine)
    res = asyncio.run(forget_module.forget_memory("shared-s:m0", allowed_namespaces={"tenant_b"}))
    assert res["status"] == "forgotten"
    assert set(engine.deleted) == {"mem-b", "sess-b", "evt-b"}
    assert "sess-a" not in engine.deleted
    assert "evt-a" not in engine.deleted


def test_orphan_cleanup_is_scoped_to_the_forgotten_memorys_namespace():
    nodes, edges = _shared_session_graph()
    cleanup = forget_module.orphan_node_ids(nodes, edges, "mem-b")
    assert cleanup == {"sess-b", "evt-b"}


def test_orphan_cleanup_still_works_for_a_single_tenant_without_edges():
    # Legacy shape: no session edges in the graph payload at all.
    nodes = [
        _session("sess-a", "s1", "tenant_a"),
        _event("evt-a", "s1"),
        _memory("mem-a", "s1:m0", "tenant_a", "s1"),
    ]
    assert forget_module.orphan_node_ids(nodes, [], "mem-a") == {"sess-a", "evt-a"}


def test_orphan_cleanup_skips_session_while_own_tenant_memory_remains():
    nodes, edges = _shared_session_graph()
    nodes.append(_memory("mem-b2", "shared-s:m1", "tenant_b", "shared-s"))
    assert forget_module.orphan_node_ids(nodes, edges, "mem-b") == set()


def test_other_tenants_remaining_memory_does_not_block_cleanup():
    nodes, edges = _shared_session_graph()
    nodes.append(_memory("mem-a", "shared-s:m9", "tenant_a", "shared-s"))
    assert forget_module.orphan_node_ids(nodes, edges, "mem-b") == {"sess-b", "evt-b"}
