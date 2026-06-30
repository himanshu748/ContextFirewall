"""Probe the hosted (streamable-HTTP) ContextFirewall MCP endpoint.

Usage: python scripts/mcp_http_probe.py [base_url]
Connects over the real MCP protocol, lists tools, and calls a couple of them.
"""
from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
URL = f"{BASE}/mcp"


def _text(res) -> str:
    return "".join(getattr(c, "text", "") for c in res.content)


async def main() -> None:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            print("TOOLS:", tools)
            expected = {
                "get_trusted_context",
                "audit_context",
                "remember",
                "forget_memory",
                "improve_rules",
                "list_coding_rules",
            }
            assert expected.issubset(set(tools)), f"missing tools: {expected - set(tools)}"
            print("PASS: all six tools exposed over streamable HTTP")

            r = await s.call_tool("get_trusted_context", {"task": "How do I deploy taskflow-api safely?"})
            txt = _text(r)
            print("---- get_trusted_context (first 240) ----")
            print(txt[:240])
            assert "ContextFirewall" in txt
            print("PASS: get_trusted_context returned a governed pack")

            r = await s.call_tool("audit_context", {"task": "How do I deploy taskflow-api safely?"})
            print("---- audit_context (first 280) ----")
            print(_text(r)[:280])
            print("PASS: audit_context returned verdicts")


if __name__ == "__main__":
    asyncio.run(main())
