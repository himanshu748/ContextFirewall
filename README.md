# ContextFirewall

**Guardrails for the memory layer.** A trust firewall for AI coding-agent memory, built on [Cognee](https://github.com/topoteretes/cognee).

Built for the **WeMakeDevs × Cognee** hackathon — *The Hangover Part AI: Where's My Context?* (Jun 29 – Jul 5, 2026).

---

## The problem

AI coding agents are getting long-term memory. But memory that is **stale, contradicted, leaked, or unproven** is worse than no memory — it silently steers the next agent wrong. A remembered `deploy` command that changed last week, a "fix" that was later disproven, an API key that got captured in a transcript, a confident claim with no evidence: today these all flow straight back into the next session's context.

## The solution

ContextFirewall records real agent sessions into a Cognee knowledge graph and, **before any remembered fact reaches the next agent**, runs four audit checks. Only memories that pass are assembled into a **trusted context pack**.

| Check | Blocks a memory when… |
|------|------------------------|
| 🕒 **Staleness / validity** | a newer value supersedes it (e.g. the deploy target changed) |
| ⚔️ **Contradiction** | a better-supported memory disagrees with it (the weaker side is blocked, the winner passes) |
| 🔑 **Secret / sensitivity** | it contains a credential (API key, DB URI, private key) — redacted, never re-leaked |
| ❓ **Evidence / trust** | it is unsupported — low trust score and no evidence in the session |

A human can **forget** any memory; it is deleted from Cognee (graph + vector) so it can never resurface in recall or a future pack.

## Built on Cognee's full memory lifecycle

ContextFirewall exercises **all four** Cognee verbs — depth here is the point:

| Verb | How ContextFirewall uses it |
|------|------------------------------|
| **Remember** | `cognee.add` + `cognify` build the entity graph from a session transcript; `add_data_points` insert a typed `Repo → AgentSession → SessionEvent → Memory` graph (with `supersedes` edges) for deterministic auditing |
| **Recall** | `cognee.search` (`GRAPH_COMPLETION`, `TEMPORAL`) for the ungoverned baseline; vector search over the `Memory_text` collection joined with graph node properties to recall candidate memories |
| **Improve** | `memify` coding-rule association distils durable `Rule` nodes (`coding_agent_rules` node set, retrievable via `SearchType.CODING_RULES`); trust scores are derived from evidence + reinforcement |
| **Forget** | governance: `delete_node` + `delete_data_points` remove a rejected/blocked memory from both the graph and the vector store |

The graph is **load-bearing**: staleness uses temporal supersession, contradiction adjudicates within a recalled cluster, and the trusted pack is assembled from typed nodes — not a flat vector list.

## Architecture

- **Backend:** FastAPI + Cognee SDK (Python 3.12), deployed as a Docker **Hugging Face Space**.
- **Model layer:** Hugging Face inference router — **Qwen2.5-72B-Instruct** (graph extraction + contradiction adjudication) and **BAAI/bge-small-en-v1.5** embeddings (384-dim, via a custom feature-extraction engine — no local model).
- **Memory (Cognee = graph + vector + relational):**
  - dev: local stores (SQLite + LanceDB + Kuzu) — fully real pipeline, validated end-to-end.
  - prod: **Supabase Postgres + pgvector** and **Neo4j Aura**, switched purely by environment variables (`bootstrap.py`) — identical code.
- **Frontend:** Next.js + Tailwind on **Vercel** — four screens: firewall audit, session replay, knowledge graph, and trusted-pack-vs-ungoverned-baseline.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | profile + node counts |
| `POST` | `/ingest` | remember a recorded session |
| `POST` | `/audit` | recall + run the four checks → per-memory verdicts |
| `POST` | `/pack` | gated trusted context pack (+ ungoverned baseline) |
| `POST` | `/improve` | distil coding rules (memify) |
| `POST` | `/forget` | delete a memory from Cognee (governance) |
| `GET` | `/graph` | knowledge-graph nodes/edges |
| `GET` | `/sessions/{id}/timeline` | session replay |
| `POST` | `/demo/seed` | ingest the bundled real onboarding session |

## Run locally

```bash
# Backend
cd backend
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
cp .env.example .env        # add your Hugging Face API key
set -a && . ./.env && set +a
PYTHONPATH=. .venv/bin/python scripts/dev_integration.py   # end-to-end check on real Cognee
PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## Evidence (real runs, no mocks)

- `dev_integration.py` → **INTEGRATION_OK**: 6 memories approved, 4 blocked — stale host decision (staleness), OOM claim (contradiction), leaked key (secret), unverified Cloud-tier claim (evidence).
- `cognify` runs live on Qwen2.5-72B (~26s); GRAPH_COMPLETION correctly reasons over temporal change.
- 21 unit tests pass (`tests/test_secrets.py`, `tests/test_checks.py`).

## AI-assistance disclosure

This project was built with AI assistance (**Hyperagent**), disclosed per the hackathon rules. All Cognee usage is real — live model and graph calls, not mocked. No fabricated demo data: the demo session is drawn from this project's own genuine build history.
