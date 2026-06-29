# ContextFirewall: putting guardrails on an AI agent's memory

*Built for the WeMakeDevs × Cognee hackathon — "The Hangover Part AI: Where's My Context?"*

AI coding agents are finally getting long-term memory. That's the good news. The bad news is the part nobody likes to say out loud: **a memory layer is only as trustworthy as the worst fact in it.** The moment an agent can remember, it can also remember *wrong* — and confidently hand that wrong thing to the next agent in line.

ContextFirewall is a small idea taken seriously: **audit every remembered fact before it reaches the next agent.** Think of it as a firewall that sits between an agent's memory and its context window.

## The failure modes that motivated it

While building this very project, our own session produced four memories that *should never* reach the next agent:

1. **Stale.** Early on we decided to host the backend on Render/Railway. A week later that became "deploy as a stateless Hugging Face Space." Both facts are "true" — but only one is current.
2. **Contradicted.** A smoke test exited with code 137 twice. The first explanation we wrote down was "OOM crash." It was wrong — they were manual interrupts. Two memories, same subject, directly incompatible.
3. **A leaked secret.** A Hugging Face key got pasted into a transcript. That's a credential sitting in memory, one recall away from leaking again.
4. **Unsupported.** "Cognee Cloud has a free hosted tier" — something we noted but never verified.

A naive memory system recalls all four. ContextFirewall blocks all four, each with a plain-language reason, and passes only what's left into a **trusted context pack**.

## The four checks

Every candidate memory runs a gauntlet:

- **🕒 Staleness** — temporal supersession. If a newer value exists for the same subject, the old one is stale.
- **⚔️ Contradiction** — an LLM adjudicates within a recalled cluster of same-subject memories. Crucially, only the *weaker* side of a conflict is blocked; the better-supported memory passes. (Authority = trust score, then evidence, then recency.)
- **🔑 Secret** — a deterministic detector for API keys, DB connection URIs, private keys, JWTs. Matches are redacted, so the secret is never re-leaked into a log or the pack.
- **❓ Evidence** — a trust score derived from real signals (evidence links, reinforcement, verification). Unsupported, low-trust claims don't pass.

## Why Cognee is load-bearing

The hackathon's whole theme is memory that *forgets the right things*, and ContextFirewall leans on all four of Cognee's lifecycle verbs:

- **Remember** — `cognee.add` + `cognify` build the entity graph from a session transcript, while `add_data_points` insert a typed `Repo → AgentSession → SessionEvent → Memory` graph (with `supersedes` edges) so the firewall has deterministic objects to audit.
- **Recall** — vector search over the `Memory_text` collection joined with graph node properties; plus `GRAPH_COMPLETION` for the "ungoverned baseline" we show side-by-side in the UI.
- **Improve** — `memify` distils durable coding `Rule` nodes from sessions (retrievable via `SearchType.CODING_RULES`).
- **Forget** — when a human rejects a memory, it's deleted from *both* the graph and the vector store, so it can never resurface.

The graph isn't decoration — staleness rides on temporal edges, contradiction adjudicates over recalled clusters, and the pack is assembled from typed nodes.

## Three war stories (because honesty is the brief)

**1. The embedding engine that silently wasn't.** We wrote a custom Cognee embedding engine to hit Hugging Face's feature-extraction endpoint, and registered it by monkey-patching `create_embedding_engine`. Every embed call still fell through to LiteLLM and 404'd. The cause was beautifully subtle: Cognee's `embeddings` package `__init__` does `from .get_embedding_engine import get_embedding_engine`, which **shadows the submodule with a function of the same name**. So `import …get_embedding_engine as m` bound `m` to the *function*, and our patch set a dead attribute on it. The fix was `importlib.import_module(...)` to reach the real module. One line; hours of confusion.

**2. The flaky provider.** Cognify worked once, then started returning `403 — provider 'deepinfra' is not available`. The HF router auto-selects an inference provider per request, and this key couldn't use the one it kept picking. Pinning the model to `:novita` made it deterministic.

**3. The secret scanner that flagged our secret detector.** After the first push, GitGuardian alerted on a "Postgres leak." The culprit? The *unit tests for our secret detector* — they contained synthetic `postgresql://…` and `neo4j+s://…` strings to test detection. The passwords were fake, but the pattern is the pattern. We fixed it by assembling every secret-shaped string at runtime from fragments, so no credential-shaped literal is ever committed. A secret-detection tool tripping a secret scanner with its own test fixtures is the most on-theme bug we could have asked for.

## Architecture

FastAPI + Cognee on a Dockerized Hugging Face Space; Qwen2.5-72B and BAAI/bge-small-en-v1.5 through the HF inference router (no local model in RAM). Storage is environment-switched: local SQLite/LanceDB/Kuzu in dev, Supabase Postgres + pgvector and Neo4j Aura in production — identical code. A Next.js front end on Vercel shows the firewall verdicts, a session replay timeline, the Cognee knowledge graph, and the trusted pack versus the ungoverned baseline.

## What "done" looks like

The end-to-end check is green on real infrastructure: ingest → cognify → recall → four checks → pack, with 6 memories approved and 4 blocked for exactly the right reasons. No mocked memories — the demo data is this project's own genuine build history.

## Disclosure

This project was built with AI assistance (Hyperagent), disclosed per the hackathon rules. Every Cognee call is real. The honesty bar we held ourselves to is the same one ContextFirewall enforces: don't pass along anything you can't back up.
