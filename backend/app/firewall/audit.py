"""Audit: run the four firewall checks over recalled candidate memories.

Returns a per-memory verdict (pass/block + the reason from each check). Memory
text is redacted on the way out so a leaked secret is never re-exposed to the UI.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.cognee_runtime.recall import recall_memory_candidates
from app.firewall.checks import (
    contradiction_check,
    evidence_check,
    secret_check,
    staleness_check,
)
from app.firewall.secrets import redact_text

# Order matters for the displayed block reason: secret first (most severe), then
# staleness, contradiction, evidence.
async def audit_cluster(
    query: str,
    cluster: List[Dict[str, Any]],
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    verdicts: List[Dict[str, Any]] = []
    for mem in cluster:
        outcomes = [
            secret_check(mem),
            staleness_check(mem, cluster),
            await contradiction_check(mem, cluster, use_llm=use_llm),
            evidence_check(mem),
        ]
        passed = all(o.passed for o in outcomes)
        blocking = next((o for o in outcomes if not o.passed), None)
        verdicts.append(
            {
                "memory_id": mem.get("memory_id"),
                "text": redact_text(mem.get("text", "")),
                "kind": mem.get("kind", "fact"),
                "subject": mem.get("subject"),
                "created_at": mem.get("created_at"),
                "trust_score": float(mem.get("trust_score", 0.0) or 0.0),
                "status": mem.get("status", "candidate"),
                "source_session_id": mem.get("source_session_id"),
                "evidence_event_ids": list(mem.get("evidence_event_ids") or []),
                "passed": passed,
                "checks": [vars(o) for o in outcomes],
                "block_reason": blocking.reason if blocking else None,
                "block_check": blocking.check if blocking else None,
            }
        )
    passed_count = sum(1 for v in verdicts if v["passed"])
    return {
        "query": query,
        "candidates": verdicts,
        "passed_count": passed_count,
        "blocked_count": len(verdicts) - passed_count,
    }


async def audit_memories(
    query: str,
    *,
    top_k: int = 12,
    use_llm: bool = True,
    namespaces=None,
) -> Dict[str, Any]:
    """Recall candidates from Cognee and audit them."""
    cluster = await recall_memory_candidates(query, top_k=top_k, namespaces=namespaces)
    return await audit_cluster(query, cluster, use_llm=use_llm)
