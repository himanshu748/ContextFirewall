# ContextFirewall: putting guardrails on an AI agent's memory

*Built for the WeMakeDevs × Cognee hackathon, "The Hangover Part AI: Where's My Context?"*

AI coding agents are finally getting long-term memory. That is the good news. The bad news is the part nobody likes to say out loud: **a memory layer is only as trustworthy as the worst fact in it.** The moment an agent can remember, it can also remember *wrong*, and confidently hand that wrong thing to the next agent in line.

ContextFirewall is a small idea taken seriously: **audit every remembered fact before it reaches the next agent.** Think of it as a firewall that sits between an agent's memory and its context window. Memories that are stale, contradicted, secret, or unproven are held back. Only what survives the audit is assembled into a trusted context pack for the next session.

You can run it yourself: open the [live console](https://contextfirewall.vercel.app), click **Run the firewall**, and watch ten remembered facts get audited live on Cognee. Six pass, four are blocked, each with a reason a human can read.

## The four failure modes

The live demo runs on a sample onboarding session for a fictional `taskflow-api` repo: an agent picks up a search-latency ticket and pulls in what earlier sessions "remembered." Four of those memories should never reach it, and each one fails a different check:

1. **Stale.** An old note says deploy with `flyctl deploy --remote-only`. A newer memory says the team moved off Fly.io and now ships with `make release`. Both were true once; only one is current. Temporal supersession catches it.
2. **Contradicted.** One memory claims "JWT access tokens never expire, cache them forever." A better-supported, verified memory says they expire after 15 minutes and clients must use the refresh flow. The weaker claim loses.
3. **A leaked secret.** A worker-config note contains an AWS access key. That is a live credential sitting in memory, one recall away from leaking again. It is detected and redacted before anything else happens.
4. **Unsupported.** "The `/search` endpoint sustains 1,000,000 requests per second with no caching" has a trust score of 0.10 and no evidence behind it. Confident, round, and unproven. Blocked.

A naive memory system recalls all four. ContextFirewall blocks all four, each with a plain-language reason, and passes only what is left.

## The four checks

Every candidate memory runs a gauntlet:

- **Staleness.** Temporal supersession. If a newer value exists for the same subject, the old one is stale.
- **Contradiction.** An LLM adjudicates within a recalled cluster of same-subject memories. Crucially, only the *weaker* side of a conflict is blocked; the better-supported memory passes. Authority is trust score, then evidence, then recency.
- **Secret.** A deterministic detector for API keys, database connection URIs, private keys, and JWTs. Matches are redacted, so the secret is never re-leaked into a log or the pack.
- **Evidence.** A trust score derived from real signals (evidence links, reinforcement, verification). Unsupported, low-trust claims do not pass.

Each verdict is explainable. Click any memory in the console and you see all four checks, the trust score, the source session, and a one-click **forget** button.

## Why Cognee is load-bearing

The hackathon's whole theme is memory that *forgets the right things*, and ContextFirewall leans on all four of Cognee's lifecycle verbs:

- **Remember.** `cognee.add` + `cognify` build the entity graph from a session transcript, while a typed `Repo → AgentSession → SessionEvent → Memory` graph (with `supersedes` relations) gives the firewall deterministic objects to audit.
- **Recall.** Vector recall over the memory nodes joined with their graph properties, plus `GRAPH_COMPLETION` for the "ungoverned baseline" we show side by side in the UI.
- **Improve.** `memify` distils durable coding `Rule` nodes from sessions, retrievable via `SearchType.CODING_RULES`. These are the lessons that outlive any single task.
- **Forget.** When a human rejects a memory, it is deleted from *both* the graph and the vector store, so it can never resurface.

The graph is not decoration. Staleness rides on temporal supersession, contradiction adjudicates over recalled clusters, and the pack is assembled from typed nodes. A flat vector store cannot tell you *when* a fact was superseded or *which* of two memories is more authoritative. The graph can.

## Three war stories (because honesty is the brief)

These are real notes from building ContextFirewall itself, not from the demo.

**1. The embedding engine that silently was not.** We wrote a custom Cognee embedding engine to hit Hugging Face's feature-extraction endpoint and registered it by monkey-patching `create_embedding_engine`. Every embed call still fell through to LiteLLM and 404'd. The cause was beautifully subtle: Cognee's `embeddings` package `__init__` does `from .get_embedding_engine import get_embedding_engine`, which **shadows the submodule with a function of the same name**. So `import ...get_embedding_engine as m` bound `m` to the *function*, and our patch set a dead attribute on it. The fix was `importlib.import_module(...)` to reach the real module. One line, hours of confusion.

**2. The flaky provider.** Cognify worked once, then started returning `403, provider 'deepinfra' is not available`. The Hugging Face router auto-selects an inference provider per request, and this key could not use the one it kept picking. Pinning the model to `:novita` made it deterministic.

**3. The secret scanner that flagged our secret detector.** After the first push, GitGuardian alerted on a "Postgres leak." The culprit? The *unit tests for our secret detector*. They contained synthetic `postgresql://...` and `neo4j+s://...` strings to test detection. The passwords were fake, but the pattern is the pattern. We fixed it by assembling every secret-shaped string at runtime from fragments, so no credential-shaped literal is ever committed. A secret-detection tool tripping a secret scanner with its own test fixtures is the most on-theme bug we could have asked for.

## Architecture

FastAPI + Cognee on a Dockerized Hugging Face Space. Qwen2.5-72B and BAAI/bge-small-en-v1.5 through the Hugging Face inference router, with no local model in RAM. Storage is environment-switched: local SQLite, LanceDB, and Kuzu in dev; Supabase Postgres + pgvector and Neo4j Aura in production, with identical code. A Next.js front end on Vercel shows the firewall verdicts, a session replay timeline, the distilled coding rules, the Cognee knowledge graph, and the trusted pack versus the ungoverned baseline.

## What "done" looks like

The end-to-end check is green on real infrastructure: ingest, cognify, recall, four checks, pack, with six memories approved and four blocked for exactly the right reasons. The contradiction call is LLM-adjudicated with a deterministic trust-based fallback, so a verdict is always produced. Production runs on the managed graph and vector stores, not local files.

## A note on what is real

The demo runs on a clearly-labeled sample session (`taskflow-api`); its memories are illustrative inputs. Everything downstream of them is genuine: the verdicts, trust scores, the knowledge graph, and the distilled rules are all real output from live Cognee and the live model. Nothing is hard-coded or fabricated.

## Disclosure

This project was built with AI assistance (Hyperagent), disclosed per the hackathon rules. Every Cognee call is real. The honesty bar we held ourselves to is the same one ContextFirewall enforces: do not pass along anything you cannot back up.
