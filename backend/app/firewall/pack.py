"""Build the trusted context pack: only firewall-approved memories reach the agent.

The pack is what ContextFirewall hands the next agent. For the demo we also return
the *ungoverned baseline*: the raw set of memories a plain recall surfaces for the
same task (stale, contradicted, leaked and unsupported items included), so the UI
can contrast "what the agent would have gotten" vs. "what the firewall let through".

The baseline is assembled from the exact candidates the firewall audited (the real
ungoverned recall), using their already-redacted text so a leaked credential is
never re-exposed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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

DEFAULT_MAX_ITEMS = 25
DEFAULT_MAX_CHARS = 4000

_MD_CONTROL_CHARS = ("#", "-", "*", "+", ">", "`", "~")
_CHECK_LABELS = {
    "staleness": "stale",
    "contradiction": "contradicted",
    "secret": "secret-bearing",
    "evidence": "unsupported",
}


def _sanitize_inline_text(value: Optional[str]) -> str:
    """Flatten text to a single line and escape leading Markdown control tokens."""
    flat = re.sub(r"[\r\n\t]+", " ", (value or "")).strip()
    if not flat:
        return ""
    # Escape any Markdown heading/list/blockquote/fence triggers at the start of
    # the flattened string or immediately following whitespace.
    flat = re.sub(r"(^|\s)([#>*+`~-])", r"\1\\\2", flat)
    return flat


def build_pack_markdown(
    query: str,
    included: List[Dict[str, Any]],
    excluded_count: int,
    *,
    max_items: Optional[int] = DEFAULT_MAX_ITEMS,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
) -> str:
    safe_query = _sanitize_inline_text(query)
    lines: List[str] = ["# Trusted context pack", f"_Task: {safe_query}_", ""]

    budgeted = list(included)
    if max_items is not None and max_items >= 0:
        budgeted = sorted(
            budgeted,
            key=lambda m: (-float(m.get("trust_score", 0) or 0), str(m.get("memory_id", ""))),
        )[:max_items]

    if max_chars is not None and max_chars > 0:
        ranked = sorted(
            budgeted,
            key=lambda m: (-float(m.get("trust_score", 0) or 0), str(m.get("memory_id", ""))),
        )
        kept: List[Dict[str, Any]] = []
        used_chars = 0
        for mem in ranked:
            sanitized = _sanitize_inline_text(mem.get("text", ""))
            stamp = f" _(as of {_sanitize_inline_text(str(mem['created_at']))})_" if mem.get("created_at") else ""
            item_len = len(f"- {sanitized}{stamp}  ·  trust 0.00\n")
            if kept and used_chars + item_len > max_chars:
                continue
            if not kept and item_len > max_chars:
                # Truncate a single oversized item so it still fits the char budget
                avail = max(16, max_chars - len(f"- {stamp}  ·  trust 0.00\n") - 1)
                mem = dict(mem, text=sanitized[:avail] + "…")
                item_len = max_chars
            kept.append(mem)
            used_chars += item_len
        budgeted = kept

    if not budgeted:
        lines.append("_No memories passed the firewall for this task._")
    else:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for mem in budgeted:
            grouped.setdefault(mem.get("kind", "fact"), []).append(mem)
        for kind in _KIND_ORDER + [k for k in grouped if k not in _KIND_ORDER]:
            items = grouped.get(kind)
            if not items:
                continue
            lines.append(f"## {_KIND_TITLES.get(kind, kind.title())}")
            for mem in sorted(items, key=lambda m: -float(m.get("trust_score", 0) or 0)):
                trust = float(mem.get("trust_score", 0) or 0)
                stamp = (
                    f" _(as of {_sanitize_inline_text(str(mem['created_at']))})_"
                    if mem.get("created_at")
                    else ""
                )
                safe_text = _sanitize_inline_text(mem.get("text", ""))
                lines.append(f"- {safe_text}{stamp}  ·  trust {trust:.2f}")
            lines.append("")
    lines.append("---")
    passed = len(budgeted)
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
        text = _sanitize_inline_text(c.get("text"))
        if text:
            lines.append(f"• {text}")

    blocked_counts: Dict[str, int] = {}
    for c in candidates:
        if c.get("passed") is False:
            chk = str(c.get("block_check") or "blocked")
            blocked_counts[chk] = blocked_counts.get(chk, 0) + 1

    if blocked_counts:
        parts = [
            f"{count} {_CHECK_LABELS.get(chk, chk)}"
            for chk, count in blocked_counts.items()
        ]
        summary = ", ".join(parts)
        lines += [
            "",
            f"A flat vector store hands all of these to the next agent, including {summary}.",
        ]
    return "\n".join(lines)


async def build_pack(
    query: str,
    *,
    top_k: int = 12,
    use_llm: bool = True,
    include_baseline: bool = True,
    namespaces=None,
    max_items: Optional[int] = DEFAULT_MAX_ITEMS,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
) -> Dict[str, Any]:
    audit = await audit_memories(query, top_k=top_k, use_llm=use_llm, namespaces=namespaces)
    included = [v for v in audit["candidates"] if v["passed"]]
    excluded = [
        {"memory_id": v["memory_id"], "reason": v["block_reason"] or "", "check": v["block_check"] or ""}
        for v in audit["candidates"]
        if not v["passed"]
    ]
    pack_md = build_pack_markdown(
        query,
        included,
        len(excluded),
        max_items=max_items,
        max_chars=max_chars,
    )
    baseline = build_raw_recall(audit["candidates"]) if include_baseline else None
    return {
        "query": query,
        "pack_markdown": pack_md,
        "included": [v["memory_id"] for v in included],
        "excluded": excluded,
        "recall_answer": baseline,
        "audit": audit,
    }
