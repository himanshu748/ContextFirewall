"""Forget — governance: remove a memory so it can never reach a context pack again.

When the firewall blocks a memory or a human rejects it, ContextFirewall deletes
it from Cognee — the graph node and its vector embedding — so it disappears from
both recall and any future trusted context pack. This is the Cognee 'forget' verb
at per-memory granularity (the headline of the hackathon's forget() theme).
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .bootstrap import configure_cognee
from .recall import MEMORY_COLLECTION


def _entry_id(entry: Any) -> str:
    if isinstance(entry, tuple):
        return str(entry[0])
    return str((entry or {}).get("id", ""))


def _entry_props(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, tuple):
        return dict(entry[1] or {})
    return dict(entry or {})


def _edge_parts(entry: Any) -> Tuple[str, str, str]:
    if isinstance(entry, tuple):
        src = str(entry[0]) if len(entry) > 0 else ""
        tgt = str(entry[1]) if len(entry) > 1 else ""
        label = str(entry[2]) if len(entry) > 2 else ""
        if not label and len(entry) > 3 and isinstance(entry[3], dict):
            label = str(entry[3].get("label", ""))
        return src, tgt, label
    if isinstance(entry, dict):
        return (
            str(entry.get("source", "")),
            str(entry.get("target", "")),
            str(entry.get("label", "")),
        )
    return "", "", ""


def _same_subject(text_a: Any, text_b: Any) -> bool:
    return str(text_a or "").strip().lower() == str(text_b or "").strip().lower()


def orphan_node_ids(nodes: Iterable[Any], edges: Iterable[Any], forgotten_memory_node_id: str) -> set[str]:
    """Return best-effort cleanup ids for a forgotten memory node.

    The helper is pure and operates on raw graph payloads so tests can exercise
    the cleanup logic without a live Cognee backend.
    """
    node_map: Dict[str, Dict[str, Any]] = {}
    for entry in nodes:
        node_map[_entry_id(entry)] = _entry_props(entry)

    forgotten_id = str(forgotten_memory_node_id)
    mem_props = node_map.get(forgotten_id, {})
    if (mem_props.get("type") or "") != "Memory":
        return set()

    session_id = mem_props.get("source_session_id")
    if not session_id:
        return set()

    # If any other memory remains in the same session, nothing else should be removed.
    for nid, props in node_map.items():
        if nid == forgotten_id:
            continue
        if props.get("type") == "Memory" and props.get("source_session_id") == session_id:
            return set()

    cleanup: set[str] = set()
    session_node_ids = {
        nid
        for nid, props in node_map.items()
        if props.get("type") == "AgentSession" and props.get("session_id") == session_id
    }
    if not session_node_ids:
        return set()
    cleanup.update(session_node_ids)

    event_ids = {
        nid
        for nid, props in node_map.items()
        if props.get("type") == "SessionEvent" and _same_subject(props.get("session_id"), session_id)
    }
    cleanup.update(event_ids)

    repo_ids: set[str] = set()
    for entry in edges:
        src, tgt, label = _edge_parts(entry)
        if not src or not tgt:
            continue
        if src in session_node_ids or tgt in session_node_ids:
            other = tgt if src in session_node_ids else src
            other_props = node_map.get(other, {})
            if label.lower() == "repo" or other_props.get("type") == "Repo":
                repo_ids.add(other)

    for repo_id in list(repo_ids):
        for entry in edges:
            src, tgt, _label = _edge_parts(entry)
            if repo_id not in (src, tgt):
                continue
            other = tgt if src == repo_id else src
            if other in session_node_ids:
                continue
            if node_map.get(other, {}).get("type") == "AgentSession":
                return cleanup

    cleanup.update(repo_ids)
    return cleanup


async def _find_memory_node_id(memory_id: str) -> Tuple[Optional[str], Any]:
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    if hasattr(engine, "get_graph_data"):
        try:
            nodes, _edges = await engine.get_graph_data()
        except Exception:  # noqa: BLE001
            return None, engine
        for entry in nodes:
            nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
            if (props or {}).get("memory_id") == memory_id:
                return str(nid), engine
    return None, engine


async def forget_memory(
    memory_id: str,
    reason: Optional[str] = None,
    *,
    allowed_namespaces: set[str] | None = None,
    allow_demo: bool = False,
) -> Dict[str, Any]:
    configure_cognee()
    node_id, engine = await _find_memory_node_id(memory_id)
    if not node_id:
        return {
            "memory_id": memory_id,
            "status": "not_found",
            "message": "No matching memory node found in the graph.",
        }

    deleted = {"graph": False, "vector": False}
    memory_props: Dict[str, Any] = {}
    graph_nodes: List[Any] = []
    graph_edges: List[Any] = []
    try:
        graph_nodes, graph_edges = await engine.get_graph_data()
        for entry in graph_nodes:
            nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
            if str(nid) == node_id:
                memory_props = props or {}
                break
    except Exception:  # noqa: BLE001
        memory_props = {}

    namespace = str((memory_props or {}).get("namespace") or "demo")
    if namespace == "demo" and not allow_demo:
        return {
            "memory_id": memory_id,
            "status": "forbidden",
            "message": "Demo memories are immutable.",
        }
    if allowed_namespaces is not None and namespace not in allowed_namespaces:
        return {
            "memory_id": memory_id,
            "status": "forbidden",
            "message": f"Memory lives in namespace '{namespace}', which is not allowed here.",
        }

    # Graph node delete (cascades its edges).
    try:
        if hasattr(engine, "delete_node"):
            await engine.delete_node(node_id)
            deleted["graph"] = True
        elif hasattr(engine, "delete_nodes"):
            await engine.delete_nodes([node_id])
            deleted["graph"] = True
    except Exception:  # noqa: BLE001
        pass

    # Vector embedding delete (otherwise the stale memory resurfaces in recall).
    try:
        from cognee.infrastructure.databases.vector import get_vector_engine

        vector_engine = get_vector_engine()  # sync factory -> handle
        if hasattr(vector_engine, "delete_data_points"):
            res = vector_engine.delete_data_points(MEMORY_COLLECTION, [node_id])
            if inspect.isawaitable(res):
                await res
            deleted["vector"] = True
    except Exception:  # noqa: BLE001
        pass

    ok = deleted["graph"] or deleted["vector"]
    cleanup_done = False
    if ok:
        try:
            cleanup_ids = orphan_node_ids(graph_nodes, graph_edges, node_id)
            if cleanup_ids:
                cleanup_done = True
                try:
                    if hasattr(engine, "delete_nodes"):
                        await engine.delete_nodes(sorted(cleanup_ids))
                    else:
                        for did in sorted(cleanup_ids):
                            await engine.delete_node(did)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
    return {
        "memory_id": memory_id,
        "status": "forgotten" if ok else "error",
        "message": (
            f"Removed from {'graph' if deleted['graph'] else ''}"
            f"{' + ' if deleted['graph'] and deleted['vector'] else ''}"
            f"{'vector store' if deleted['vector'] else ''}."
            + (" + removed orphaned session" if cleanup_done else "")
            + (f" Reason: {reason}" if reason else "")
        )
        if ok
        else "Delete failed on both stores.",
    }
