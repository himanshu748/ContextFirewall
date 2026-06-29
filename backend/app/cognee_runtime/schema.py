"""Typed Cognee knowledge-graph schema for ContextFirewall.

Declaring a typed ``DataPoint`` schema (instead of letting the LLM invent node
shapes) is the single biggest lever on graph quality — and it makes the firewall
deterministic: every candidate ``Memory`` carries the exact metadata the four
audit checks need (created_at, trust_score, subject, evidence, supersedes edge).

Graph shape (nested DataPoint fields become typed edges):

    Repo
     ▲ repo
    AgentSession ◀── session ── SessionEvent
     ▲ source_session                       ▲ derived_from
    Memory ── supersedes ▶ Memory           │
       └──────────────── evidence ──────────┘

Two population paths are used together by the ingest pipeline:
  1. ``add_data_points([...])`` — insert these typed nodes/edges directly (no LLM),
     giving the firewall precise Memory objects + a clean replay timeline.
  2. ``cognify(...)`` over the rendered session text — lets the LLM grow the rich
     entity web that powers GRAPH_COMPLETION / TEMPORAL recall and the graph view.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import SkipValidation

from cognee.infrastructure.engine import DataPoint

# Memory lifecycle states (governance).
STATUS_CANDIDATE = "candidate"  # ingested, not yet audited
STATUS_APPROVED = "approved"    # passed the firewall / human-approved
STATUS_BLOCKED = "blocked"      # failed an audit check
STATUS_FORGOTTEN = "forgotten"  # removed via forget() governance

# Event kinds captured by the recorder.
EVENT_KINDS = ("prompt", "tool_call", "terminal", "file_change", "error", "fix", "decision")
# Memory kinds (volatility differs — commands/configs go stale fast).
MEMORY_KINDS = ("command", "config", "fact", "lesson", "decision", "credential")
VOLATILE_KINDS = ("command", "config")


class Repo(DataPoint):
    """A code repository an agent works in."""

    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    metadata: dict = {"index_fields": ["name", "description"]}


class AgentSession(DataPoint):
    """One recorded AI coding-agent working session against a repo."""

    session_id: str
    task: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    repo: SkipValidation[Any] = None  # -> Repo
    metadata: dict = {"index_fields": ["task"]}


class SessionEvent(DataPoint):
    """A single timeline event within a session (the flight-recorder track)."""

    event_id: str
    session_id: Optional[str] = None  # explicit property for robust timeline filtering
    kind: str  # one of EVENT_KINDS
    content: str
    timestamp: Optional[str] = None
    ordinal: int = 0
    session: SkipValidation[Any] = None  # -> AgentSession (typed edge)
    metadata: dict = {"index_fields": ["content"]}


class Memory(DataPoint):
    """A distilled claim that could be handed to the next agent — what the firewall audits."""

    memory_id: str
    text: str
    kind: str = "fact"  # one of MEMORY_KINDS
    subject: Optional[str] = None  # normalized topic key (e.g. "deploy command") for supersession
    created_at: Optional[str] = None
    trust_score: float = 0.5
    status: str = STATUS_CANDIDATE
    reinforcement_count: int = 1
    evidence_event_ids: List[str] = []
    source_session_id: Optional[str] = None
    supersedes: SkipValidation[Any] = None  # -> Memory (this memory replaces an older one)
    metadata: dict = {"index_fields": ["text"]}


class Rule(DataPoint):
    """A coding rule derived from sessions via the memify coding-rules pipeline."""

    rule_id: str
    text: str
    metadata: dict = {"index_fields": ["text"]}


def render_session_text(session: dict) -> str:
    """Render a recorded session into a compact transcript for ``cognify`` extraction.

    The recorded ``session`` is the same JSON the recorder emits (see data/sessions/).
    """
    lines: List[str] = []
    repo = session.get("repo", {})
    lines.append(f"Repository: {repo.get('name', 'unknown')} — {repo.get('description', '')}".rstrip(" —"))
    lines.append(f"Agent session: {session.get('task', '')} (session {session.get('session_id', '')})")
    if session.get("started_at"):
        lines.append(f"Started: {session['started_at']}")
    lines.append("")
    for ev in session.get("events", []):
        ts = ev.get("timestamp", "")
        stamp = f"[{ts}] " if ts else ""
        lines.append(f"{stamp}{ev.get('kind', 'event').upper()}: {ev.get('content', '').strip()}")
    return "\n".join(lines).strip()
