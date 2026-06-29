---
title: ContextFirewall API
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Trust firewall for AI coding-agent memory, built on Cognee
---

# ContextFirewall API

FastAPI + Cognee backend for **ContextFirewall** — guardrails for the memory layer.

It records AI coding-agent sessions into a Cognee knowledge graph and, before any
remembered fact reaches the next agent, runs four audit checks (staleness,
contradiction, secret, evidence), assembling only what passes into a trusted
context pack.

- Interactive API docs: **`/docs`**
- Health + node counts: **`/health`**
- Seed the real demo session: `POST /demo/seed`

Model layer: Hugging Face inference router (Qwen2.5-72B chat + BAAI/bge-small-en-v1.5
embeddings). Storage: Cognee (local stores, or externalized to Supabase Postgres +
pgvector and Neo4j Aura via Space secrets).

Built for the WeMakeDevs × Cognee hackathon. Built with AI assistance (Hyperagent),
disclosed per the rules; all Cognee usage is real — live model and graph calls.
