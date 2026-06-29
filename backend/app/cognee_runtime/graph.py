"""Read the Cognee knowledge graph for the UI (graph view + session replay).

Cognee's graph adapters expose ``get_graph_data() -> (nodes, edges)`` where each
node is ``(id, properties)`` and each edge is ``(source_id, target_id, label,
properties)``. We normalize that into the shapes the frontend expects and stay
defensive about adapter differences.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .bootstrap import configure_cognee

# Node "type" values we assign meaning to (others still render).
_LABEL_FIELDS = ("name", "text", "task", "content", "memory_id", "event_id", "id")


async def _get_graph():
    configure_cognee()
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    nodes: List[Tuple[str, Dict[str, Any]]] = []
    edges: List[Tuple] = []
    if hasattr(engine, "get_graph_data"):
        data = await engine.get_graph_data()
        if isinstance(data, tuple) and len(data) == 2:
            nodes, edges = data
    return engine, nodes, edges


def _node_type(props: Dict[str, Any]) -> str:
    return str(props.get("type") or props.get("__type__") or "Node")


def _node_label(props: Dict[str, Any]) -> str:
    for field in _LABEL_FIELDS:
        val = props.get(field)
        if val:
            text = str(val)
            return text if len(text) <= 60 else text[:57] + "…"
    return _node_type(props)


async def graph_view(limit: int = 400) -> Dict[str, Any]:
    """Return {nodes, edges} for visualization."""
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception as exc:  # noqa: BLE001
        return {"nodes": [], "edges": [], "error": repr(exc)}

    nodes_out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw_nodes[:limit]:
        try:
            nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        except Exception:  # noqa: BLE001
            continue
        props = props or {}
        nid = str(nid)
        if nid in seen:
            continue
        seen.add(nid)
        nodes_out.append(
            {
                "id": nid,
                "label": _node_label(props),
                "type": _node_type(props),
                "props": {k: v for k, v in props.items() if k not in ("embedding",)},
            }
        )

    edges_out: List[Dict[str, Any]] = []
    for entry in raw_edges:
        try:
            if isinstance(entry, tuple):
                src, tgt = str(entry[0]), str(entry[1])
                label = str(entry[2]) if len(entry) > 2 else ""
            else:
                src, tgt, label = str(entry.get("source")), str(entry.get("target")), str(entry.get("label", ""))
        except Exception:  # noqa: BLE001
            continue
        if src in seen and tgt in seen:
            edges_out.append({"source": src, "target": tgt, "label": label})

    return {"nodes": nodes_out, "edges": edges_out}


def _event_session_id(props: Dict[str, Any]) -> str:
    """A SessionEvent's owning session id — explicit property, with id-prefix fallback."""
    sid = props.get("session_id")
    if sid:
        return str(sid)
    eid = str(props.get("event_id", ""))
    return eid.split(":", 1)[0] if ":" in eid else ""


async def list_sessions() -> List[Dict[str, Any]]:
    """All AgentSession nodes with an event count."""
    try:
        _engine, raw_nodes, _edges = await _get_graph()
    except Exception:
        return []
    event_counts: Dict[str, int] = {}
    agent_sessions: List[Dict[str, Any]] = []
    for entry in raw_nodes:
        _nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        t = _node_type(props)
        if t == "SessionEvent":
            sid = _event_session_id(props)
            if sid:
                event_counts[sid] = event_counts.get(sid, 0) + 1
        elif t == "AgentSession":
            agent_sessions.append(props)
    return [
        {
            "session_id": p.get("session_id", ""),
            "task": p.get("task", ""),
            "agent": p.get("agent"),
            "started_at": p.get("started_at"),
            "repo": {},
            "event_count": event_counts.get(p.get("session_id", ""), 0),
        }
        for p in agent_sessions
    ]


async def session_timeline(session_id: str) -> List[Dict[str, Any]]:
    """All SessionEvent nodes for a session, ordered by ordinal."""
    try:
        _engine, raw_nodes, _edges = await _get_graph()
    except Exception:
        return []
    events: List[Dict[str, Any]] = []
    for entry in raw_nodes:
        _nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        if _node_type(props) != "SessionEvent":
            continue
        if session_id and _event_session_id(props) != session_id:
            continue
        events.append(
            {
                "event_id": props.get("event_id", ""),
                "kind": props.get("kind", "event"),
                "content": props.get("content", ""),
                "timestamp": props.get("timestamp"),
                "ordinal": int(props.get("ordinal", 0) or 0),
            }
        )
    events.sort(key=lambda e: e["ordinal"])
    return events


async def count_nodes() -> Dict[str, int]:
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return {}
    counts: Dict[str, int] = {"_edges": len(raw_edges)}
    for entry in raw_nodes:
        _nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        t = _node_type(props or {})
        counts[t] = counts.get(t, 0) + 1
    return counts
