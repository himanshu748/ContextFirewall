"""Read the Cognee knowledge graph for the UI (graph view + session replay).

Cognee's graph adapters expose ``get_graph_data() -> (nodes, edges)`` where each
node is ``(id, properties)`` and each edge is ``(source_id, target_id, label,
properties)``. We normalize that into the shapes the frontend expects and stay
defensive about adapter differences.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.firewall.secrets import redact_text

from .bootstrap import configure_cognee
from .recall import effective_namespace, in_namespace

logger = logging.getLogger(__name__)

# Node "type" values we assign meaning to (others still render).
_LABEL_FIELDS = ("name", "text", "task", "content", "memory_id", "event_id", "id")
_RECENCY_FIELDS = ("updated_at", "created_at", "timestamp", "started_at")
_GRAPH_ERROR = "Graph data is temporarily unavailable."


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
            text = redact_text(str(val))
            return text if len(text) <= 60 else text[:57] + "…"
    return _node_type(props)


def _safe_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Copy node props for the UI, dropping embeddings and redacting secret-bearing text."""
    out: Dict[str, Any] = {}
    for k, v in props.items():
        if k == "embedding":
            continue
        out[k] = redact_text(v) if k in ("text", "content") and isinstance(v, str) else v
    return out


def _node_recency(props: Dict[str, Any]) -> float:
    """Return a sortable timestamp for a node, or negative infinity if absent."""
    for field in _RECENCY_FIELDS:
        value = props.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        try:
            return parsed.timestamp()
        except (OverflowError, OSError):
            continue
    return float("-inf")


def _node_priority(props: Dict[str, Any]) -> Tuple[bool, float]:
    """Prefer typed nodes, then the most recent node, when the graph is capped."""
    return bool(props.get("type") or props.get("__type__")), _node_recency(props)


