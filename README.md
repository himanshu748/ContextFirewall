# ContextFirewall

**Guardrails for the memory layer.** An MCP server that puts a trust firewall on your AI coding agent's memory, built on [Cognee](https://github.com/topoteretes/cognee).

Connect Claude Code, Cursor, or Windsurf in one line. Every memory your agent recalls, stores, distils, or forgets flows through Cognee and four firewall checks, so stale, contradicted, secret-bearing, and unsupported memory never reaches the model.

Built for the **WeMakeDevs × Cognee** hackathon, *The Hangover Part AI: Where's My Context?* (Jun 29 to Jul 5, 2026).

| | |
|---|---|
| **MCP endpoint** | `https://himanshukumarjha-contextfirewall.hf.space/mcp` (streamable HTTP) |
| **Live console** | https://contextfirewall.vercel.app |
| **Live API (docs)** | https://himanshukumarjha-contextfirewall.hf.space/health · [`/docs`](https://himanshukumarjha-contextfirewall.hf.space/docs) |
| **Demo video** | https://pub.hyperagent.com/api/published/pbf01KWBWRQ03_TD5WV2G37P8HAFM8/hybrid.mp4 (2 min product walkthrough) |
| **Launch film** | https://pub.hyperagent.com/api/published/pbf01KWBWRWVX_7GTBE26MNV1XK3S1/cinematic.mp4 (40s teaser) |
| **Source** | https://github.com/himanshu748/ContextFirewall |

---

## Connect your agent (MCP)

ContextFirewall is a Model Context Protocol server. It ships **two transports with an identical six-tool surface**, so it drops into whatever agent you use:

- **Hosted (one line, no install):** connect straight to the streamable-HTTP endpoint on the Space.
- **Local (private):** run a tiny zero-dependency stdio server with `uvx`, pointed at any ContextFirewall backend (self-host the backend and nothing leaves your machine).

**Claude Code, hosted:**

```bash
claude mcp add --transport http contextfirewall https://himanshukumarjha-contextfirewall.hf.space/mcp
```

**Claude Code, local with uvx:**

```bash
claude mcp add contextfirewall \
  --env CF_API_BASE=https://himanshukumarjha-contextfirewall.hf.space \
  -- uvx --from "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp" contextfirewall-mcp
```

**Cursor / Windsurf / generic (`mcp.json`), hosted:**

```json
{ "mcpServers": { "contextfirewall": { "url": "https://himanshukumarjha-contextfirewall.hf.space/mcp" } } }
```

### The six tools

Identical on both transports. Together they exercise all four Cognee verbs.

| Tool | Cognee verb | What it does |
|------|-------------|--------------|
| `get_trusted_context(task)` | recall | Returns a trusted context pack: only memories that pass all four checks. |
| `audit_context(task)` | recall | Per-memory verdicts: what was approved, what was blocked, the failing check and why, plus the `memory_id`. |
| `remember(text, subject, kind)` | remember | Store a durable fact; it becomes auditable on the next recall. Secrets are redacted at ingest. |
| `forget_memory(memory_id)` | forget | Delete a memory from the graph and vector store so it can never resurface. |
| `improve_rules()` | improve / memify | Distil reusable `Rule` nodes from recorded sessions. |
| `list_coding_rules(query)` | recall | Retrieve the distilled coding rules (`CODING_RULES` search). |

The loop: call `get_trusted_context` before you act, `remember` durable facts as you learn them, `improve_rules` when a task is done, and `forget_memory` to retract anything that should never come back. Full client setup and privacy notes are in [`mcp/README.md`](mcp/README.md).

---

## The problem

AI coding agents are getting long-term memory. But memory that is **stale, contradicted, leaked, or unproven** is worse than no memory: it silently steers the next agent wrong. A remembered `deploy` command that changed last week, a "fix" that was later disproven, an API key captured in a transcript, a confident claim with no evidence. Today these all flow straight back into the next session's context.

## The solution

ContextFirewall records agent sessions into a Cognee knowledge graph and, **before any remembered fact reaches the agent**, runs four audit checks. Only memories that pass are assembled into a **trusted context pack**. The ungoverned raw recall is shown side by side, so you can see exactly what the firewall kept out.

