"""Build the trusted context pack — only firewall-approved memories reach the agent.

The pack is what ContextFirewall hands the next agent. For the demo we also return
the *ungoverned baseline*: the raw set of memories a plain recall surfaces for the
same task (stale, contradicted, leaked and unsupported items included), so the UI
can contrast "what the agent would have gotten" vs. "what the firewall let through".

The baseline is assembled from the exact candidates the firewall audited (the real
ungoverned recall), using their already-redacted text so a leaked credential is
never re-exposed.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.firewall.audit import audit_memories

_KIND_TITLES = {
    "command": "Commands",
    "config": "Configuration",
    "fact": "Facts",
    "lesson": "Lessons",
    "decision": "Decisions",
    "credential": "Credentials",
}
_KIND_ORDER = ["command", "config", "decision", "lesson", "fact", "credential"]


def build_pack_markdown(query: str, included: List[Dict[str, Any]], excluded_count: int) -> str:
    lines: List[str] = ["# Trusted context pack", f"_Task: {query}_", ""]
    if not included:
        lines.append("_No memories passed the firewall for this task._")
    else:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for mem in included:
            grouped.setdefault(mem.get("kind", "fact"), []).append(mem)
        for kind in _KIND_ORDER + [k for k in grouped if k not in _KIND_ORDER]:
            items = grouped.get(kind)
            if not items:
                continue
            lines.append(f"## {_KIND_TITLES.get(kind, kind.title())}")
            for mem in sorted(items, key=lambda m: -float(m.get("trust_score", 0))):
                trust = float(mem.get("trust_score", 0))
                stamp = f" _(as of {mem['created_at']})_" if mem.get("created_at") else ""
                lines.append(f"- {mem.get('text', '').strip()}{stamp}  ·  trust {trust:.2f}")
            lines.append("")
    lines.append("---")
    passed = len(included)
    lines.append(
        f"_ContextFirewall: {passed} mem{'ory' if passed == 1 else 'ories'} approved, "
        f"{excluded_count} blocked before reaching the agent._"
    )
    return "\n".join(lines).strip()


def build_raw_recall(candidates: List[Dict[str, Any]]) -> str:
    """The ungoverned baseline: every recalled memory, unaudited and unfiltered.

    This is exactly what a flat recall hands the next agent. Text is the firewall's
    already-redacted form, so a leaked credential is never re-exposed in the baseline.
    """
    if not candidates:
        return "Raw recall returned no memories for this task."
    lines = ["Raw recall returns every memory it finds for this task, with no trust judgment:", ""]
    for c in candidates[:12]:
        text = (c.get("text") or "").strip()
        if text:
            lines.append(f"• {text}")
    lines += [
        "",
        "A flat vector store hands all of these to the next agent, including the stale deploy "
        "command, the contradicted claim, the leaked credential, and the unsupported number.",
    ]
    return "\n".join(lines)


async def build_pack(
    query: str,
    *,
    top_k: int = 12,
    use_llm: bool = True,
    include_baseline: bool = True,
) -> Dict[str, Any]:
    audit = await audit_memories(query, top_k=top_k, use_llm=use_llm)
    included = [v for v in audit["candidates"] if v["passed"]]
    excluded = [
        {"memory_id": v["memory_id"], "reason": v["block_reason"] or "", "check": v["block_check"] or ""}
        for v in audit["candidates"]
        if not v["passed"]
    ]
    pack_md = build_pack_markdown(query, included, len(excluded))
    baseline = build_raw_recall(audit["candidates"]) if include_baseline else None
    return {
        "query": query,
        "pack_markdown": pack_md,
        "included": [v["memory_id"] for v in included],
        "excluded": excluded,
        "recall_answer": baseline,
        "audit": audit,
    }
