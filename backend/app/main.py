"""ContextFirewall API: FastAPI surface over the Cognee-backed firewall engine.

Endpoints:
  GET  /health                      profile + node counts
  POST /ingest                      remember a recorded session
  POST /remember                    remember one durable fact (single-shot)
  POST /audit                       recall + run the 4 checks -> per-memory verdicts
  POST /pack                        gated trusted context pack (+ ungoverned baseline)
  POST /forget                      governance: delete a memory from Cognee
  POST /improve                     distil coding rules (Cognee memify / improve)
  GET  /rules                       retrieve distilled coding rules
  GET  /graph                       knowledge-graph nodes/edges for the viz
  GET  /sessions                    recorded sessions
  GET  /sessions/{id}/timeline      replay timeline for a session
  POST /demo/seed                   ingest the bundled sample session
  GET  /demo/queries                suggested demo queries
  ANY  /mcp                         MCP server (streamable HTTP): the six firewall tools

The same six MCP tools also ship as a local stdio package under ``mcp/``.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.activity import get_activity, log_activity
from app.cognee_runtime.bootstrap import configure_cognee
from app.cognee_runtime.forget import forget_memory
from app.cognee_runtime.graph import count_nodes, graph_view, list_sessions, session_timeline
from app.cognee_runtime.improve import improve as improve_memory, recall_rules
from app.cognee_runtime.ingest import hydrate_demo_secrets, ingest_session, remember_fact
from app.firewall.audit import audit_memories
from app.firewall.pack import build_pack
from app.mcp_server import cf_mcp, mcp_http_app
from app.models import (
    AuditRequest,
    AuditResponse,
    ForgetRequest,
    ForgetResponse,
    GraphResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    PackRequest,
    PackResponse,
    RememberRequest,
    RememberResponse,
    SessionSummary,
    TimelineResponse,
)

# data/ lives under backend/, not backend/app/, so resolve from the backend dir.
DEMO_SESSION = Path(__file__).resolve().parents[1] / "data" / "sessions" / "taskflow_onboarding.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure Cognee once on startup so the first request isn't cold.
    try:
        configure_cognee()
    except Exception:  # noqa: BLE001
        pass
    # Run the MCP streamable-HTTP session manager for the life of the app. The MCP
    # app is mounted at /mcp; mounted ASGI sub-apps do not get their lifespan run
    # automatically, so we drive the session manager here.
    async with cf_mcp.session_manager.run():
        yield


app = FastAPI(
    title="ContextFirewall API",
    description="Guardrails for the memory layer: a trust firewall for AI coding-agent memory, built on Cognee.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public demo API
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount the ContextFirewall MCP server (streamable HTTP) at /mcp. This is the
# headline surface: any MCP client (Claude Code, Cursor, Windsurf, ...) connects
# here to get a governed memory layer. The same six tools are also shipped as a
# local stdio package under mcp/ for laptops.
app.mount("/mcp", mcp_http_app)


@app.get("/")
async def root() -> dict:
    return {
        "name": "ContextFirewall",
        "tagline": "Guardrails for the memory layer.",
        "mcp_endpoint": "/mcp",
        "mcp_tools": [
            "get_trusted_context",
            "audit_context",
            "remember",
            "forget_memory",
            "improve_rules",
            "list_coding_rules",
        ],
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/remember", response_model=RememberResponse)
async def remember(req: RememberRequest) -> RememberResponse:
    """Remember one durable fact (the single-shot 'remember' verb the MCP server uses)."""
    try:
        res = await remember_fact(
            req.text,
            subject=req.subject,
            kind=req.kind,
            trust_score=req.trust_score,
            cognify=req.cognify,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Remember failed: {e}")
    subj = f" on '{res['subject']}'" if res.get("subject") else ""
    log_activity("api", "remember", f"stored {res['memory_id']}{subj}")
    return RememberResponse(
        memory_id=res["memory_id"],
        subject=res.get("subject"),
        kind=res["kind"],
        session_id=res["session_id"],
        cognified=res["cognified"],
        nodes_added=res["nodes_added"],
        message=f"Remembered {req.kind}{subj}. It is now auditable by the firewall.",
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    profile = configure_cognee()
    counts = await count_nodes()
    return HealthResponse(status="ok", profile=profile, counts=counts)


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    try:
        res = await ingest_session(req.session.model_dump(), cognify=req.cognify)
    except Exception as e:  # noqa: BLE001 (surface a clean message to the console)
        raise HTTPException(status_code=400, detail=f"Ingest failed: {e}")
    return IngestResponse(
        session_id=res["session_id"],
        nodes_added=res["nodes_added"],
        memories_created=res["memories_created"],
        cognified=res["cognified"],
        message=f"Remembered session '{res['session_id']}' into Cognee.",
    )


@app.post("/audit", response_model=AuditResponse)
async def audit(req: AuditRequest) -> AuditResponse:
    result = await audit_memories(req.query, top_k=req.top_k)
    log_activity("api", "audit", f"{result.get('passed_count', 0)} approved / {result.get('blocked_count', 0)} blocked · {req.query[:60]}")
    return AuditResponse(**result)


@app.post("/pack", response_model=PackResponse)
async def pack(req: PackRequest) -> PackResponse:
    result = await build_pack(req.query, top_k=req.top_k)
    _a = result.get("audit") or {}
    log_activity("api", "pack", f"{_a.get('passed_count', 0)} approved / {_a.get('blocked_count', 0)} blocked · {req.query[:60]}")
    return PackResponse(
        query=result["query"],
        pack_markdown=result["pack_markdown"],
        included=result["included"],
        excluded=result["excluded"],
        recall_answer=result.get("recall_answer"),
        audit=AuditResponse(**result["audit"]) if result.get("audit") else None,
    )


@app.post("/forget", response_model=ForgetResponse)
async def forget(req: ForgetRequest) -> ForgetResponse:
    result = await forget_memory(req.memory_id, reason=req.reason)
    log_activity("api", "forget", f"{result.get('status', '?')} · {req.memory_id}")
    return ForgetResponse(**result)


@app.post("/improve")
async def improve_endpoint() -> dict:
    """Distil durable coding rules from stored sessions (Cognee memify / improve)."""
    return await improve_memory()


@app.get("/rules")
async def rules_endpoint(query: str = "What coding rules apply when working in this repo?") -> dict:
    return {"query": query, "rules": await recall_rules(query)}


@app.get("/activity")
async def activity(limit: int = 40) -> dict:
    """Recent firewall calls (MCP + REST) for the live console feed. Observability only."""
    return {"events": get_activity(limit=limit)}


@app.get("/graph", response_model=GraphResponse)
async def graph(limit: int = 400) -> GraphResponse:
    data = await graph_view(limit=limit)
    return GraphResponse(nodes=data.get("nodes", []), edges=data.get("edges", []))


@app.get("/sessions", response_model=List[SessionSummary])
async def sessions() -> List[SessionSummary]:
    return [SessionSummary(**s) for s in await list_sessions()]


@app.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
async def timeline(session_id: str) -> TimelineResponse:
    events = await session_timeline(session_id)
    summary = SessionSummary(session_id=session_id, task="", event_count=len(events))
    return TimelineResponse(session=summary, events=events)


async def _reset_memory() -> None:
    """Wipe all Cognee stores, used to keep /demo/seed idempotent on the demo Space."""
    configure_cognee()
    import cognee

    try:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(graph=True, vector=True, metadata=True)
    except Exception:  # noqa: BLE001
        pass


@app.post("/reset")
async def reset() -> dict:
    await _reset_memory()
    return {"status": "ok", "message": "All Cognee memory pruned."}


@app.post("/demo/seed", response_model=IngestResponse)
async def demo_seed(cognify: bool = True, reset: bool = True) -> IngestResponse:
    if not DEMO_SESSION.exists():
        raise HTTPException(status_code=404, detail="bundled demo session not found")
    # Idempotent by default: prune first so repeated seeds (or proxy retries) never duplicate.
    if reset:
        await _reset_memory()
    session = hydrate_demo_secrets(json.loads(DEMO_SESSION.read_text()))
    res = await ingest_session(session, cognify=cognify)
    return IngestResponse(
        session_id=res["session_id"],
        nodes_added=res["nodes_added"],
        memories_created=res["memories_created"],
        cognified=res["cognified"],
        message="Seeded the sample taskflow-api onboarding session.",
    )


@app.get("/demo/queries")
async def demo_queries() -> dict:
    return {
        "queries": [
            "What should a new agent know before working on taskflow-api?",
            "How do I deploy taskflow-api safely?",
            "Do JWT access tokens expire in taskflow-api?",
            "How is the public API rate-limited?",
        ]
    }
