"""ContextFirewall MCP server.

Puts the ContextFirewall memory firewall inside your coding agent. Any MCP client
(Claude Code, Cursor, Windsurf, Cline) can pull a trusted, governed context pack and
record session memories that future packs will audit on Cognee.

This server is a thin client over the existing ContextFirewall HTTP API. It changes
nothing about the backend; it just exposes the firewall as MCP tools over stdio.

Environment:
  CF_API_BASE      ContextFirewall API base URL.
                   Default: the public demo Space (good for a quick try of
                   get_trusted_context). For real use, run your own instance and point
                   here (local dev: http://localhost:8000) so your memories stay yours.
  CF_SESSION_FILE  Where record_event buffers the in-progress session.
                   Default: ~/.contextfirewall/session.json
  CF_HTTP_TIMEOUT  Request timeout in seconds. Default: 120
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

DEFAULT_BASE = "https://himanshukumarjha-contextfirewall.hf.space"


# --- configuration (read at call time so tests and clients can set env freely) ---
def _base() -> str:
    return os.environ.get("CF_API_BASE", DEFAULT_BASE).rstrip("/")


def _session_file() -> Path:
    return Path(os.environ.get("CF_SESSION_FILE", str(Path.home() / ".contextfirewall" / "session.json")))


def _timeout() -> float:
    return float(os.environ.get("CF_HTTP_TIMEOUT", "120"))


# --- HTTP helper (stdlib only, no extra dependencies) ---
def _api(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = _base() + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"content-type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"ContextFirewall {method} {path}: HTTP {exc.code} {body}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach ContextFirewall at {_base()}: {exc.reason}")


# --- local session buffer ---
def _new_session() -> Dict[str, Any]:
    return {
        "session_id": f"mcp-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}",
        "task": "",
        "agent": "mcp-client",
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": {},
        "events": [],
        "memories": [],
    }


def _load_session() -> Dict[str, Any]:
    path = _session_file()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return _new_session()


def _save_session(session: Dict[str, Any]) -> None:
    path = _session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2))


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
        return f"{header}\n(no trusted memories for this task yet)"
    return f"{header}\n\n{pack}"


def _impl_record_event(kind: str, content: str, subject: str = "") -> str:
    session = _load_session()
    n = len(session["events"]) + 1
    event = {
        "event_id": f"{session['session_id']}:e{n}",
        "kind": kind,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ordinal": n,
    }
    session["events"].append(event)
    note = "timeline event"
    if subject.strip():
        m = len(session["memories"]) + 1
        session["memories"].append(
            {
                "memory_id": f"{session['session_id']}:m{m}",
                "text": content,
                "kind": kind,
                "subject": subject.strip(),
                "created_at": datetime.now().strftime("%Y-%m-%d"),
                "evidence_event_ids": [event["event_id"]],
            }
        )
        note = f"timeline event + memory on '{subject.strip()}'"
    _save_session(session)
    return (
        f"Recorded {note}. Buffer now holds "
        f"{len(session['events'])} events and {len(session['memories'])} memories. "
        f"Call commit_session to persist into Cognee."
    )


def _impl_commit_session(task: str = "", repo: str = "", cognify: bool = True) -> str:
    session = _load_session()
    if not session["events"] and not session["memories"]:
        return "Nothing to commit: the session buffer is empty."
    if task.strip():
        session["task"] = task.strip()
    if not session.get("task"):
        session["task"] = "Agent session recorded via MCP"
    if repo.strip():
        session["repo"] = {"name": repo.strip()}
    resp = _api("POST", "/ingest", {"session": session, "cognify": bool(cognify)})
    _session_file().unlink(missing_ok=True)
    return (
        f"Committed session {session['session_id']}: "
        f"{resp.get('memories_created', '?')} memories, {resp.get('nodes_added', '?')} nodes added, "
        f"cognified={resp.get('cognified')}."
    )


def _impl_forget_memory(memory_id: str, reason: str = "rejected via MCP") -> str:
    resp = _api("POST", "/forget", {"memory_id": memory_id, "reason": reason})
    return f"{resp.get('status', '?')}: {resp.get('message', '')}"


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
def record_event(kind: str, content: str, subject: str = "") -> str:
    """Record a session event into the local ContextFirewall buffer.

    kind: one of prompt, tool_call, terminal, fix, decision, error, fact, lesson, config.
    content: the text of the event.
    subject: OPTIONAL. If set, the event is also stored as a durable MEMORY about
    `subject`. Memories are what a future get_trusted_context call audits. Leave blank
    for pure timeline events (used for session replay only).

    Events are buffered locally. Call commit_session to persist them into Cognee.
    """
    return _impl_record_event(kind, content, subject)


@mcp.tool()
def commit_session(task: str = "", repo: str = "", cognify: bool = True) -> str:
    """Persist the buffered session into Cognee (the remember verb).

    Sends the buffered events and memories to ContextFirewall and cognifies them so
    they enter the knowledge graph and become auditable by future trusted-context
    requests. Clears the local buffer afterward.
    """
    return _impl_commit_session(task, repo, cognify)


@mcp.tool()
def forget_memory(memory_id: str, reason: str = "rejected via MCP") -> str:
    """Governance (the forget verb): delete a memory from Cognee (graph and vector) so
    it can never resurface in recall or a future trusted pack."""
    return _impl_forget_memory(memory_id, reason)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
