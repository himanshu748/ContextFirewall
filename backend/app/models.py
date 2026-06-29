"""Pydantic request/response models — the ContextFirewall API contract.

Kept separate from the cognee runtime so the frontend's types and the API surface
have one source of truth. No secrets ever appear here: memory text is redacted
before it leaves the firewall.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

CheckName = str  # "staleness" | "contradiction" | "secret" | "evidence"


# --- health -------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    profile: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)


# --- ingest (remember) --------------------------------------------------------
class RecordedEvent(BaseModel):
    kind: str
    content: str
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    ordinal: Optional[int] = None


class RecordedSession(BaseModel):
    session_id: str
    task: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    repo: dict[str, Any] = Field(default_factory=dict)
    events: List[RecordedEvent] = Field(default_factory=list)
    # Optional pre-distilled candidate memories (else they are derived at ingest).
    memories: Optional[List[dict[str, Any]]] = None


class IngestRequest(BaseModel):
    session: RecordedSession
    cognify: bool = True  # also build the LLM entity graph (slower, richer recall)


class IngestResponse(BaseModel):
    session_id: str
    nodes_added: int
    memories_created: int
    cognified: bool
    message: str


# --- audit (recall + the four checks) -----------------------------------------
class CheckResult(BaseModel):
    check: CheckName
    passed: bool
    reason: str
    severity: str = "info"  # info | warn | block


class MemoryVerdict(BaseModel):
    memory_id: str
    text: str  # redacted if it contained a secret
    kind: str
    subject: Optional[str] = None
    created_at: Optional[str] = None
    trust_score: float = 0.0
    status: str = "candidate"
    source_session_id: Optional[str] = None
    passed: bool
    checks: List[CheckResult] = Field(default_factory=list)
    block_reason: Optional[str] = None
    block_check: Optional[CheckName] = None


class AuditRequest(BaseModel):
    query: str = Field(..., description="Task/context the next agent needs memory for")
    top_k: int = 12


class AuditResponse(BaseModel):
    query: str
    candidates: List[MemoryVerdict] = Field(default_factory=list)
    passed_count: int = 0
    blocked_count: int = 0


# --- trusted context pack -----------------------------------------------------
class ExcludedMemory(BaseModel):
    memory_id: str
    reason: str
    check: CheckName


class PackRequest(BaseModel):
    query: str
    top_k: int = 12


class PackResponse(BaseModel):
    query: str
    pack_markdown: str
    included: List[str] = Field(default_factory=list)
    excluded: List[ExcludedMemory] = Field(default_factory=list)
    recall_answer: Optional[str] = None  # raw cognee GRAPH_COMPLETION, for comparison


# --- forget (governance) ------------------------------------------------------
class ForgetRequest(BaseModel):
    memory_id: str
    reason: Optional[str] = None


class ForgetResponse(BaseModel):
    memory_id: str
    status: str
    message: str


# --- graph view ---------------------------------------------------------------
class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class GraphResponse(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


# --- replay timeline ----------------------------------------------------------
class TimelineEvent(BaseModel):
    event_id: str
    kind: str
    content: str
    timestamp: Optional[str] = None
    ordinal: int = 0


class SessionSummary(BaseModel):
    session_id: str
    task: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    repo: dict[str, Any] = Field(default_factory=dict)
    event_count: int = 0


class TimelineResponse(BaseModel):
    session: SessionSummary
    events: List[TimelineEvent] = Field(default_factory=list)
