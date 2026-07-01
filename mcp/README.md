# ContextFirewall MCP server

Put the memory firewall **inside your coding agent**. ContextFirewall speaks the [Model Context Protocol](https://modelcontextprotocol.io), so any MCP client (Claude Code, Cursor, Windsurf, Cline, Claude Desktop) can pull a governed context pack and record, distil, or forget memories, all audited on Cognee.

There are **two transports with an identical six-tool surface**:

- **Hosted (streamable HTTP):** the server is mounted at `/mcp` on the backend. Connect in one line, nothing to install.
- **Local (stdio):** this package, a tiny zero-dependency client over the HTTP API. Run it with `uvx`, pointed at any ContextFirewall backend.

## Tools

| Tool | What it does | Cognee verb |
|------|--------------|-------------|
| `get_trusted_context(task, top_k=12)` | Returns a **trusted context pack** for the task. Only memories that pass all four checks (staleness, contradiction, secret, evidence) are included. | recall |
| `audit_context(task, top_k=12)` | Per-memory verdicts: what was **approved**, what was **blocked**, the failing check and a plain-language reason, plus the `memory_id`. | recall |
| `remember(text, subject="", kind="fact")` | Store a durable fact. With a `subject` set, the firewall can later detect staleness and contradiction against peers. Secrets are redacted at ingest. | remember |
| `forget_memory(memory_id, reason="rejected via MCP")` | Delete a memory from the graph and vector store so it can never resurface. | forget |
| `improve_rules()` | Distil reusable coding rules from recorded sessions (memify). | improve |
| `list_coding_rules(query="")` | Retrieve the distilled coding rules (`CODING_RULES` search). | recall |

The intended loop: `get_trusted_context` before you act, `remember` durable facts as you work, `improve_rules` when a task is done, `forget_memory` to retract a bad one. The next session starts from governed memory, not a raw dump.

## Connect it

### Hosted (one line, no install)

**Claude Code:**

```bash
claude mcp add --transport http contextfirewall https://himanshukumarjha-contextfirewall.hf.space/mcp
```

**Cursor / Cline / generic (`.cursor/mcp.json` or `mcp.json`):**

```json
{
  "mcpServers": {
    "contextfirewall": {
      "url": "https://himanshukumarjha-contextfirewall.hf.space/mcp"
    }
  }
}
```

**Windsurf (`~/.codeium/windsurf/mcp_config.json`)** — the key is `serverUrl`, not `url`:

```json
{
  "mcpServers": {
    "contextfirewall": {
      "serverUrl": "https://himanshukumarjha-contextfirewall.hf.space/mcp"
    }
  }
}
```

### Local (stdio via uvx)

Runs the server on your machine and talks to a ContextFirewall backend over HTTP. `uvx` (from [uv](https://docs.astral.sh/uv/)) fetches and runs it in one step.

**Claude Code:**

```bash
claude mcp add contextfirewall \
  --env CF_API_BASE=https://himanshukumarjha-contextfirewall.hf.space \
  --env CF_API_KEY=cf_live_... \
  -- uvx --from "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp" contextfirewall-mcp
```

**Config form (Cursor, Windsurf, Cline, Claude Desktop):**

```json
{
  "mcpServers": {
    "contextfirewall": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp", "contextfirewall-mcp"],
      "env": { "CF_API_BASE": "https://himanshukumarjha-contextfirewall.hf.space", "CF_API_KEY": "cf_live_..." }
    }
  }
}
```

### Local from a clone (no install)

```bash
git clone https://github.com/himanshu748/ContextFirewall
cd ContextFirewall/mcp
uv run --with mcp python -m contextfirewall_mcp
```

## Configuration

| Variable | Default | Notes |
|----------|---------|-------|
| `CF_API_BASE` | the public demo Space | The ContextFirewall backend the stdio server talks to. |
| `CF_API_KEY` | (none) | ContextFirewall API key (`cf_live_...`), sent as `Authorization: Bearer`. Required for writes (`remember`/`forget_memory`) and to scope reads/writes to your private namespace. Without it the stdio server is read-only against the public demo, and write tools fail with an HTTP 401. |
| `CF_HTTP_TIMEOUT` | `120` | Request timeout in seconds. |

## Privacy

The default `CF_API_BASE` points at the shared public demo, convenient for trying it but not where you want your real memories. For private use, run your own ContextFirewall backend and point `CF_API_BASE` at it. The backend runs fully local (SQLite, LanceDB, and cognee's default graph) and can use a local model endpoint, so with a self-hosted instance nothing, prompts or memories, leaves your machine.

## Test

```bash
cd mcp
# stdio package: mock write path + live MCP protocol handshake
CF_API_BASE=https://himanshukumarjha-contextfirewall.hf.space uv run --with mcp python tests/test_mcp.py
```

The write-path tools are tested against a local mock (so they never touch a real graph); the read path plus MCP handshake run against the live API. The hosted streamable-HTTP endpoint is exercised by `backend/scripts/mcp_http_probe.py` and `backend/scripts/mcp_full_probe.py`.