async def graph_view(limit: int = 400, namespaces=None) -> Dict[str, Any]:
    """Return {nodes, edges} for visualization."""
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load graph data")
        return {"nodes": [], "edges": [], "truncated": False, "error": _GRAPH_ERROR}

    owners = _EventOwners(raw_nodes, raw_edges)

    visible_nodes: List[Tuple[str, Dict[str, Any], str]] = []
    seen: set[str] = set()
    for entry in raw_nodes:
        try:
            nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        except Exception:  # noqa: BLE001
            continue
        props = props or {}
        nid = str(nid)
        if nid in seen:
            continue
        node_type = _node_type(props)
        node_ns_props = props
        if node_type == "SessionEvent":
            ns = owners.namespace(nid, props)
            node_ns_props = {"namespace": ns} if ns else {}
        if not in_namespace(node_ns_props, namespaces):
            continue
        seen.add(nid)
        visible_nodes.append((nid, props, node_type))

    visible_limit = max(0, limit)
    truncated = len(visible_nodes) > visible_limit
    prioritized = sorted(visible_nodes, key=lambda node: _node_priority(node[1]), reverse=True)
    selected_ids = {nid for nid, _props, _node_type_value in prioritized[:visible_limit]}

    nodes_out: List[Dict[str, Any]] = []
    for nid, props, node_type in visible_nodes:
        if nid not in selected_ids:
            continue
        nodes_out.append(
            {
                "id": nid,
                "label": _node_label(props),
                "type": node_type,
                "props": _safe_props(props),
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
        if src in selected_ids and tgt in selected_ids:
            edges_out.append({"source": src, "target": tgt, "label": label})

    return {"nodes": nodes_out, "edges": edges_out, "truncated": truncated}


def _event_session_id(props: Dict[str, Any]) -> str:
    """A SessionEvent's owning session id, explicit property, with id-prefix fallback."""
    sid = props.get("session_id")
    if sid:
        return str(sid)
    eid = str(props.get("event_id", ""))
    return eid.split(":", 1)[0] if ":" in eid else ""


def _entry(entry: Any) -> Tuple[str, Dict[str, Any]]:
    nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
    return str(nid), props or {}


def _edge_ends(entry: Any) -> Tuple[str, str]:
    if isinstance(entry, tuple):
        return str(entry[0]), str(entry[1])
    return str(entry.get("source")), str(entry.get("target"))


class _EventOwners:
    """Resolve which namespace owns each SessionEvent.

    Session ids are caller-chosen, so two tenants (or a tenant and the public
    demo) can share one. An event is attributed by its own ``namespace`` tag,
    then (older events) by its edge to an AgentSession node, then by session id
    only when no other namespace uses that id. Anything else is unattributable.
    """

    def __init__(self, raw_nodes: List[Any], raw_edges: List[Any]) -> None:
        sessions_by_node: Dict[str, Dict[str, Any]] = {}
        self.sessions_by_id: Dict[str, List[Dict[str, Any]]] = {}
        for entry in raw_nodes:
            try:
                nid, props = _entry(entry)
            except Exception:  # noqa: BLE001
                continue
            if _node_type(props) == "AgentSession" and props.get("session_id"):
                sessions_by_node[nid] = props
                self.sessions_by_id.setdefault(str(props["session_id"]), []).append(props)
        self._linked: Dict[str, Dict[str, Any]] = {}
        for entry in raw_edges or []:
            try:
                src, tgt = _edge_ends(entry)
            except Exception:  # noqa: BLE001
                continue
            if tgt in sessions_by_node:
                self._linked.setdefault(src, sessions_by_node[tgt])
            elif src in sessions_by_node:
                self._linked.setdefault(tgt, sessions_by_node[src])

    def namespace(self, node_id: str, props: Dict[str, Any]) -> Optional[str]:
        own = props.get("namespace")
        if own:
            return str(own)
        linked = self._linked.get(node_id)
        if linked is not None:
            return effective_namespace(linked)
        owners = {effective_namespace(p) for p in self.sessions_by_id.get(_event_session_id(props), [])}
        if len(owners) == 1 and None not in owners:
            return next(iter(owners))
        return None


async def list_sessions(namespaces=None, include_all: bool = False) -> List[Dict[str, Any]]:
    """All AgentSession nodes with an event count.

    ``include_all`` is for internal pipelines (e.g. rule distillation) that must
    span every namespace; public endpoints always leave it False.
    """
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return []
    owners = _EventOwners(raw_nodes, raw_edges)
    event_counts: Dict[Tuple[Optional[str], str], int] = {}
    agent_sessions: List[Dict[str, Any]] = []
    for entry in raw_nodes:
        nid, props = _entry(entry)
        t = _node_type(props)
        if t == "SessionEvent":
            sid = _event_session_id(props)
            if sid:
                key = (owners.namespace(nid, props), sid)
                event_counts[key] = event_counts.get(key, 0) + 1
        elif t == "AgentSession":
            if not include_all:
                if not in_namespace(props, namespaces):
                    continue
                if effective_namespace(props) == "demo" and str(props.get("session_id", "")).startswith("mcp-"):
                    continue
            agent_sessions.append(props)
    return [
        {
            "session_id": p.get("session_id", ""),
            "task": p.get("task", ""),
            "agent": p.get("agent"),
            "started_at": p.get("started_at"),
            "repo": {},
            "event_count": event_counts.get((effective_namespace(p), p.get("session_id", "")), 0),
        }
        for p in agent_sessions
    ]


async def session_timeline(session_id: str, namespaces=None, include_all: bool = False) -> List[Dict[str, Any]]:
    """All SessionEvent nodes for a session, ordered by ordinal.

    ``include_all`` bypasses namespace scoping for internal pipelines only.
    """
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return []
    owners = _EventOwners(raw_nodes, raw_edges)
    candidates = owners.sessions_by_id.get(str(session_id), [])
    if not include_all:
        candidates = [
            p
            for p in candidates
            if in_namespace(p, namespaces)
            and not (effective_namespace(p) == "demo" and str(session_id).startswith("mcp-"))
        ]
    if not candidates:
        return []
    owner_ns = effective_namespace(candidates[0])
    if owner_ns is None:
        return []
    events: List[Dict[str, Any]] = []
    for entry in raw_nodes:
        nid, props = _entry(entry)
        if _node_type(props) != "SessionEvent":
            continue
        if session_id and _event_session_id(props) != session_id:
            continue
        if owners.namespace(nid, props) != owner_ns:
            continue
        events.append(
            {
                "event_id": props.get("event_id", ""),
                "kind": props.get("kind", "event"),
                "content": redact_text(props.get("content", "")),
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
