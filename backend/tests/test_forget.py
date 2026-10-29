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

    async def get_graph_data(self):
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
    assert res["status"] != "forgotten"
    assert engine.deleted == []


def test_lookup_matches_on_memory_id_and_namespace(monkeypatch):
    engine = _FakeEngine([_node("node-a", "s1:m0", "tenant_a"), _node("node-b", "s1:m0", "tenant_b")])
    _install(monkeypatch, engine)
    node_id, _ = asyncio.run(forget_module._find_memory_node_id("s1:m0", {"tenant_b"}))
    assert node_id == "node-b"
    node_id, _ = asyncio.run(forget_module._find_memory_node_id("s1:m0", {"tenant_a"}))
    assert node_id == "node-a"
