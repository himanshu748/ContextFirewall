"""Tests for the ContextFirewall MCP server (local stdio package).

Part A (write path) runs against a local mock HTTP server, so it never touches a real
graph. It proves remember / forget_memory build the right requests and parse responses.

Part B (read path + protocol) spawns the real MCP server over stdio via the official MCP
client SDK, lists tools, and calls get_trusted_context against a live API, proving
end-to-end MCP conformance. The target API is CF_API_BASE (default: the public Space);
set it to http://127.0.0.1:8000 to test against a local backend.

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
LIVE_BASE = os.environ.get("CF_API_BASE", "https://himanshukumarjha-contextfirewall.hf.space")
sys.path.insert(0, MCP_DIR)

EXPECTED_TOOLS = {
    "get_trusted_context",
    "audit_context",
    "remember",
    "forget_memory",
    "improve_rules",
    "list_coding_rules",
}


# ----------------------------- Part A: mock write path -----------------------------
class _Mock(BaseHTTPRequestHandler):
    captured: list = []

    def log_message(self, *a):  # silence
        pass

    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        _Mock.captured.append((self.path, body))
        if self.path == "/remember":
            self._send({
                "memory_id": "mock:m1", "subject": body.get("subject"), "kind": body.get("kind"),
                "session_id": "mock", "cognified": False, "nodes_added": 3, "message": "ok (mock)",
            })
        elif self.path == "/forget":
            self._send({"memory_id": body["memory_id"], "status": "forgotten", "message": "removed (mock)"})
        else:
            self.send_response(404)
            self.end_headers()


def part_a_write_path() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Mock)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["CF_API_BASE"] = f"http://127.0.0.1:{port}"

    import contextfirewall_mcp as cf

    out = cf._impl_remember("Deploy with `make release`.", subject="deploy command", kind="command")
    assert "mock:m1" in out, out
    path, body = next((p, b) for p, b in _Mock.captured if p == "/remember")
    assert body == {"text": "Deploy with `make release`.", "subject": "deploy command", "kind": "command"}, body
    print("PASS A1: remember POSTs a valid /remember payload and returns the memory id")

    out = cf._impl_forget_memory("tf:m_demo", reason="qa")
    assert "forgotten" in out, out
    path, body = next((p, b) for p, b in _Mock.captured if p == "/forget")
    assert body == {"memory_id": "tf:m_demo", "reason": "qa"}, body
    print("PASS A2: forget_memory POSTs a valid /forget request")

    srv.shutdown()
    os.environ.pop("CF_API_BASE", None)


# ------------------------- Part B: live read path + MCP protocol -------------------------
async def part_b_protocol() -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    child_env = {**os.environ, "CF_API_BASE": LIVE_BASE, "PYTHONPATH": MCP_DIR}
    params = StdioServerParameters(command=sys.executable, args=["-m", "contextfirewall_mcp"], env=child_env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            assert EXPECTED_TOOLS.issubset(set(tools)), tools
            print(f"PASS B1: MCP handshake OK, tools exposed = {tools}")

            res = await session.call_tool("get_trusted_context", {"task": "How do I deploy taskflow-api safely?"})
            text = "".join(getattr(c, "text", "") for c in res.content)
            assert "approved" in text and "blocked" in text, text[:300]
            print("PASS B2: get_trusted_context returns a live governed pack over MCP")
            print("---- live pack (first 240 chars) ----")
            print(text[:240])


if __name__ == "__main__":
    part_a_write_path()
    asyncio.run(part_b_protocol())
    print("\nALL MCP TESTS PASSED")
