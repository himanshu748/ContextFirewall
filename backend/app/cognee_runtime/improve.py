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


def _nodeset_for(namespaces: Optional[Set[str]]) -> str:
    """Per-tenant rules node set name for the caller's namespace.

    Mirrors ``in_namespace``'s default: an unscoped caller resolves to ``demo``.
    A single-namespace caller gets ``coding_agent_rules_<ns>``; a multi-namespace
    caller gets a stable, order-independent composite so the same set of
    namespaces always maps to the same node set.
    """
    if not namespaces:
        ns = "demo"
    elif len(namespaces) == 1:
        ns = next(iter(namespaces))
    else:
        ns = "+".join(sorted(namespaces))
    return f"{RULES_NODESET}_{ns}"


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


async def improve(namespaces: Optional[Set[str]] = None) -> Dict[str, Any]:
    configure_cognee()
    from cognee.tasks.codingagents.coding_rule_associations import add_rule_associations

    from .graph import count_nodes

    transcript = await _stored_transcript(namespaces)
    if not transcript.strip():
        return {"status": "empty", "rules_total": 0, "rules_added": 0, "message": "No stored sessions to improve from."}

    nodeset = _nodeset_for(namespaces)
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
            node_name=[_nodeset_for(namespaces)],
        )
    except Exception as exc:  # noqa: BLE001
        return f"(coding rules unavailable: {exc!r})"
    if isinstance(res, list):
        return redact_text(" ".join(str(x) for x in res) if res else "")
    return redact_text(str(res))
