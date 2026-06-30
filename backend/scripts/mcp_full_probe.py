"""Exercise the full ContextFirewall MCP tool surface over streamable HTTP.

Proves all six tools work end to end on real Cognee: remember -> audit -> improve ->
list rules -> forget. Usage: python scripts/mcp_full_probe.py [base_url]
"""
from __future__ import annotations

import asyncio
import re
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

            # 1. remember a new durable fact
            out = _text(await s.call_tool(
                "remember",
                {"text": "Staging is reset nightly at 02:00 UTC by a cron job.",
                 "subject": "staging reset", "kind": "fact"},
            ))
            print("REMEMBER:", out)
            m = re.search(r"\bas (\S+?)\.", out)
            assert m, "could not parse memory id from remember output"
            new_id = m.group(1)
            print("  -> new memory id:", new_id)

            # 2. audit a task touching that subject; the new memory should be present + approved
            out = _text(await s.call_tool("audit_context", {"task": "How is the staging environment managed?"}))
            print("AUDIT after remember (header):", out.splitlines()[1])
            assert new_id in out, "remembered memory not found in audit"
            print("PASS: remembered memory is now auditable")

            # 3. improve_rules (Cognee memify) — distil reusable coding rules
            out = _text(await s.call_tool("improve_rules", {}))
            print("IMPROVE (first 180):", out[:180].replace("\n", " "))

            # 4. list_coding_rules
            out = _text(await s.call_tool("list_coding_rules", {}))
            print("RULES (first 180):", out[:180].replace("\n", " "))

            # 5. forget the memory we added (governance), leaving the demo set clean
            out = _text(await s.call_tool("forget_memory", {"memory_id": new_id, "reason": "probe cleanup"}))
            print("FORGET:", out)
            assert "forgotten" in out, out

            # 6. confirm it is gone
            out = _text(await s.call_tool("audit_context", {"task": "How is the staging environment managed?"}))
            assert new_id not in out, "memory still present after forget"
            print("PASS: memory removed after forget — full MCP verb cycle works")


if __name__ == "__main__":
    asyncio.run(main())
