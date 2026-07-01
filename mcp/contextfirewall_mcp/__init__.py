"""ContextFirewall MCP server (local stdio).

Puts the ContextFirewall memory firewall inside your coding agent. Any MCP client
(Claude Code, Cursor, Windsurf, Cline, Claude Desktop) can pull a trusted, governed context pack and
record session memories that future packs will audit on Cognee.

This server is a thin, zero-dependency client over the ContextFirewall HTTP API, so it
runs anywhere uvx/uv can and needs nothing but the standard library plus `mcp`. It
exposes the SAME six tools as the hosted streamable-HTTP endpoint (mounted at /mcp on
the backend), so the agent experience and the docs are identical across transports:

    get_trusted_context   recall + audit -> a trusted context pack   (Cognee: recall)
    audit_context         recall + audit -> per-memory verdicts        (Cognee: recall)
    remember              store one durable, auditable memory          (Cognee: remember)
    forget_memory         delete a memory from graph + vector          (Cognee: forget)
    improve_rules         distil reusable coding rules (memify)         (Cognee: improve)
    list_coding_rules     retrieve the distilled rules                  (Cognee: recall)

Environment:
  CF_API_BASE      ContextFirewall API base URL.
                   Default: the public demo Space (good for a quick try). For real use,
                   run your own instance and point here (local dev: http://localhost:8000)
                   so your memories stay yours.
  CF_API_KEY       ContextFirewall API key (cf_live_...). Sent as an Authorization
                   bearer token so reads/writes are scoped to your private namespace.
                   Optional: without it the server talks to the read-only demo.
  CF_HTTP_TIMEOUT  Request timeout in seconds. Default: 120
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

DEFAULT_BASE = "https://himanshukumarjha-contextfirewall.hf.space"


# --- configuration (read at call time so tests and clients can set env freely) ---
def _base() -> str:
    return os.environ.get("CF_API_BASE", DEFAULT_BASE).rstrip("/")


def _timeout() -> float:
    try:
        return float(os.environ.get("CF_HTTP_TIMEOUT", "120"))
    except ValueError:
        return 120.0


def _api_key() -> str:
    return os.environ.get("CF_API_KEY", "").strip()


# --- HTTP helper (stdlib only, no extra dependencies) ---
def _api(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = _base() + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"content-type": "application/json"} if data is not None else {}
    key = _api_key()
    if key:
        headers["authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"ContextFirewall {method} {path}: HTTP {exc.code} {body}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach ContextFirewall at {_base()}: {exc.reason}")


def _short(text: str, n: int = 90) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


# --- tool implementations (plain functions, directly unit-testable) ---
def _impl_get_trusted_context(task: str, top_k: int = 12) -> str:
    resp = _api("POST", "/pack", {"query": task, "top_k": int(top_k)})
    audit = resp.get("audit") or {}
    pack = (resp.get("pack_markdown") or "").strip()
    header = (
        f"<!-- ContextFirewall ({_base()}): "
        f"{audit.get('passed_count', '?')} approved, {audit.get('blocked_count', '?')} blocked for this task -->"
    )
    if not pack:
        return f"{header}\n(no trusted memories passed the firewall for this task yet)"
    return f"{header}\n\n{pack}"


def _impl_audit_context(task: str, top_k: int = 12) -> str:
    audit = _api("POST", "/audit", {"query": task, "top_k": int(top_k)})
    cands: List[Dict[str, Any]] = audit.get("candidates", [])
    approved = [c for c in cands if c.get("passed")]
    blocked = [c for c in cands if not c.get("passed")]
    lines = [
        f"ContextFirewall audit for: {task}",
        f"{audit.get('passed_count', 0)} approved, {audit.get('blocked_count', 0)} blocked.",
        "",
        "BLOCKED:",
    ]
    lines += (
        [
            f"  - [{c.get('block_check')}] {c.get('memory_id')} "
            f"(trust {float(c.get('trust_score', 0)):.2f}): {c.get('block_reason')}"
            for c in blocked
        ]
        if blocked
        else ["  (none)"]
    )
    lines += ["", "APPROVED:"]
    lines += (
        [f"  - {c.get('memory_id')} (trust {float(c.get('trust_score', 0)):.2f}): {_short(c.get('text'))}" for c in approved]
        if approved
        else ["  (none)"]
    )
    return "\n".join(lines)


def _impl_remember(text: str, subject: str = "", kind: str = "fact") -> str:
    resp = _api("POST", "/remember", {"text": text, "subject": subject or None, "kind": kind})
    subj = f" on '{resp.get('subject')}'" if resp.get("subject") else ""
    return (
        f"Remembered {kind}{subj} as {resp.get('memory_id')}. It is now in Cognee and will be "
        f"audited by the firewall on the next get_trusted_context call."
    )


def _impl_forget_memory(memory_id: str, reason: str = "rejected via MCP") -> str:
    resp = _api("POST", "/forget", {"memory_id": memory_id, "reason": reason})
    return f"{resp.get('status', '?')}: {resp.get('message', '')}"


def _impl_improve_rules() -> str:
    res = _api("POST", "/improve")
    head = f"{res.get('message', '')} (total rules: {res.get('rules_total')}, added: {res.get('rules_added')})."
    rules = _api("GET", "/rules").get("rules", "")
    rules = (rules or "").strip()
    return f"{head}\n\n{rules}" if rules else head


def _impl_list_coding_rules(query: str = "What coding rules apply when working in this repo?") -> str:
    path = "/rules?" + urllib.parse.urlencode({"query": query})
    text = (_api("GET", path).get("rules") or "").strip()
    return text or "No coding rules have been distilled yet. Call improve_rules first."


# --- MCP server ---
mcp = FastMCP("contextfirewall")


@mcp.tool()
def get_trusted_context(task: str, top_k: int = 12) -> str:
    """Return a TRUSTED context pack for a task, governed by ContextFirewall.

    Only memories that pass all four audit checks (staleness, contradiction, secret,
    evidence) are included. Stale, contradicted, secret-bearing, and unsupported
    memories are withheld. Call this BEFORE acting on a task to get governed context
    instead of raw, ungoverned recall.
    """
    return _impl_get_trusted_context(task, top_k)


@mcp.tool()
def audit_context(task: str, top_k: int = 12) -> str:
    """Show the firewall's per-memory verdicts for a task (the transparency view).

    Returns which recalled memories were APPROVED and which were BLOCKED, with the
    failing check and a plain-language reason for each block, plus the memory_id you
    can pass to forget_memory.
    """
    return _impl_audit_context(task, top_k)


@mcp.tool()
def remember(text: str, subject: str = "", kind: str = "fact") -> str:
    """Remember a durable fact so future trusted-context requests can audit it (Cognee remember).

    text: the thing to remember (a command, decision, lesson, config value, or fact).
    subject: OPTIONAL but recommended — what the memory is about (e.g. "deploy command");
    a subject lets the firewall detect staleness and contradiction against peers later.
    kind: one of fact, decision, lesson, command, config, credential.

    Secrets are redacted at ingest, so a credential is never stored and will be blocked
    on the next audit. Returns the new memory_id.
    """
    return _impl_remember(text, subject, kind)


@mcp.tool()
def forget_memory(memory_id: str, reason: str = "rejected via MCP") -> str:
    """Governance (Cognee forget): delete a memory from the graph and vector store so
    it can never resurface in recall or a future trusted pack."""
    return _impl_forget_memory(memory_id, reason)


@mcp.tool()
def improve_rules() -> str:
    """Distil durable, reusable coding rules from the recorded sessions (Cognee improve / memify),
    then return the current rule set. Memory that improves itself: raw events become guidance."""
    return _impl_improve_rules()


@mcp.tool()
def list_coding_rules(query: str = "What coding rules apply when working in this repo?") -> str:
    """Retrieve the distilled coding rules from Cognee (CODING_RULES search)."""
    return _impl_list_coding_rules(query)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
