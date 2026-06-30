"""Tests for the ContextFirewall MCP server.

Part A (write path) runs against a local mock HTTP server, so it never touches the
public demo graph. It proves record_event / commit_session / forget_memory build the
right requests and parse the responses.

Part B (read path + protocol) spawns the real MCP server over stdio via the official
MCP client SDK, lists tools, and calls get_trusted_context against the LIVE API, proving
end-to-end MCP conformance on real Cognee.

Run:  python -m tests.test_mcp   (from the mcp/ directory, with `mcp` installed)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MCP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_BASE = "https://himanshukumarjha-contextfirewall.hf.space"
sys.path.insert(0, MCP_DIR)


# ----------------------------- Part A: mock write path -----------------------------
class _Mock(BaseHTTPRequestHandler):
    captured: list = []

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        _Mock.captured.append((self.path, body))
        if self.path == "/ingest":
            s = body["session"]
            out = {
                "session_id": s["session_id"],
                "nodes_added": 7,
                "memories_created": len(s.get("memories", [])),
                "cognified": body.get("cognify"),
                "message": "ok (mock)",
            }
        elif self.path == "/forget":
            out = {"memory_id": body["memory_id"], "status": "forgotten", "message": "removed (mock)"}
        else:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def part_a_write_path() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Mock)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    os.environ["CF_API_BASE"] = f"http://127.0.0.1:{port}"
    os.environ["CF_SESSION_FILE"] = tmp.name
    if os.path.exists(tmp.name):
        os.remove(tmp.name)  # start with an empty buffer

    import contextfirewall_mcp as cf

    # record one durable memory and one pure timeline event
    cf._impl_record_event("decision", "Deploy with `make release`.", subject="deploy command")
    cf._impl_record_event("tool_call", "Ran the test suite, all green.")
    buf = json.load(open(tmp.name))
    assert len(buf["events"]) == 2, buf
    assert len(buf["memories"]) == 1, buf
    assert buf["memories"][0]["subject"] == "deploy command"
    assert buf["memories"][0]["evidence_event_ids"] == [buf["events"][0]["event_id"]]
    print("PASS A1: record_event buffers events + a subject-tagged memory")

    out = cf._impl_commit_session(task="demo onboarding", repo="acme/taskflow-api")
    assert "2 memories" not in out  # only 1 memory was created
    assert "1 memories" in out and "7 nodes" in out, out
    assert not os.path.exists(tmp.name), "buffer should be cleared after commit"
    path, body = next((p, b) for p, b in _Mock.captured if p == "/ingest")
    assert body["cognify"] is True
    assert body["session"]["task"] == "demo onboarding"
    assert body["session"]["repo"] == {"name": "acme/taskflow-api"}
    assert len(body["session"]["events"]) == 2 and len(body["session"]["memories"]) == 1
    print("PASS A2: commit_session POSTs a valid /ingest payload and clears the buffer")

    out = cf._impl_forget_memory("tf:m_demo", reason="qa")
    assert "forgotten" in out, out
    path, body = next((p, b) for p, b in _Mock.captured if p == "/forget")
    assert body == {"memory_id": "tf:m_demo", "reason": "qa"}
    print("PASS A3: forget_memory POSTs a valid /forget request")

    srv.shutdown()


# ------------------------- Part B: live read path + MCP protocol -------------------------
async def part_b_protocol() -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    child_env = {**os.environ, "CF_API_BASE": LIVE_BASE, "PYTHONPATH": MCP_DIR}
    child_env["CF_SESSION_FILE"] = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    params = StdioServerParameters(command=sys.executable, args=["-m", "contextfirewall_mcp"], env=child_env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            expected = {"get_trusted_context", "record_event", "commit_session", "forget_memory"}
            assert expected.issubset(set(tools)), tools
            print(f"PASS B1: MCP handshake OK, tools exposed = {tools}")

            res = await session.call_tool(
                "get_trusted_context", {"task": "How do I deploy taskflow-api safely?"}
            )
            text = "".join(getattr(c, "text", "") for c in res.content)
            assert "approved" in text and "blocked" in text, text[:300]
            assert ("make release" in text or "Trusted context pack" in text or "trust" in text), text[:300]
            print("PASS B2: get_trusted_context returns a live governed pack over MCP")
            print("---- live pack (first 280 chars) ----")
            print(text[:280])


if __name__ == "__main__":
    part_a_write_path()
    asyncio.run(part_b_protocol())
    print("\nALL MCP TESTS PASSED")
