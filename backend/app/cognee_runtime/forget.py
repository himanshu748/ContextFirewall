"""Forget — governance: remove a memory so it can never reach a context pack again.

When the firewall blocks a memory or a human rejects it, ContextFirewall deletes
it from Cognee — the graph node and its vector embedding — so it disappears from
both recall and any future trusted context pack. This is the Cognee 'forget' verb
at per-memory granularity (the headline of the hackathon's forget() theme).
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Tuple

from .bootstrap import configure_cognee
from .recall import MEMORY_COLLECTION


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


async def forget_memory(memory_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    configure_cognee()
    node_id, engine = await _find_memory_node_id(memory_id)
    if not node_id:
        return {
            "memory_id": memory_id,
            "status": "not_found",
            "message": "No matching memory node found in the graph.",
        }

    deleted = {"graph": False, "vector": False}

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
    return {
        "memory_id": memory_id,
        "status": "forgotten" if ok else "error",
        "message": (
            f"Removed from {'graph' if deleted['graph'] else ''}"
            f"{' + ' if deleted['graph'] and deleted['vector'] else ''}"
            f"{'vector store' if deleted['vector'] else ''}."
            + (f" Reason: {reason}" if reason else "")
        )
        if ok
        else "Delete failed on both stores.",
    }
