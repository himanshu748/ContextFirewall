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
  POST /demo/seed                   ingest the bundled sample session (idempotent, non-destructive)
  GET  /demo/queries                suggested demo queries
  POST /reset                       admin-only: wipe Cognee stores (requires X-Admin-Token)
  ANY  /mcp                         MCP server (streamable HTTP): the six firewall tools

The same six MCP tools also ship as a local stdio package under ``mcp/``.

Destructive operations (pruning the stores) are gated behind an admin token so the
public demo deployment cannot be wiped by an anonymous caller. Set ``CF_ADMIN_TOKEN``
in the environment to enable them; without it, destructive paths are disabled.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.activity import get_activity, log_activity
from app.identity import resolve_identity
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


def _admin_token_ok(token: Optional[str]) -> bool:
    """True only when an admin token is configured AND the caller presents the match."""
    configured = os.environ.get("CF_ADMIN_TOKEN")
    return bool(configured) and bool(token) and token == configured


def _require_admin(token: Optional[str]) -> None:
    """Gate a destructive operation. 403 if no admin token is configured or it does not match."""
    if not os.environ.get("CF_ADMIN_TOKEN"):
        raise HTTPException(status_code=403, detail="Destructive operations are disabled on this deployment.")
    if not _admin_token_ok(token):
        raise HTTPException(status_code=403, detail="A valid X-Admin-Token is required for this operation.")


_WRITE_AUTH_DETAIL = "A valid ContextFirewall API key is required for writes. Sign in to the console to mint one."


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
async def remember(req: RememberRequest, authorization: Optional[str] = Header(default=None)) -> RememberResponse:
    """Remember one durable fact (the single-shot 'remember' verb the MCP server uses)."""
    ident = await resolve_identity(authorization)
    if not ident.can_write:
        raise HTTPException(status_code=401, detail=_WRITE_AUTH_DETAIL)
    try:
        res = await remember_fact(
            req.text,
            subject=req.subject,
            kind=req.kind,
            trust_score=req.trust_score,
            cognify=req.cognify,
            namespace=ident.namespace,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Remember failed: {e}")
    subj = f" on '{res['subject']}'" if res.get("subject") else ""
    response = RememberResponse(
        memory_id=res["memory_id"],
        subject=res.get("subject"),
        kind=res["kind"],
        session_id=res["session_id"],
        cognified=res["cognified"],
        nodes_added=res["nodes_added"],
        message=f"Remembered {req.kind}{subj}. It is now auditable by the firewall.",
    )
    log_activity("api", "remember", f"stored {req.kind or 'fact'}")
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    profile = configure_cognee()
    counts = await count_nodes()
    return HealthResponse(status="ok", profile=profile, counts=counts)


@app.get("/activity")
async def activity(limit: int = 40) -> dict:
    return {"events": get_activity(limit)}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, authorization: Optional[str] = Header(default=None)) -> IngestResponse:
    ident = await resolve_identity(authorization)
    if not ident.can_write:
        raise HTTPException(status_code=401, detail=_WRITE_AUTH_DETAIL)
    try:
        res = await ingest_session(req.session.model_dump(), cognify=req.cognify, namespace=ident.namespace)
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
async def audit(req: AuditRequest, authorization: Optional[str] = Header(default=None)) -> AuditResponse:
    ident = await resolve_identity(authorization)
    result = await audit_memories(req.query, top_k=req.top_k, namespaces=ident.read_namespaces)
    response = AuditResponse(**result)
    log_activity(
        "api",
        "audit_context",
        f"{response.passed_count} approved · {response.blocked_count} blocked",
    )
    return response


@app.post("/pack", response_model=PackResponse)
async def pack(req: PackRequest, authorization: Optional[str] = Header(default=None)) -> PackResponse:
    ident = await resolve_identity(authorization)
    result = await build_pack(req.query, top_k=req.top_k, namespaces=ident.read_namespaces)
    response = PackResponse(
        query=result["query"],
        pack_markdown=result["pack_markdown"],
        included=result["included"],
        excluded=result["excluded"],
        recall_answer=result.get("recall_answer"),
        audit=AuditResponse(**result["audit"]) if result.get("audit") else None,
    )
    log_activity("api", "get_trusted_context", "built a trusted context pack")
    return response


