"""Improve (memify) — distil durable coding rules from the stored sessions.

This is the Cognee 'improve' verb. It runs Cognee's coding-rule-association task
over the recorded session transcript, minting typed Rule nodes under a per-tenant
``coding_agent_rules_<namespace>`` node set (retrievable via
``SearchType.CODING_RULES``) — higher-order, reusable knowledge derived from the
raw memories. Distillation and retrieval are both scoped to the caller's
namespace so one tenant's rules never leak into another's.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from app.firewall.secrets import redact_text

from .bootstrap import configure_cognee

RULES_NODESET = "coding_agent_rules"


def nodeset_for(namespace: str) -> str:
    """Per-tenant rules node set: rules distilled for one namespace live in
    ``coding_agent_rules_<namespace>`` so one tenant's rules never leak into
    another's recall."""
    return f"{RULES_NODESET}_{namespace or 'demo'}"


def _nodesets_to_search(namespaces: Optional[Set[str]]) -> list[str]:
    """Every rules node set the caller may read.

    One per readable namespace, plus the legacy unsuffixed set when the caller
    can read ``demo``: rules distilled before node sets became per-tenant were
    written to the global ``coding_agent_rules`` set, and that pre-existing
    content is demo/sample material — only operators could write back then.
    """
    ns = namespaces or {"demo"}
    names = [nodeset_for(n) for n in sorted(ns)]
    if "demo" in ns:
        names.append(RULES_NODESET)
    return names


async def _stored_transcript(namespaces: Optional[Set[str]] = None) -> str:
    """Reconstruct a transcript from the SessionEvents already in the graph."""
    from .graph import list_sessions, session_timeline

    lines = []
    for s in await list_sessions(namespaces=namespaces):
        for e in await session_timeline(s["session_id"], namespaces=namespaces):
            content = (e.get("content") or "").strip()
            if content:
                lines.append(f"{e.get('kind', 'event').upper()}: {content}")
    return "\n".join(lines)


async def improve(
    read_namespaces: Optional[Set[str]] = None,
    *,
    rules_namespace: str = "demo",
) -> Dict[str, Any]:
    """Distil rules from the sessions in ``read_namespaces`` into the node set
    of ``rules_namespace``.

    Read and write are separated on purpose: an API-key tenant improves their
    own sessions into their own node set, while the operator (admin token)
    reads the public sample sessions and writes the ``demo`` node set — the
    one anonymous console visitors recall from.
    """
    configure_cognee()
    from cognee.tasks.codingagents.coding_rule_associations import add_rule_associations

    from .graph import count_nodes

    transcript = await _stored_transcript(read_namespaces)
    if not transcript.strip():
        return {"status": "empty", "rules_total": 0, "rules_added": 0, "message": "No stored sessions to improve from."}

    nodeset = nodeset_for(rules_namespace)
    before = (await count_nodes()).get("Rule", 0)
    await add_rule_associations(data=transcript, rules_nodeset_name=nodeset)
    after = (await count_nodes()).get("Rule", 0)
    return {
        "status": "ok",
        "rules_total": after,
        "rules_added": max(0, after - before),
        "message": f"Distilled coding rules into the '{nodeset}' node set (Cognee memify / improve).",
    }


async def recall_rules(
    query: str = "What coding rules apply when working in this repo?",
    namespaces: Optional[Set[str]] = None,
) -> str:
    configure_cognee()
    import cognee
    from cognee import SearchType

    try:
        res = await cognee.search(
            query_text=query,
            query_type=SearchType.CODING_RULES,
            node_name=_nodesets_to_search(namespaces),
        )
    except Exception as exc:  # noqa: BLE001
        return f"(coding rules unavailable: {exc!r})"
    if isinstance(res, list):
        return redact_text(" ".join(str(x) for x in res) if res else "")
    return redact_text(str(res))
