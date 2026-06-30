"""ContextFirewall MCP server (hosted, streamable HTTP).

This is the headline surface of ContextFirewall: it puts the memory firewall
*inside the coding agent*. Any MCP client (Claude Code, Cursor, Windsurf, Cline, or
a generic MCP client) connects to one endpoint and gets a governed memory layer
where every operation flows through Cognee and the four firewall checks.

Unlike the local stdio package under ``mcp/`` (a thin HTTP proxy for laptops), this
server is mounted directly on the FastAPI app and calls the firewall/Cognee core
in-process, so it is the lowest-latency, fullest-fidelity path. Both transports
expose the *same six tools* so the docs and the agent experience are identical:

    get_trusted_context   recall + audit -> a trusted context pack   (Cognee: recall)
    audit_context         recall + audit -> per-memory verdicts       (Cognee: recall)
    remember              store one durable, auditable memory         (Cognee: remember)
    forget_memory         delete a memory from graph + vector         (Cognee: forget)
    improve_rules         distil reusable coding rules (memify)        (Cognee: improve)
    list_coding_rules     retrieve the distilled rules                 (Cognee: recall)

The server is stateless (``stateless_http=True``) so it scales as a public,
multi-client endpoint with no per-session server state.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.cognee_runtime.forget import forget_memory as _forget_memory
from app.cognee_runtime.improve import improve as _improve, recall_rules as _recall_rules
from app.cognee_runtime.ingest import remember_fact as _remember_fact
from app.firewall.audit import audit_memories as _audit_memories
from app.firewall.pack import build_pack as _build_pack

INSTRUCTIONS = (
    "ContextFirewall is a trust firewall for an AI coding agent's long-term memory, "
    "built on Cognee. Call get_trusted_context BEFORE acting on a task to receive only "
    "memory that passes four checks (staleness, contradiction, secret, evidence); call "
    "audit_context to see what was blocked and why; remember durable facts as you learn "
    "them; forget_memory to retract a bad one; improve_rules / list_coding_rules to work "
    "with distilled coding rules. Stale, contradicted, secret-bearing, and unsupported "
    "memory never reaches you."
)

cf_mcp = FastMCP(
    "contextfirewall",
    instructions=INSTRUCTIONS,
    stateless_http=True,
    # Return tool results as plain JSON (not an SSE stream): simplest and most
    # proxy-friendly path through the Hugging Face Space edge.
    json_response=True,
    streamable_http_path="/",
    # This is a public, intentionally-shared endpoint. DNS-rebinding Host/Origin
    # validation (meant to protect a localhost MCP server from malicious web pages)
    # would otherwise reject the Space's public host with 421 "Invalid Host header".
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _pack_header(audit: Dict[str, Any], base_note: str = "") -> str:
    return (
        f"<!-- ContextFirewall: {audit.get('passed_count', '?')} approved, "
        f"{audit.get('blocked_count', '?')} blocked for this task{base_note} -->"
    )


@cf_mcp.tool()
async def get_trusted_context(task: str, top_k: int = 12) -> str:
    """Return a TRUSTED context pack for a task, governed by ContextFirewall.

    Only memories that pass all four audit checks (staleness, contradiction, secret,
    evidence) are included. Stale, contradicted, secret-bearing, and unsupported
    memories are withheld. Call this BEFORE acting on a task to get governed context
    instead of raw, ungoverned recall.
    """
    result = await _build_pack(task, top_k=int(top_k), namespaces={"demo", "public"})
    audit = result.get("audit") or {}
    pack = (result.get("pack_markdown") or "").strip()
    header = _pack_header(audit)
    if not pack:
        return f"{header}\n(no trusted memories passed the firewall for this task yet)"
    return f"{header}\n\n{pack}"


@cf_mcp.tool()
async def audit_context(task: str, top_k: int = 12) -> str:
    """Show the firewall's per-memory verdicts for a task (the transparency view).

    Returns which recalled memories were APPROVED and which were BLOCKED, with the
    failing check and a plain-language reason for each block, plus the memory_id you
    can pass to forget_memory. Use this to explain to a human *why* a memory was
    withheld, or to decide what to retract.
    """
    audit = await _audit_memories(task, top_k=int(top_k), namespaces={"demo", "public"})
    cands: List[Dict[str, Any]] = audit.get("candidates", [])
    approved = [c for c in cands if c.get("passed")]
    blocked = [c for c in cands if not c.get("passed")]
    lines = [
        f"ContextFirewall audit for: {task}",
        f"{audit.get('passed_count', 0)} approved, {audit.get('blocked_count', 0)} blocked.",
        "",
        "BLOCKED:",
    ]
    if blocked:
        for c in blocked:
            lines.append(
                f"  - [{c.get('block_check')}] {c.get('memory_id')} "
                f"(trust {float(c.get('trust_score', 0)):.2f}): {c.get('block_reason')}"
            )
    else:
        lines.append("  (none)")
    lines += ["", "APPROVED:"]
    if approved:
        for c in approved:
            txt = (c.get("text") or "").strip().replace("\n", " ")
            txt = txt if len(txt) <= 90 else txt[:89] + "…"
            lines.append(f"  - {c.get('memory_id')} (trust {float(c.get('trust_score', 0)):.2f}): {txt}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


@cf_mcp.tool()
async def remember(text: str, subject: str = "", kind: str = "fact") -> str:
    """Remember a durable fact so future trusted-context requests can audit it (Cognee remember).

    text: the thing to remember (a command, decision, lesson, config value, or fact).
    subject: OPTIONAL but recommended — what the memory is about (e.g. "deploy command").
        A subject lets the firewall detect staleness and contradiction against peers
        on the same subject later.
    kind: one of fact, decision, lesson, command, config, credential.

    Secrets are redacted at ingest, so a credential is never stored and will be
    blocked on the next audit. Returns the new memory_id.
    """
    res = await _remember_fact(text, subject=subject or None, kind=kind, namespace="public")
    subj = f" on '{res['subject']}'" if res.get("subject") else ""
    return (
        f"Remembered {kind}{subj} as {res['memory_id']}. It is now in Cognee and will be "
        f"audited by the firewall on the next get_trusted_context call."
    )


@cf_mcp.tool()
async def forget_memory(memory_id: str, reason: str = "rejected via MCP") -> str:
    """Governance (Cognee forget): delete a memory from the graph and vector store so it
    can never resurface in recall or a future trusted context pack."""
    res = await _forget_memory(memory_id, reason=reason, allowed_namespaces={"public"}, allow_demo=False)
    return f"{res.get('status', '?')}: {res.get('message', '')}"


@cf_mcp.tool()
async def improve_rules() -> str:
    """Distil durable, reusable coding rules from the recorded sessions (Cognee improve / memify).

    Runs Cognee's coding-rule-association task over the stored session transcript to
    mint higher-order Rule nodes, then returns the current rule set. This is memory
    that improves itself: raw events become reusable guidance.
    """
    res = await _improve()
    summary = res.get("message", "")
    total = res.get("rules_total")
    added = res.get("rules_added")
    rules_text = (await _recall_rules()).strip()
    head = f"{summary} (total rules: {total}, added: {added})."
    return f"{head}\n\n{rules_text}" if rules_text else head


@cf_mcp.tool()
async def list_coding_rules(query: str = "What coding rules apply when working in this repo?") -> str:
    """Retrieve the distilled coding rules from Cognee (CODING_RULES search)."""
    text = (await _recall_rules(query)).strip()
    return text or "No coding rules have been distilled yet. Call improve_rules first."


# Build the streamable-HTTP ASGI app once (this also creates the session manager,
# which the FastAPI lifespan must run). Mounted at /mcp by app.main.
mcp_http_app = cf_mcp.streamable_http_app()