@app.post("/forget", response_model=ForgetResponse)
async def forget(req: ForgetRequest, authorization: Optional[str] = Header(default=None), x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> ForgetResponse:
    ident = await resolve_identity(authorization)
    if not ident.can_write:
        raise HTTPException(status_code=401, detail=_WRITE_AUTH_DETAIL)
    result = await forget_memory(
        req.memory_id,
        reason=req.reason,
        allowed_namespaces={ident.namespace},
        allow_demo=ident.allow_demo_write or _admin_token_ok(x_admin_token),
    )
    response = ForgetResponse(**result)
    log_activity("api", "forget_memory", f"forgot {req.memory_id}")
    return response


@app.post("/improve")
async def improve_endpoint() -> dict:
    """Distil durable coding rules from stored sessions (Cognee memify / improve)."""
    res = await improve_memory()
    log_activity("api", "improve_rules", res.get("message", "distilled rules"))
    return res


@app.get("/rules")
async def rules_endpoint(query: str = "What coding rules apply when working in this repo?") -> dict:
    return {"query": query, "rules": await recall_rules(query)}


@app.get("/graph", response_model=GraphResponse)
async def graph(limit: int = 400, authorization: Optional[str] = Header(default=None)) -> GraphResponse:
    ident = await resolve_identity(authorization)
    data = await graph_view(limit=limit, namespaces=ident.read_namespaces)
    return GraphResponse(nodes=data.get("nodes", []), edges=data.get("edges", []))


@app.get("/sessions", response_model=List[SessionSummary])
async def sessions(authorization: Optional[str] = Header(default=None)) -> List[SessionSummary]:
    ident = await resolve_identity(authorization)
    return [SessionSummary(**s) for s in await list_sessions(namespaces=ident.read_namespaces)]


@app.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
async def timeline(session_id: str, authorization: Optional[str] = Header(default=None)) -> TimelineResponse:
    ident = await resolve_identity(authorization)
    events = await session_timeline(session_id, namespaces=ident.read_namespaces)
    summary = SessionSummary(session_id=session_id, task="", event_count=len(events))
    return TimelineResponse(session=summary, events=events)


async def _reset_memory() -> None:
    """Wipe all Cognee stores. Admin-gated; never reachable by an anonymous caller."""
    configure_cognee()
    import cognee

    try:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(graph=True, vector=True, metadata=True)
    except Exception:  # noqa: BLE001
        pass


@app.post("/reset")
async def reset(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> dict:
    """Admin-only: wipe all Cognee memory. Requires a valid X-Admin-Token."""
    _require_admin(x_admin_token)
    await _reset_memory()
    return {"status": "ok", "message": "All Cognee memory pruned."}


async def _demo_already_seeded() -> bool:
    try:
        counts = await count_nodes()
        return int(counts.get("Memory", 0)) > 0
    except Exception:  # noqa: BLE001
        return False


@app.post("/demo/seed", response_model=IngestResponse)
async def demo_seed(
    cognify: bool = True,
    reset: bool = False,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> IngestResponse:
    """Seed the bundled sample session.

    Non-destructive and idempotent by default: if memory already exists it is left
    untouched (this also prevents the old double-ingest from proxy retries). A
    ``reset=true`` prune-and-reseed is honored only for an authenticated admin; for
    everyone else it silently downgrades to the safe idempotent seed, so the public
    "Reload sample project" button keeps working but can never wipe the demo.
    """
    if not DEMO_SESSION.exists():
        raise HTTPException(status_code=404, detail="bundled demo session not found")

    do_reset = bool(reset) and _admin_token_ok(x_admin_token)
    if do_reset:
        await _reset_memory()
    elif await _demo_already_seeded():
        counts = await count_nodes()
        session = hydrate_demo_secrets(json.loads(DEMO_SESSION.read_text()))
        sid = session.get("session_id") or session.get("id") or "demo-session"
        response = IngestResponse(
            session_id=sid,
            nodes_added=0,
            memories_created=int(counts.get("Memory", 0)),
            cognified=True,
            message="Sample session already loaded; no changes made.",
        )
        log_activity("api", "seed", "reloaded sample taskflow-api session")
        return response

    session = hydrate_demo_secrets(json.loads(DEMO_SESSION.read_text()))
    res = await ingest_session(session, cognify=cognify, namespace="demo")
    response = IngestResponse(
        session_id=res["session_id"],
        nodes_added=res["nodes_added"],
        memories_created=res["memories_created"],
        cognified=res["cognified"],
        message="Seeded the sample taskflow-api onboarding session.",
    )
    log_activity("api", "seed", "reloaded sample taskflow-api session")
    return response


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
