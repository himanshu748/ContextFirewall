# ContextFirewall MCP server

Put the memory firewall **inside your coding agent**. This is a small [MCP](https://modelcontextprotocol.io) server that wraps the existing ContextFirewall API, so any MCP client (Claude Code, Cursor, Windsurf, Cline) can pull a governed context pack and record session memories that future packs will audit on Cognee.

It is a thin client over the HTTP API. It changes nothing about the backend.

## Tools

| Tool | What it does | Cognee verb |
|------|--------------|-------------|
| `get_trusted_context(task, top_k=12)` | Returns a **trusted context pack** for the task. Only memories that pass all four checks (staleness, contradiction, secret, evidence) are included. | recall + audit |
| `record_event(kind, content, subject="")` | Buffers a session event. If `subject` is set, it is also stored as a durable memory that future packs audit. | (stages remember) |
| `commit_session(task="", repo="", cognify=true)` | Persists the buffered session into Cognee and cognifies it. | remember |
| `forget_memory(memory_id, reason="")` | Deletes a memory from the graph and vector store so it can never resurface. | forget |

The intended loop: call `get_trusted_context` before you act, `record_event` as you work, and `commit_session` when the task is done so the next session starts from governed memory.

## Connect it

### Claude Code

```bash
claude mcp add contextfirewall \
  --env CF_API_BASE=https://himanshukumarjha-contextfirewall.hf.space \
  -- uvx --from "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp" contextfirewall-mcp
```

### Cursor, Windsurf, Claude Desktop

Add to your MCP config (`.cursor/mcp.json`, `~/.codeium/windsurf/mcp_config.json`, or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "contextfirewall": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp", "contextfirewall-mcp"],
      "env": { "CF_API_BASE": "https://himanshukumarjha-contextfirewall.hf.space" }
    }
  }
}
```

`uvx` (from [uv](https://docs.astral.sh/uv/)) fetches and runs the server in one step. The git form needs the repo to be public; until then, use the local option below.

### Local (from a clone, no install)

```bash
git clone https://github.com/himanshu748/ContextFirewall
cd ContextFirewall/mcp
uv run --with mcp python -m contextfirewall_mcp
```

Config form:

```json
{
  "mcpServers": {
    "contextfirewall": {
      "command": "uv",
      "args": ["run", "--with", "mcp", "python", "-m", "contextfirewall_mcp"],
      "cwd": "/absolute/path/to/ContextFirewall/mcp",
      "env": { "CF_API_BASE": "http://localhost:8000" }
    }
  }
}
```

## Configuration

| Variable | Default | Notes |
|----------|---------|-------|
| `CF_API_BASE` | the public demo Space | The ContextFirewall API to talk to. |
| `CF_SESSION_FILE` | `~/.contextfirewall/session.json` | Where `record_event` buffers the session. |
| `CF_HTTP_TIMEOUT` | `120` | Request timeout in seconds. |

## Privacy

The default `CF_API_BASE` points at the shared public demo, which is convenient for trying `get_trusted_context` but is not where you want your real memories. For private use, run your own ContextFirewall instance and point `CF_API_BASE` at it. The backend runs fully local (SQLite, LanceDB, Kuzu) and can use a local model endpoint, so with a self-hosted instance nothing, prompts or memories, leaves your machine.

## Test

```bash
cd mcp
uv run --with mcp python tests/test_mcp.py
```

The write-path tools are tested against a local mock (so they never touch the public demo), and the read path plus MCP handshake are tested against the live API.
