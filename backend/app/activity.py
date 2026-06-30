"""A tiny in-memory activity log of firewall calls (for the live console feed).

Every governed operation, whether it arrives over MCP or the REST API, appends a
one-line, secret-free entry here. The console polls /activity to show, in real time,
that real agents and clients are exercising the firewall. This is observability only:
it never affects a verdict, and it is best-effort (failures are swallowed).

It is a process-local ring buffer (the demo Space runs a single worker), not durable
storage, so it resets on restart. No memory text or secrets are recorded, only short
summaries built from counts and ids.
"""
from __future__ import annotations

import itertools
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List

_MAX = 60
_events: Deque[Dict[str, Any]] = deque(maxlen=_MAX)
_counter = itertools.count(1)


def log_activity(source: str, tool: str, detail: str) -> None:
    """Record one firewall call. ``source`` is "mcp" or "api"; ``tool`` is the verb/tool."""
    try:
        _events.appendleft(
            {
                "id": next(_counter),
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": source,
                "tool": tool,
                "detail": (detail or "")[:160],
            }
        )
    except Exception:  # noqa: BLE001 — observability must never break a request
        pass


def get_activity(limit: int = 40) -> List[Dict[str, Any]]:
    return list(itertools.islice(_events, 0, max(0, limit)))
