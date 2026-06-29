"""Recall — retrieve candidate memories from Cognee for the firewall to audit.

The vector store only embeds the indexed ``text`` field, so its payload lacks our
custom Memory fields (subject, trust_score, created_at, ...). Those live as graph
node properties. So recall *joins* the two: vector search for relevance ranking,
the graph for the full, trustworthy record (keyed by the shared node id).

We return the full memory set (ranked) so the cluster-level checks (staleness /
contradiction) always see a memory's same-subject peers.

``recall_answer`` returns the ungoverned GRAPH_COMPLETION answer — the baseline
the firewall improves on in the demo.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, List

from .bootstrap import configure_cognee

MEMORY_COLLECTION = "Memory_text"
_MAX_CLUSTER = 200


def _coerce_record(node_id: str, props: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": str(node_id),
        "memory_id": props.get("memory_id") or str(node_id),
        "text": props.get("text", ""),
        "kind": props.get("kind", "fact"),
        "subject": props.get("subject"),
        "created_at": props.get("created_at"),
        "trust_score": float(props.get("trust_score", 0.5) or 0.0),
        "status": props.get("status", "candidate"),
        "reinforcement_count": int(props.get("reinforcement_count", 1) or 1),
        "evidence_event_ids": props.get("evidence_event_ids") or [],
        "source_session_id": props.get("source_session_id"),
    }


async def _load_graph_memories() -> Dict[str, Dict[str, Any]]:
    """All Memory nodes from the graph, keyed by node id (full custom fields)."""
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    try:
        nodes, _edges = await engine.get_graph_data()
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for entry in nodes:
        nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        if props.get("type") == "Memory":
            out[str(nid)] = _coerce_record(nid, props)
    return out


async def _vector_rank(query: str, top_k: int) -> List[str]:
    """Node ids ordered by vector relevance to the query (best effort)."""
    from cognee.infrastructure.databases.vector import get_vector_engine

    engine = get_vector_engine()  # sync factory -> handle
    try:
        results = engine.search(
            collection_name=MEMORY_COLLECTION, query_text=query, limit=top_k, include_payload=False
        )
        if inspect.isawaitable(results):
            results = await results
    except Exception:
        return []
    return [str(getattr(r, "id", "")) for r in (results or [])]


async def recall_memory_candidates(query: str, *, top_k: int = 12) -> List[Dict[str, Any]]:
    configure_cognee()
    graph_mems = await _load_graph_memories()
    if not graph_mems:
        return []

    ranked_ids = await _vector_rank(query, top_k=top_k)
    ordered: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for nid in ranked_ids:
        rec = graph_mems.get(nid)
        if rec and nid not in seen:
            ordered.append(rec)
            seen.add(nid)
    # Include remaining memories so cluster checks see every same-subject peer.
    for nid, rec in graph_mems.items():
        if nid not in seen:
            ordered.append(rec)
            seen.add(nid)
    return ordered[:_MAX_CLUSTER]


async def recall_answer(query: str) -> str:
    """The ungoverned baseline: ask Cognee's graph directly (GRAPH_COMPLETION)."""
    configure_cognee()
    import cognee
    from cognee import SearchType

    try:
        results = await cognee.search(query_text=query, query_type=SearchType.GRAPH_COMPLETION)
    except Exception as exc:  # noqa: BLE001
        return f"(graph completion unavailable: {exc!r})"
    if isinstance(results, list):
        return " ".join(str(x) for x in results) if results else ""
    return str(results)
