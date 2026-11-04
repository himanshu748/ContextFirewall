# Contributing to ContextFirewall

Thanks for your interest in ContextFirewall! It is a trust firewall for AI coding-agent memory: every
memory an agent recalls goes through four checks (staleness, contradiction, secrets, evidence) before
it can reach the model. Contributions of every size are welcome — bug reports, docs fixes, new secret
detectors, tests, UI polish, and new firewall checks.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

- [Ways to contribute](#ways-to-contribute)
- [Finding something to work on](#finding-something-to-work-on)
- [Project layout](#project-layout)
- [Development setup](#development-setup)
- [Running the checks](#running-the-checks)
- [Project invariants](#project-invariants)
- [Common contributions](#common-contributions)
- [Coding guidelines](#coding-guidelines)
- [Commits and pull requests](#commits-and-pull-requests)
- [Reporting security issues](#reporting-security-issues)
- [Getting help](SUPPORT.md)
- [License](#license)

## Ways to contribute

- **Report a bug** with the [bug report form](https://github.com/himanshu748/ContextFirewall/issues/new?template=bug_report.yml).
- **Propose a feature** (a new check, MCP tool, or integration) with the
  [feature request form](https://github.com/himanshu748/ContextFirewall/issues/new?template=feature_request.yml).
- **Improve the docs**: README, `mcp/README.md`, `.env.example`, or this guide.
- **Pick up an open issue** and send a pull request.
- **Try it in your agent** (Claude Code, Cursor, Windsurf, Cline) and tell us what broke or was confusing.

For anything larger than a small fix, please **comment on the issue (or open one) before you start**,
so we can agree on the approach and avoid duplicate work.

## Finding something to work on

| Label | Meaning |
|-------|---------|
| [`good first issue`](https://github.com/himanshu748/ContextFirewall/labels/good%20first%20issue) | Small, well-scoped, with pointers to the code involved |
| [`help wanted`](https://github.com/himanshu748/ContextFirewall/labels/help%20wanted) | Larger tasks where we'd especially welcome help |
| `security`, `performance`, `testing`, `ci`, `devex`, `frontend`, `mcp`, `documentation` | Area of the codebase |

Comment "I'd like to work on this" on an issue to claim it. If you go quiet for two weeks we may
unassign it so someone else can pick it up — no hard feelings.

## Project layout

```
backend/                 FastAPI + Cognee service (Python 3.12) — deployed to a Hugging Face Space
  app/main.py            REST API (/pack, /audit, /remember, /forget, /graph, ...)
  app/mcp_server.py      Hosted MCP server mounted at /mcp (the six tools)
  app/firewall/          The four checks (checks.py), secret detector (secrets.py), audit + pack
  app/cognee_runtime/    Cognee bootstrap, ingest, recall, improve (memify), forget, LLM + embeddings
  app/identity.py        API key → namespace resolution (multi-tenant isolation)
  data/sessions/         The bundled, fictional taskflow-api demo session
  scripts/               Live probes and the end-to-end integration script (need real credentials)
  tests/                 Unit tests (pytest) — no network, no model calls
frontend/                Next.js 14 + Tailwind console (graph, session replay, Connect view)
mcp/                     Standalone stdio MCP package (`uvx contextfirewall-mcp`) that calls the REST API
supabase/migrations/     Auth tables, API keys, and RLS lockdown for the hosted deployment
server.json              MCP registry manifest
```

The REST API and the hosted MCP server share one firewall/Cognee core, so logic belongs in
`app/firewall/` or `app/cognee_runtime/`, not in endpoint handlers.

## Development setup

### Prerequisites

- **Python 3.12** (we recommend [`uv`](https://docs.astral.sh/uv/))
- **Node.js 20** and npm 10 (the version CI uses)
- A **Hugging Face API token** — only needed to run the backend for real; the unit tests don't need one

### Backend

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -p .venv -r requirements.txt pytest
cp .env.example .env              # add your Hugging Face token; never commit .env
set -a && . ./.env && set +a
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000
```

The API is now at <http://localhost:8000> (interactive docs at `/docs`) and the MCP server at `/mcp`.
In development Cognee uses local file stores under `CF_DATA_DIR` (`./.cf_data`, gitignored), so you
don't need Postgres or Neo4j. Load the sample session with `curl -X POST localhost:8000/demo/seed`.

### Frontend

```bash
cd frontend
npm ci
cp .env.local.example .env.local  # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:3000
```

Sign-in and per-account API keys also need `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY`; without them the console runs in read-only demo mode with the
auth UI hidden.

### MCP package

```bash
cd mcp
uv venv .venv && uv pip install -p .venv -e .
CF_API_BASE=http://localhost:8000 .venv/bin/contextfirewall-mcp   # stdio server
```

To try it in Claude Code against your local backend:

```bash
claude mcp add contextfirewall-dev --env CF_API_BASE=http://localhost:8000 \
  -- /absolute/path/to/mcp/.venv/bin/contextfirewall-mcp
```

## Running the checks

CI (`.github/workflows/ci.yml`) runs these on every pull request. Please run them locally first:

```bash
# Backend unit tests — fast, offline, no credentials needed
cd backend && PYTHONPATH=. .venv/bin/python -m pytest -q

# Frontend lint, typecheck, production build
cd frontend && npm run lint && npx tsc --noEmit && npm run build

# MCP package: offline write-path tests (what CI runs)
cd mcp && .venv/bin/python -c "from tests.test_mcp import part_a_write_path; part_a_write_path()"

# MCP package: full suite (Part B talks to a live API — point it at your local backend)
cd mcp && CF_API_BASE=http://localhost:8000 .venv/bin/python -m tests.test_mcp
```

The scripts in `backend/scripts/` (`dev_integration.py`, `mcp_full_probe.py`, …) hit real Cognee and
Hugging Face models. Run them when you change ingest, recall, or model plumbing, and mention the
result in your PR. They are not part of CI.

## Project invariants

These properties are the point of the project. PRs that weaken them won't be merged, so please call
out anything that touches them in your PR description.

1. **Secrets never persist.** Credentials are redacted *before* anything is written to the graph,
   vector store, or cognified transcript, and redacted again on every read path. Never log, return,
   or store raw secret values — including in tests and error messages.
2. **Fail closed.** If a check can't decide (model unavailable, unparsable date, missing data), the
   memory must not silently become *more* trusted. An authentication failure must never widen access.
3. **Namespaces are isolated.** A caller only reads, audits, or forgets memories in its own namespace.
   The `demo` namespace is read-only for everyone except admin flows.
4. **One core, two transports.** The six MCP tools must keep the same names, arguments, and semantics
   in `backend/app/mcp_server.py` (hosted) and `mcp/contextfirewall_mcp/` (stdio). Change both together
   and update `README.md`, `mcp/README.md`, and `server.json`.
5. **No fabricated results.** Verdicts, rules, and packs come from real checks over real data. Don't
   hard-code outputs to make the demo look good.

## Common contributions

### Adding a secret detector

1. Add a `(kind, label, regex)` entry to `_PATTERNS` in `backend/app/firewall/secrets.py`.
2. Add tests to `backend/tests/test_secrets.py`: at least one positive match, one realistic
   **negative** (a string that looks similar but isn't a secret), and a check that `redact_text`
   removes the value.
3. Use obviously fake fixtures (e.g. `AKIAIOSFODNN7EXAMPLE`). Real-looking live tokens trip GitHub
   push protection and other people's scanners.

### Changing or adding a firewall check

Checks live in `backend/app/firewall/checks.py` and return a `CheckOutcome(check, passed, reason, severity)`.
They run in `audit_cluster` (`backend/app/firewall/audit.py`), where order decides which block reason
is shown. When you add or change a check:

- keep it deterministic where possible; LLM-assisted logic needs a deterministic fallback (`use_llm=False`),
- give it a clear, human-readable `reason` — it is shown to users and agents,
- add unit tests in `backend/tests/test_checks.py` covering pass, block, and edge cases,
- make sure the demo session still produces sensible verdicts (`POST /demo/seed`, then `POST /audit`).

### Changing an MCP tool or REST endpoint

Update both MCP surfaces (see invariant 4), the request/response models in `backend/app/models.py`,
the API table in `README.md`, and the frontend types in `frontend/lib/types.ts` if the shape changed.

### Adding configuration

New environment variables must be documented in `backend/.env.example` (or `frontend/.env.local.example`)
with a safe default and a one-line comment.

## Coding guidelines

**Python (backend, mcp)**

- Target Python 3.12 for the backend (the `mcp/` package supports 3.10+ — don't use newer syntax there).
- Use type hints on public functions and `from __future__ import annotations`, as existing modules do.
- Keep endpoint handlers thin; put logic in `app/firewall/` or `app/cognee_runtime/`.
- Don't swallow exceptions silently. If a fallback is intentional, keep it narrow and explain why.
- Match the surrounding style: PEP 8, 4-space indentation, double quotes.

**TypeScript (frontend)**

- `npm run lint` and `npx tsc --noEmit` must pass. Prefer explicit types over `any`.
- Keep API calls in `frontend/lib/api.ts` and shared types in `frontend/lib/types.ts`.
- Interactive elements must be keyboard accessible and have accessible names.
- For visual changes, include a before/after screenshot in the PR.

**Tests**

- Every bug fix should come with a test that fails without the fix.
- Unit tests must not need network access, credentials, or a model. Mock Cognee and the LLM.

## Commits and pull requests

1. Fork the repository and create a branch from `main` (e.g. `fix/staleness-timezones`).
2. Make focused changes — one logical change per PR is much easier to review.
3. Use [Conventional Commits](https://www.conventionalcommits.org/)-style messages and PR titles, as the
   history does: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`, `chore:`
   (e.g. `fix(checks): normalise timezones before comparing dates`).
4. Run the checks above, then open a PR and fill in the template. Link the issue with `Closes #123`.
5. A maintainer will review as soon as possible. Please address feedback by pushing new commits
   rather than force-pushing, so reviewers can see what changed.

### What to expect on your first pull request

- **CI waits for approval.** GitHub holds workflow runs from first-time contributors until a
  maintainer clicks *Approve and run*. A missing CI result on your first PR is normal.
- **The Vercel check may fail on forks.** Preview deployments from forks need maintainer
  authorization on Vercel. This failure doesn't reflect your change, and you can ignore it.
- **No changelog entry needed.** Maintainers update [`CHANGELOG.md`](CHANGELOG.md) when merging.
- **Credit.** Merged contributions are listed in the README's Contributors section.

Merges to `main` that touch `backend/` are automatically deployed to the public Hugging Face Space,
so `main` should always be deployable.

## Reporting security issues

Please **do not** open public issues for vulnerabilities such as redaction bypasses, cross-namespace
access, or auth flaws. Follow [SECURITY.md](SECURITY.md) instead.

## License

ContextFirewall is [MIT licensed](LICENSE). By contributing, you agree that your contributions are
licensed under the same license.