| Check | Blocks a memory when |
|------|------------------------|
| **Staleness / validity** | a newer value supersedes it (for example, the deploy target changed) |
| **Contradiction** | a better-supported memory disagrees with it (the weaker side is blocked, the winner passes) |
| **Secret / sensitivity** | it contains a credential (API key, DB URI, private key); it is redacted at ingest, so it never persists and never reaches the pack |
| **Evidence / trust** | it is unsupported: a low trust score with no evidence recorded in the session |

A human (or the agent, via `forget_memory`) can **forget** any memory; it is deleted from Cognee so it can never resurface in recall or a future pack.

## Built on Cognee's full memory lifecycle

ContextFirewall exercises **all four** Cognee verbs, and every MCP tool maps onto one. Depth here is the point.

| Verb | How ContextFirewall uses it |
|------|------------------------------|
| **Remember** | `cognee.add` + `cognify` build the entity graph from a session transcript, plus a typed `Repo → AgentSession → SessionEvent → Memory` graph (with `supersedes` relations) so the firewall has deterministic objects to audit. `remember(...)` is the single-shot path. |
| **Recall** | `cognee.search` (`GRAPH_COMPLETION`) for the ungoverned baseline, plus vector recall over the memory nodes joined with their graph properties to gather candidates the firewall audits. |
| **Improve** | `memify` distils durable `Rule` nodes into the `coding_agent_rules` node set, retrievable via `SearchType.CODING_RULES`; trust scores are derived from evidence and reinforcement. |
| **Forget** | governance: a rejected or blocked memory is removed from both the graph and the vector store. |

The graph is **load-bearing**: staleness rides on temporal supersession, contradiction is adjudicated within a recalled cluster of same-subject memories, and the trusted pack is assembled from typed nodes, not a flat vector list.

## How it maps to the judging criteria

- **Potential impact.** Memory governance is a real and growing attack surface as agents gain persistence. An MCP firewall that audits every fact before it is reused, with a forget control, drops into any MCP-capable agent stack.
- **Technical execution.** One env-switched codebase runs on local stores in dev and on managed Neo4j Aura + Supabase pgvector in production. The MCP server and the REST API share one core (no duplicated logic). Real model and graph calls only, no mocks. 21 unit tests; the full MCP verb cycle validated over both streamable HTTP and stdio on real Cognee.
- **Presentation quality.** A live console (overview, **connect**, firewall, coding rules, session replay, an interactive knowledge graph) with a live MCP activity feed, this README, the MCP tool reference, and two videos: a two minute product walkthrough and a forty second launch film.
- **Best use of Cognee.** All four lifecycle verbs are exercised and surfaced as MCP tools, and the knowledge graph is essential to how staleness and contradiction are judged.

## Architecture

- **MCP server:** the headline surface, mounted at `/mcp` on the backend (streamable HTTP, stateless), plus a zero-dependency stdio package under [`mcp/`](mcp/) for laptops. Both expose the same six tools from one definition.
- **Backend:** FastAPI + Cognee SDK (Python 3.12), deployed as a Docker **Hugging Face Space**. The MCP tools and the REST endpoints both call one firewall/Cognee core.
- **Model layer:** Hugging Face inference router. **Qwen2.5-72B-Instruct** for graph extraction and contradiction adjudication, **BAAI/bge-small-en-v1.5** embeddings (384-dim, via a custom feature-extraction engine, no local model in RAM).
- **Memory (Cognee = graph + vector + relational):**
  - dev: local stores (SQLite + LanceDB + Kuzu), the full real pipeline, validated end to end.
  - prod: **Supabase Postgres + pgvector** and **Neo4j Aura**, switched purely by environment variables in `bootstrap.py`. Identical code.
- **Frontend:** Next.js + Tailwind on **Vercel**. A live, interactive force-directed knowledge graph (drag, zoom, pan, click a node for its verdict), the Connect view, and a polling firewall activity feed.

## API

The MCP tools are the primary surface; these REST endpoints back them and power the console.

| Method | Path | Purpose |
|--------|------|---------|
| `ANY` | `/mcp` | **MCP server (streamable HTTP): the six firewall tools** |
| `GET` | `/health` | live profile (providers, model) + node counts |
| `POST` | `/ingest` | remember a recorded session |
| `POST` | `/remember` | remember one durable fact (single-shot) |
| `POST` | `/audit` | recall + run the four checks, per-memory verdicts |
| `POST` | `/pack` | gated trusted context pack (and the ungoverned baseline) |
| `POST` | `/improve` | distil coding rules (memify) |
| `GET` | `/rules` | recall distilled rules (`CODING_RULES` search) |
| `POST` | `/forget` | delete a memory from Cognee (governance) |
| `GET` | `/graph` | knowledge-graph nodes and edges |
| `GET` | `/activity` | recent firewall calls (MCP + REST) for the live feed |
| `GET` | `/sessions/{id}/timeline` | session replay |
| `POST` | `/demo/seed` | ingest the bundled sample session (idempotent) |

