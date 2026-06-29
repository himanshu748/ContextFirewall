# ContextFirewall

**Guardrails for the memory layer.** A trust firewall for AI coding-agent memory, built on [Cognee](https://github.com/topoteretes/cognee).

Built for the **WeMakeDevs × Cognee** hackathon, *The Hangover Part AI: Where's My Context?* (Jun 29 to Jul 5, 2026).

| | |
|---|---|
| **Live console** | https://contextfirewall.vercel.app |
| **Live API (docs)** | https://himanshukumarjha-contextfirewall.hf.space/health · [`/docs`](https://himanshukumarjha-contextfirewall.hf.space/docs) |
| **Demo video** | https://pub.hyperagent.com/api/published/pbf01KW9YQEZY_WK8T6EPDES8FMT04/contextfirewall_demo.mp4 |
| **Source** | https://github.com/himanshu748/ContextFirewall |

> Open the console and click **Run the firewall**: 10 remembered facts from a sample agent session are audited live on Cognee. 6 pass into a trusted context pack; 4 are blocked, one per check, each with a plain-language reason.

---

## The problem

AI coding agents are getting long-term memory. But memory that is **stale, contradicted, leaked, or unproven** is worse than no memory: it silently steers the next agent wrong. A remembered `deploy` command that changed last week, a "fix" that was later disproven, an API key captured in a transcript, a confident claim with no evidence. Today these all flow straight back into the next session's context.

## The solution

ContextFirewall records agent sessions into a Cognee knowledge graph and, **before any remembered fact reaches the next agent**, runs four audit checks. Only memories that pass are assembled into a **trusted context pack**. The ungoverned raw recall is shown side by side, so you can see exactly what the firewall kept out.

| Check | Blocks a memory when |
|------|------------------------|
| **Staleness / validity** | a newer value supersedes it (for example, the deploy target changed) |
| **Contradiction** | a better-supported memory disagrees with it (the weaker side is blocked, the winner passes) |
| **Secret / sensitivity** | it contains a credential (API key, DB URI, private key); it is redacted and never re-leaked |
| **Evidence / trust** | it is unsupported: a low trust score with no evidence recorded in the session |

A human can **forget** any memory; it is deleted from Cognee (graph and vector) so it can never resurface in recall or a future pack.

## Built on Cognee's full memory lifecycle

ContextFirewall exercises **all four** Cognee verbs. Depth here is the point.

| Verb | How ContextFirewall uses it |
|------|------------------------------|
| **Remember** | `cognee.add` + `cognify` build the entity graph from a session transcript, plus a typed `Repo → AgentSession → SessionEvent → Memory` graph (with `supersedes` relations) so the firewall has deterministic objects to audit |
| **Recall** | `cognee.search` (`GRAPH_COMPLETION`) for the ungoverned baseline, plus vector recall over the memory nodes joined with their graph properties to gather candidate memories |
| **Improve** | `memify` distils durable `Rule` nodes into the `coding_agent_rules` node set, retrievable via `SearchType.CODING_RULES`; trust scores are derived from evidence and reinforcement |
| **Forget** | governance: a rejected or blocked memory is removed from both the graph and the vector store |

The graph is **load-bearing**: staleness rides on temporal supersession, contradiction is adjudicated within a recalled cluster of same-subject memories, and the trusted pack is assembled from typed nodes, not a flat vector list.

## How it maps to the judging criteria

- **Potential impact.** Memory governance is a real and growing attack surface as agents gain persistence. A trust gate that audits every fact before it is reused, with a human forget control, is reusable across any agent stack.
- **Technical execution.** One env-switched codebase runs on local stores in dev and on managed Neo4j Aura + Supabase pgvector in production. Real model and graph calls only, no mocks. 21 unit tests; a runnable end-to-end integration script.
- **Presentation quality.** A live console with five views (firewall, replay, coding rules, knowledge graph, overview), a clear problem-to-solution story, this README, and a demo video.
- **Best use of Cognee.** All four lifecycle verbs are exercised (remember, recall, improve/memify, forget), and the knowledge graph is essential to how staleness and contradiction are judged.

## Architecture

- **Backend:** FastAPI + Cognee SDK (Python 3.12), deployed as a Docker **Hugging Face Space**.
- **Model layer:** Hugging Face inference router. **Qwen2.5-72B-Instruct** for graph extraction and contradiction adjudication, **BAAI/bge-small-en-v1.5** embeddings (384-dim, via a custom feature-extraction engine, no local model in RAM).
- **Memory (Cognee = graph + vector + relational):**
  - dev: local stores (SQLite + LanceDB + Kuzu), the full real pipeline, validated end to end.
  - prod: **Supabase Postgres + pgvector** and **Neo4j Aura**, switched purely by environment variables in `bootstrap.py`. Identical code.
- **Frontend:** Next.js + Tailwind on **Vercel**. Five console views: overview, firewall audit, coding rules, session replay, and the knowledge graph, plus the trusted-pack-versus-ungoverned-baseline panel.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | live profile (providers, model) + node counts |
| `POST` | `/ingest` | remember a recorded session |
| `POST` | `/audit` | recall + run the four checks, returns per-memory verdicts |
| `POST` | `/pack` | gated trusted context pack (and the ungoverned baseline) |
| `POST` | `/improve` | distil coding rules (memify) |
| `GET` | `/rules` | recall distilled rules (`CODING_RULES` search) |
| `POST` | `/forget` | delete a memory from Cognee (governance) |
| `GET` | `/graph` | knowledge-graph nodes and edges |
| `GET` | `/sessions/{id}/timeline` | session replay |
| `POST` | `/demo/seed` | ingest the bundled sample session (idempotent) |

Try it against the live API:

```bash
curl -s -X POST https://himanshukumarjha-contextfirewall.hf.space/pack \
  -H 'content-type: application/json' \
  -d '{"query": "How do I deploy taskflow-api safely?"}'
```

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

`.env.example` documents every variable. For local dev you only need a Hugging Face API key; Cognee uses local file stores. To run on managed stores, set the Postgres/pgvector/Neo4j variables and the same code externalizes storage.

## The demo data, and what is real

The bundled demo is a **sample agent session on a fictional `taskflow-api` repo** (a task-management backend: FastAPI, Postgres, Redis, Stripe). An agent onboards and picks up a search-latency ticket. The ten memories are clearly-illustrative **inputs**, engineered so each check is exercised:

- **Staleness:** `flyctl deploy --remote-only` (Feb) is superseded by `make release` (Jun) on the subject "deploy command".
- **Contradiction:** "JWT access tokens never expire" (trust 0.45) loses to "expire after 15 minutes, use the refresh flow" (verified, trust 0.99).
- **Secret:** an AWS access key in a worker-config note is detected and redacted (`AKIA…PLE`).
- **Evidence:** "`/search` sustains 1,000,000 req/s, no caching" is unsupported (trust 0.10) and blocked.

Everything **downstream of those inputs is real system output**: the verdicts, trust scores, the knowledge graph, the distilled rules, and the trusted pack all come from live Cognee and the live model. No verdict is hard-coded, and no results are fabricated.

## Evidence (real runs, no mocks)

- `scripts/dev_integration.py` is green on real Cognee + Hugging Face: ingest → cognify → recall → four checks → pack, with **6 approved and 4 blocked** for exactly the right reasons.
- `cognify` runs live on Qwen2.5-72B; `GRAPH_COMPLETION` correctly reasons over the temporal deploy-command change.
- 21 unit tests pass (`tests/test_secrets.py`, `tests/test_checks.py`).
- The production deployment runs on managed stores: `/health` reports `graph: neo4j`, `relational: postgres`, `vector: pgvector`.

## AI-assistance disclosure

This project was built with AI assistance (**Hyperagent**), disclosed per the hackathon rules. All Cognee usage is real: live model and graph calls, not mocked. The demo session is a clearly-labeled sample; every firewall verdict shown is genuine system output.
