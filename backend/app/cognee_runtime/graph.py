"""Read the Cognee knowledge graph for the UI (graph view + session replay).

Cognee's graph adapters expose ``get_graph_data() -> (nodes, edges)`` where each
node is ``(id, properties)`` and each edge is ``(source_id, target_id, label,
properties)``. We normalize that into the shapes the frontend expects and stay
defensive about adapter differences.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.firewall.secrets import redact_text

from .bootstrap import configure_cognee
from .recall import effective_namespace, in_namespace, node_namespaces

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
    """Redact every string in graph properties, including legacy nested metadata."""
    def safe_value(value: Any) -> Any:
        if isinstance(value, str):
            return redact_text(value)
        if isinstance(value, dict):
            return {key: safe_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [safe_value(item) for item in value]
        return value

    return {key: safe_value(value) for key, value in props.items() if key != "embedding"}


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


def _event_scopes(raw_nodes, raw_edges) -> Dict[str, Tuple[Dict[str, Any], str | None]]:
    """Resolve events by graph-node relationships, never by client-supplied session_id.

    New events have an explicit namespace. For older events, the typed session
    edge identifies their owner. Missing, conflicting, or ambiguous ownership
    is excluded, including when two tenants reuse the same session_id.
    """
    nodes_by_id: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for entry in raw_nodes:
        try:
            nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        except (AttributeError, IndexError, TypeError, ValueError):
            continue
        if nid is not None:
            props = props or {}
            nodes_by_id[str(nid)] = (_node_type(props), props)

    session_links: Dict[str, set[str]] = {}
    for edge in raw_edges:
        try:
            src, tgt = (edge[0], edge[1]) if isinstance(edge, tuple) else (edge["source"], edge["target"])
        except (KeyError, IndexError, TypeError):
            continue
        src, tgt = str(src), str(tgt)
        source_node, target_node = nodes_by_id.get(src), nodes_by_id.get(tgt)
        if (source_node is not None and source_node[0] == "SessionEvent"
                and target_node is not None and target_node[0] == "AgentSession"):
            session_links.setdefault(src, set()).add(tgt)

    scopes: Dict[str, Tuple[Dict[str, Any], str | None]] = {}
    for nid, (node_type, props) in nodes_by_id.items():
        if node_type != "SessionEvent":
            continue
        event_namespaces = node_namespaces(props)
        if len(event_namespaces) > 1:
            continue
        owners = session_links.get(nid, set())
        if len(owners) > 1:
            continue
        if owners:
            owner_id = next(iter(owners))
            owner_props = nodes_by_id[owner_id][1]
            owner_namespaces = node_namespaces(owner_props)
            if len(owner_namespaces) != 1 or (event_namespaces and event_namespaces != owner_namespaces):
                continue
            scopes[nid] = (owner_props, owner_id)
        elif len(event_namespaces) == 1:
            scopes[nid] = (props, None)
    return scopes


async def graph_view(limit: int = 400, namespaces=None) -> Dict[str, Any]:
    """Return {nodes, edges} for visualization."""
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load graph data")
        return {"nodes": [], "edges": [], "truncated": False, "error": _GRAPH_ERROR}

    event_scopes = _event_scopes(raw_nodes, raw_edges)

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
            resolved = event_scopes.get(nid)
            if resolved is None:
                continue
            node_ns_props = resolved[0]
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


async def list_sessions(namespaces=None, include_all: bool = False) -> List[Dict[str, Any]]:
    """All AgentSession nodes with an event count.

    ``include_all`` is for internal pipelines (e.g. rule distillation) that must
    span every namespace; public endpoints always leave it False.
    """
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return []
    event_counts: Dict[str, int] = {}
    for _scope, owner_id in _event_scopes(raw_nodes, raw_edges).values():
        if owner_id is not None:
            event_counts[owner_id] = event_counts.get(owner_id, 0) + 1
    agent_sessions: List[Tuple[str, Dict[str, Any]]] = []
    for entry in raw_nodes:
        nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        t = _node_type(props)
        if t == "AgentSession":
            if not include_all:
                if not in_namespace(props, namespaces):
                    continue
                if effective_namespace(props) == "demo" and str(props.get("session_id", "")).startswith("mcp-"):
                    continue
            agent_sessions.append((str(nid), props))
    return [
        {
            "session_id": p.get("session_id", ""),
            "task": p.get("task", ""),
            "agent": p.get("agent"),
            "started_at": p.get("started_at"),
            "repo": {},
            "event_count": event_counts.get(nid, 0),
        }
        for nid, p in agent_sessions
    ]


async def session_timeline(session_id: str, namespaces=None, include_all: bool = False) -> List[Dict[str, Any]]:
    """All SessionEvent nodes for a session, ordered by ordinal.

    ``include_all`` bypasses namespace scoping for internal pipelines only.
    """
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return []
    candidate_session_ids = []
    for entry in raw_nodes:
        nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        if _node_type(props) != "AgentSession" or props.get("session_id") != session_id:
            continue
        if not include_all and (not in_namespace(props, namespaces)
                                or (effective_namespace(props) == "demo" and str(session_id).startswith("mcp-"))):
            continue
        candidate_session_ids.append(str(nid))
    # The URL has only a session_id, so multiple matching accessible sessions
    # cannot be distinguished safely, even if their graph IDs are different.
    if len(candidate_session_ids) != 1:
        return []
    owner_id = candidate_session_ids[0]
    event_scopes = _event_scopes(raw_nodes, raw_edges)
    events: List[Dict[str, Any]] = []
    for entry in raw_nodes:
        nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        if _node_type(props) != "SessionEvent":
            continue
        resolved = event_scopes.get(str(nid))
        if resolved is None or resolved[1] != owner_id:
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


async def count_nodes(namespaces=None, source_session_id: str | None = None) -> Dict[str, int]:
    """Count admitted nodes and their edges; optionally count one session's memories."""
    try:
        _engine, raw_nodes, raw_edges = await _get_graph()
    except Exception:
        return {}

    if namespaces is None and source_session_id is None:
        counts: Dict[str, int] = {"_edges": len(raw_edges)}
        for entry in raw_nodes:
            _nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
            t = _node_type(props or {})
            counts[t] = counts.get(t, 0) + 1
        return counts

    event_scopes = _event_scopes(raw_nodes, raw_edges)
    counts: Dict[str, int] = {"_edges": 0}
    admitted_ids: set[str] = set()
    for entry in raw_nodes:
        nid, props = entry if isinstance(entry, tuple) else (entry.get("id"), entry)
        props = props or {}
        node_type = _node_type(props)
        scope = props
        if node_type == "SessionEvent":
            resolved = event_scopes.get(str(nid))
            if resolved is None:
                continue
            scope = resolved[0]
        if namespaces is not None and not in_namespace(scope, namespaces):
            continue
        if source_session_id is not None and (
            node_type != "Memory" or str(props.get("source_session_id", "")) != source_session_id
        ):
            continue
        admitted_ids.add(str(nid))
        counts[node_type] = counts.get(node_type, 0) + 1

    for edge in raw_edges:
        try:
            src, tgt = (edge[0], edge[1]) if isinstance(edge, tuple) else (edge["source"], edge["target"])
            if str(src) in admitted_ids and str(tgt) in admitted_ids:
                counts["_edges"] += 1
        except (KeyError, IndexError, TypeError):
            continue
    return counts