Try the trusted pack against the live API:

```bash
curl -s -X POST https://himanshukumarjha-contextfirewall.hf.space/pack \
  -H 'content-type: application/json' \
  -d '{"query": "How do I deploy taskflow-api safely?"}'
```

## Privacy and local-only mode

- **Secrets are redacted at ingest.** When a session is remembered, any detected credential (API key, database URI, private key, AWS key, JWT) is stripped before it is written to the graph, the vector store, or the cognified transcript. It never persists, and the firewall still blocks the memory it came from. The read paths redact defensively as a second layer.
- **Storage is local by default.** In dev, Cognee runs on local SQLite, LanceDB, and Kuzu, so nothing leaves the machine. The managed Neo4j Aura and Supabase pgvector setup is only for the hosted demo; self-host and your memory graph stays yours.
- **Local model option.** The model and embedding endpoints are environment-configurable. Point them at a local OpenAI-compatible server (for example Ollama) for a fully offline deployment.

## Run locally

```bash
# Backend
cd backend
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
cp .env.example .env        # add your Hugging Face API key
set -a && . ./.env && set +a
PYTHONPATH=. .venv/bin/python scripts/dev_integration.py   # end-to-end check on real Cognee
PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8000     # MCP at /mcp, API at /

# Frontend
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

For local dev you only need a Hugging Face API key; Cognee uses local file stores. To run on managed stores, set the Postgres/pgvector/Neo4j variables and the same code externalizes storage.

## The demo data, and what is real

The bundled demo is a **sample agent session on a fictional `taskflow-api` repo** (a task-management backend: FastAPI, Postgres, Redis, Stripe). An agent onboards and picks up a search-latency ticket. The ten memories are clearly-illustrative **inputs**, engineered so each check is exercised:

- **Staleness:** `flyctl deploy --remote-only` (Feb) is superseded by `make release` (Jun) on the subject "deploy command".
- **Contradiction:** "JWT access tokens never expire" (trust 0.45) loses to "expire after 15 minutes, use the refresh flow" (verified).
- **Secret:** an AWS access key in a worker-config note is detected and redacted (`AKIA…PLE`).
- **Evidence:** "`/search` sustains 1,000,000 req/s, no caching" is unsupported (trust 0.10) and blocked.

Everything **downstream of those inputs is real system output**: the verdicts, trust scores, the knowledge graph, the distilled rules, and the trusted pack all come from live Cognee and the live model. No verdict is hard-coded, and no results are fabricated.

## Evidence (real runs, no mocks)

- The full MCP verb cycle is validated over both transports on real Cognee + Hugging Face: `get_trusted_context` and `audit_context` return **6 approved and 4 blocked** for exactly the right reasons; `remember` adds an auditable memory; `improve_rules` distils real `Rule` nodes; `forget_memory` removes from graph and vector.
- `scripts/mcp_http_probe.py` and `scripts/mcp_full_probe.py` exercise the hosted streamable-HTTP endpoint; `mcp/tests/test_mcp.py` covers the stdio write path and the MCP protocol handshake.
- `cognify` runs live on Qwen2.5-72B; `GRAPH_COMPLETION` correctly reasons over the temporal deploy-command change.
- 21 unit tests pass (`tests/test_secrets.py`, `tests/test_checks.py`).
- The production deployment runs on managed stores: `/health` reports `graph: neo4j`, `relational: postgres`, `vector: pgvector`.

## Roadmap

- **Trust re-weighting over time**, reinforcing memories that prove correct and decaying those that do not.
- **Continuous auto-recording** of live agent sessions, instead of explicit `remember` calls.
- **Cross-session accumulating memory** with the firewall governing the growing graph.
- **Managed Cognee Cloud** as a hosting option alongside the self-hosted path.

## AI-assistance disclosure

This project was built with AI assistance (**Hyperagent**), disclosed per the hackathon rules. All Cognee usage is real: live model and graph calls, not mocked. The demo session is a clearly-labeled sample; every firewall verdict shown is genuine system output.
