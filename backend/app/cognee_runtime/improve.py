"""Improve (memify) — distil durable coding rules from the stored sessions.

This is the Cognee 'improve' verb. It runs Cognee's coding-rule-association task
over the recorded session transcript, minting typed Rule nodes under the
``coding_agent_rules`` node set (retrievable via ``SearchType.CODING_RULES``) —
higher-order, reusable knowledge derived from the raw memories.
"""
from __future__ import annotations

from typing import Any, Dict

from app.firewall.secrets import redact_text

from .bootstrap import configure_cognee

RULES_NODESET = "coding_agent_rules"


async def _stored_transcript() -> str:
    """Reconstruct a transcript from the SessionEvents already in the graph."""
    from .graph import list_sessions, session_timeline

    lines = []
    for s in await list_sessions(include_all=True):
        for e in await session_timeline(s["session_id"], include_all=True):
            content = (e.get("content") or "").strip()
            if content:
                lines.append(f"{e.get('kind', 'event').upper()}: {content}")
    return "\n".join(lines)


async def improve() -> Dict[str, Any]:
    configure_cognee()
    from cognee.tasks.codingagents.coding_rule_associations import add_rule_associations

    from .graph import count_nodes

    transcript = await _stored_transcript()
    if not transcript.strip():
        return {"status": "empty", "rules_total": 0, "message": "No stored sessions to improve from."}

    before = (await count_nodes()).get("Rule", 0)
    await add_rule_associations(data=transcript, rules_nodeset_name=RULES_NODESET)
    after = (await count_nodes()).get("Rule", 0)
    return {
        "status": "ok",
        "rules_total": after,
        "rules_added": max(0, after - before),
        "message": f"Distilled coding rules into the '{RULES_NODESET}' node set (Cognee memify / improve).",
    }


async def recall_rules(query: str = "What coding rules apply when working in this repo?") -> str:
    configure_cognee()
    import cognee
    from cognee import SearchType

    try:
        res = await cognee.search(query_text=query, query_type=SearchType.CODING_RULES)
    except Exception as exc:  # noqa: BLE001
        return f"(coding rules unavailable: {exc!r})"
    if isinstance(res, list):
        return redact_text(" ".join(str(x) for x in res) if res else "")
    return redact_text(str(res))
