# ContextFirewall

**Guardrails for the memory layer.** A trust firewall for AI coding-agent memory, built on [Cognee](https://github.com/topoteretes/cognee).

Built for the **WeMakeDevs × Cognee** hackathon — *The Hangover Part AI: Where's My Context?* (Jun 29 – Jul 5, 2026).

## The idea

AI coding agents are getting memory. ContextFirewall makes that memory **trustworthy**. It records real agent sessions into a Cognee knowledge graph, distills lessons and trust scores, and — before any remembered fact reaches the next agent — runs four audit checks:

- 🕒 **Staleness / validity** — outdated facts (e.g. a deploy command that has since changed)
- ⚔️ **Contradiction** — facts contradicted by newer, established ones
- 🔑 **Secret / sensitivity** — leaked API keys, tokens, credentials
- ❓ **Evidence / trust** — unsupported or unproven claims

Only memories that pass are assembled into a clean **trusted context pack** for the next agent. A human can approve or forget memories. ContextFirewall exercises Cognee's full lifecycle: **remember → recall → improve (memify) → forget**.

## Status — built in public (in progress)

- ✅ Cognee 1.2.2 running live on Hugging Face inference (Qwen2.5-72B for graph extraction)
- ✅ Embeddings via the Hugging Face router API — custom engine, no local model (`app/cognee_runtime/hf_embeddings.py`)
- ✅ Config-driven runtime bootstrap that switches dev local stores ↔ prod managed stores by env (`app/cognee_runtime/bootstrap.py`)
- 🚧 Session recorder, the four audit checks, FastAPI API, and the web UI
- 🚧 Live deploy: Hugging Face Space backend + Vercel frontend, with Supabase + Neo4j Aura stores

## Architecture

- **Backend:** FastAPI + Cognee SDK (Python 3.12)
- **Model layer:** Hugging Face inference router — Qwen2.5-72B (chat / extraction) + BAAI/bge-small-en-v1.5 (embeddings)
- **Memory (Cognee — graph + vector + relational):**
  - dev: local files (SQLite + LanceDB + cognee's default graph)
  - prod: Supabase Postgres + pgvector + Neo4j Aura (stateless backend on a Space)
- **Frontend:** Next.js (planned)

## Setup (dev)

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
cp .env.example .env        # add your Hugging Face API key
set -a && . ./.env && set +a
PYTHONPATH=. .venv/bin/python scripts/smoke_cognee.py
```

## AI-assistance disclosure

This project is built with AI assistance (Hyperagent), disclosed per the hackathon rules. All Cognee usage is real — live model and graph calls, not mocked.
