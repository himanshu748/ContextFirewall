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


DEFAULT_MAX_PACK_CHARS = 12_000
DEFAULT_MAX_PACK_ITEMS = 12


def _safe_markdown_inline(value: object) -> str:
    """Keep untrusted memory content on one Markdown line, as literal text."""
    flat = " ".join(str(value or "").split())
    # Neutralize embedded HTML and inline Markdown delimiters without losing content.
    flat = flat.replace("\\", "\\\\").replace("<", "&lt;").replace(">", "&gt;")
    for marker in ("`", "*", "_", "[", "]"):
        flat = flat.replace(marker, "\\" + marker)
    if flat.startswith(("#", "-", "+", "!", "|")):
        flat = "\\" + flat
    return flat


def _render_pack(
    query: str, included: List[Dict[str, Any]], approved_count: int,
    excluded_count: int, omitted_count: int,
) -> str:
    lines: List[str] = ["# Trusted context pack", f"_Task: {_safe_markdown_inline(query)}_", ""]
    if not included:
        lines.append("_No memories included in this pack._")
    else:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for mem in included:
            grouped.setdefault(str(mem.get("kind") or "fact"), []).append(mem)
        for kind in _KIND_ORDER + [k for k in grouped if k not in _KIND_ORDER]:
            items = grouped.get(kind)
            if not items:
                continue
            lines.append(f"## {_safe_markdown_inline(_KIND_TITLES.get(kind, kind.title()))}")
            for mem in items:
                trust = float(mem.get("trust_score", 0))
                stamp = (
                    f" _(as of {_safe_markdown_inline(mem['created_at'])})_"
                    if mem.get("created_at") else ""
                )
                lines.append(
                    f"- {_safe_markdown_inline(mem.get('text'))}{stamp}  ·  trust {trust:.2f}"
                )
            lines.append("")
    lines.append("---")
    lines.append(
        f"_ContextFirewall: {approved_count} approved, "
        f"{excluded_count} blocked before reaching the agent._"
    )
    if omitted_count:
        lines.append(
            f"_Pack limit: {omitted_count} approved "
            f"memories omitted to stay within the output budget._"
        )
    return "\n".join(lines).strip()


def build_pack_markdown(
    query: str,
    included: List[Dict[str, Any]],
    excluded_count: int,
    *,
    max_chars: int = DEFAULT_MAX_PACK_CHARS,
    max_items: int = DEFAULT_MAX_PACK_ITEMS,
) -> str:
    """Render the highest-trust approved memories within item and character budgets."""
    if max_chars < 1 or max_items < 0:
        raise ValueError("max_chars must be positive and max_items nonnegative")
    selected = sorted(
        included, key=lambda mem: -float(mem.get("trust_score", 0))
    )[:max_items]
    while True:
        result = _render_pack(
            query, selected, len(included), excluded_count, len(included) - len(selected)
        )
        if len(result) <= max_chars:
            return result
        if not selected:
            # An exceptionally tiny caller-supplied budget cannot fit even the
            # empty-pack metadata. Still honor the hard cap.
            return result[:max_chars]
        selected.pop()


def build_raw_recall(
    candidates: List[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_PACK_CHARS,
    max_items: int = DEFAULT_MAX_PACK_ITEMS,
) -> str:
    """Bounded ungoverned baseline, using the already-redacted recall content."""
    if max_chars < 1 or max_items < 0:
        raise ValueError("max_chars must be positive and max_items nonnegative")
    if not candidates:
        return "Raw recall returned no memories for this task."[:max_chars]
    lines = ["Raw recall returned memories without a firewall trust judgment:", ""]
    for candidate in candidates[:max_items]:
        content = _safe_markdown_inline(candidate.get("text"))
        if not content:
            continue
        proposal = "\n".join([*lines, f"• {content}"])
        if len(proposal) > max_chars:
            break
        lines.append(f"• {content}")
    return "\n".join(lines)[:max_chars]


async def build_pack(
    query: str,
    *,
    top_k: int = 12,
    use_llm: bool = True,
    include_baseline: bool = True,
    namespaces=None,
) -> Dict[str, Any]:
    audit = await audit_memories(query, top_k=top_k, use_llm=use_llm, namespaces=namespaces)
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
