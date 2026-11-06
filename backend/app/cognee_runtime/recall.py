"""Recall — retrieve candidate memories from Cognee for the firewall to audit.

The vector store only embeds the indexed ``text`` field, so its payload lacks our
custom Memory fields (subject, trust_score, created_at, ...). Those live as graph
node properties. So recall *joins* the two: vector search for relevance ranking,
the graph for the full, trustworthy record (keyed by the shared node id).

We return ranked memories together with their same-subject peers so the
cluster-level checks (staleness / contradiction) still see related context.

``recall_answer`` returns the ungoverned GRAPH_COMPLETION answer — the baseline
the firewall improves on in the demo.
"""
from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Dict, List, Optional, Set

from app.firewall.secrets import redact_text

from .bootstrap import configure_cognee

MEMORY_COLLECTION = "Memory_text"
_MAX_CLUSTER = 200

logger = logging.getLogger(__name__)


def _coerce_record(node_id: str, props: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": str(node_id),
        "memory_id": props.get("memory_id") or str(node_id),
        "text": redact_text(str(props.get("text") or "")),
        "kind": props.get("kind", "fact"),
        "subject": props.get("subject"),
        "created_at": props.get("created_at"),
        "trust_score": float(props.get("trust_score", 0.5) or 0.0),
        "status": props.get("status", "candidate"),
        "reinforcement_count": int(props.get("reinforcement_count", 1) or 1),
        "evidence_event_ids": props.get("evidence_event_ids") or [],
        "source_session_id": props.get("source_session_id"),
        "namespace": props.get("namespace"),
    }


DEMO_NAMESPACE = "demo"
# Node set attached to everything Cognee derives (chunks, entities, ...) from one
# namespace's transcripts, so those nodes can be attributed to a tenant.
NAMESPACE_NODESET_PREFIX = "cf_ns_"
# Our typed nodes always carry ``namespace``; one without it predates
# multi-tenancy, when only the demo was writable. SessionEvent is excluded: it
# inherits its session's namespace.
_LEGACY_DEMO_TYPES = {"Repo", "AgentSession", "Memory"}


def namespace_nodeset(namespace: str) -> str:
    return f"{NAMESPACE_NODESET_PREFIX}{namespace or DEMO_NAMESPACE}"


def _nodeset_names(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
        if isinstance(value, str):
            return [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v.get("name") if isinstance(v, dict) else v) for v in value if v]


def _namespaces_from_nodesets(names: List[str]) -> Set[str]:
    from .improve import RULES_NODESET

    found: Set[str] = set()
    for name in names:
        if name.startswith(NAMESPACE_NODESET_PREFIX) and len(name) > len(NAMESPACE_NODESET_PREFIX):
            found.add(name[len(NAMESPACE_NODESET_PREFIX):])
        elif name.startswith(f"{RULES_NODESET}_") and len(name) > len(RULES_NODESET) + 1:
            found.add(name[len(RULES_NODESET) + 1:])
        elif name == RULES_NODESET:  # legacy global rules set: operator-written demo content
            found.add(DEMO_NAMESPACE)
    return found


def node_namespaces(props: Dict[str, Any]) -> Set[str]:
    """Every namespace a graph node belongs to; empty when it can't be attributed.

    Cognee merges node-set tags when several namespaces produce the same node
    (e.g. one entity mentioned by two tenants), so a node can carry more than one.
    """
    ns = props.get("namespace")
    if ns:
        return {str(ns)}
    if str(props.get("type") or props.get("__type__") or "") in _LEGACY_DEMO_TYPES:
        return {DEMO_NAMESPACE}
    return _namespaces_from_nodesets(_nodeset_names(props.get("belongs_to_set")))


def effective_namespace(props: Dict[str, Any]) -> Optional[str]:
    """The single namespace a node belongs to, or None when it has none or several."""
    found = node_namespaces(props)
    return next(iter(found)) if len(found) == 1 else None


def in_namespace(props: Dict[str, Any], allowed: Optional[Set[str]]) -> bool:
    """Fail closed: readable only when the caller may read *every* namespace the node
    belongs to, since a shared or unattributed node may hold any of those tenants' content."""
    found = node_namespaces(props)
    if not found:
        return False
    return found <= (allowed or {DEMO_NAMESPACE})


async def _load_graph_memories(namespaces: Optional[Set[str]] = None) -> Dict[str, Dict[str, Any]]:
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
            if in_namespace(props, namespaces):
                out[str(nid)] = _coerce_record(nid, props)
    return out


async def _vector_rank(query: str, top_k: int) -> List[str]:
    """Node ids ordered by vector relevance to the query (best effort)."""
    try:
        from cognee.infrastructure.databases.vector import get_vector_engine

        engine = get_vector_engine()  # sync factory -> handle
        results = engine.search(
            collection_name=MEMORY_COLLECTION, query_text=query, limit=top_k, include_payload=False
        )
        if inspect.isawaitable(results):
            results = await results
    except Exception as exc:
        # Fail closed: an unavailable index must not turn into an unranked dump
        # of every memory. Log the exception type only - the query and vector
        # payloads may contain secrets (project invariant 1).
        logger.warning(
            "vector search failed during recall (%s); returning no candidates",
            type(exc).__name__,
        )
        return []
    return [str(getattr(r, "id", "")) for r in (results or [])]


async def recall_memory_candidates(
    query: str,
    *,
    top_k: int = 12,
    namespaces: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    configure_cognee()
    namespaces = {"demo"} if namespaces is None else namespaces
    graph_mems = await _load_graph_memories(namespaces)
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
    if not ordered:
        # No vector hit means we have no relevance signal at all. Returning the
        # whole graph here handed the caller (and the LLM contradiction check)
        # up to _MAX_CLUSTER unrelated memories whenever the index was empty or
        # unhealthy. Fail closed instead.
        return []
    subjects = {(rec.get("subject") or "").strip().lower() for rec in ordered if (rec.get("subject") or "").strip()}
    for nid, rec in graph_mems.items():
        if nid in seen:
            continue
        subj = (rec.get("subject") or "").strip().lower()
        if subj and subj in subjects:
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
        return redact_text(" ".join(str(x) for x in results) if results else "")
    return redact_text(str(results))
