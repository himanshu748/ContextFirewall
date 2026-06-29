"""The four ContextFirewall audit checks.

Each check inspects one candidate memory (some also against the recalled cluster
of related memories) and returns a CheckOutcome. A memory must pass all four to
enter the trusted context pack.

  - secret        : pure, deterministic (secrets.py)
  - staleness      : temporal supersession within the cluster (a newer value exists)
  - contradiction  : LLM adjudication vs. established peers, deterministic fallback
  - evidence       : trust score + evidence linkage

Severity ``block`` fails the memory; ``info`` passes.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.cognee_runtime.llm import chat_json
from app.firewall.secrets import find_secrets

MIN_TRUST = 0.40
VERY_LOW_TRUST = 0.30


@dataclass
class CheckOutcome:
    check: str
    passed: bool
    reason: str
    severity: str = "info"  # info | warn | block


# --- helpers ------------------------------------------------------------------
def _parse_date(value: Optional[str]) -> Optional[_dt.datetime]:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip().replace("Z", "+00:00")
    for candidate in (raw, raw[:19], raw[:10]):
        try:
            return _dt.datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _date_key(value: Optional[str]) -> _dt.datetime:
    return _parse_date(value) or _dt.datetime.min


def _is_newer(a: Optional[str], b: Optional[str]) -> bool:
    da, db = _parse_date(a), _parse_date(b)
    if da is None or db is None:
        return False
    return da > db


def _short(text: Optional[str], n: int = 90) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def _dated(mem: Dict[str, Any]) -> str:
    return f", {mem['created_at']}" if mem.get("created_at") else ""


def _authority(mem: Dict[str, Any]) -> tuple:
    """Rank a memory's authority: trust, then evidence count, then recency."""
    return (
        round(float(mem.get("trust_score", 0.5) or 0.0), 3),
        len(mem.get("evidence_event_ids") or []),
        _date_key(mem.get("created_at")),
    )


def _same_subject_peers(mem: Dict[str, Any], cluster: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    subj = (mem.get("subject") or "").strip().lower()
    if not subj:
        return []
    peers = []
    for other in cluster:
        if other.get("memory_id") == mem.get("memory_id"):
            continue
        if (other.get("subject") or "").strip().lower() == subj:
            peers.append(other)
    return peers


# --- check 1: secret ----------------------------------------------------------
def secret_check(mem: Dict[str, Any]) -> CheckOutcome:
    findings = find_secrets(mem.get("text", ""))
    if findings:
        preview = "; ".join(f"{f.label} ({f.redacted})" for f in findings[:3])
        return CheckOutcome(
            "secret",
            False,
            f"Leaked credential blocked: {preview}. Secrets must never enter a context pack.",
            "block",
        )
    return CheckOutcome("secret", True, "No credentials detected.", "info")


# --- check 2: staleness -------------------------------------------------------
def staleness_check(mem: Dict[str, Any], cluster: List[Dict[str, Any]]) -> CheckOutcome:
    peers = _same_subject_peers(mem, cluster)
    newer = [p for p in peers if _is_newer(p.get("created_at"), mem.get("created_at"))]
    if newer:
        latest = max(newer, key=lambda x: _date_key(x.get("created_at")))
        return CheckOutcome(
            "staleness",
            False,
            f"Stale: superseded by a newer value for “{mem.get('subject')}”: "
            f"“{_short(latest.get('text'))}”{_dated(latest)}.",
            "block",
        )
    return CheckOutcome("staleness", True, "Current: no newer value on this subject.", "info")


# --- check 3: contradiction (LLM-adjudicated) ---------------------------------
async def contradiction_check(
    mem: Dict[str, Any],
    cluster: List[Dict[str, Any]],
    *,
    use_llm: bool = True,
) -> CheckOutcome:
    # Only adjudicate memories that share a subject. A strictly-newer peer is a
    # temporal supersession (staleness's job), so drop those. Critically, a memory
    # is only *contradicted* if a MORE-authoritative peer disagrees, the winner of
    # a conflict passes, only the weaker side is blocked.
    peers = _same_subject_peers(mem, cluster)
    peers = [p for p in peers if not _is_newer(p.get("created_at"), mem.get("created_at"))]
    stronger = [p for p in peers if _authority(p) > _authority(mem)]
    if not stronger:
        return CheckOutcome("contradiction", True, "No more-authoritative conflicting memory.", "info")

    if use_llm:
        verdict = await _llm_contradiction(mem, stronger)
        if verdict is not None:
            return verdict

    # Deterministic fallback: a clearly stronger same-subject peer with a different claim.
    diff = [
        p
        for p in stronger
        if (p.get("text") or "").strip() != (mem.get("text") or "").strip()
        and float(p.get("trust_score", 0.5)) >= float(mem.get("trust_score", 0.5)) + 0.15
    ]
    if diff and float(mem.get("trust_score", 0.5)) < 0.6:
        winner = max(diff, key=_authority)
        return CheckOutcome(
            "contradiction",
            False,
            f"Contradicted by a better-supported memory: “{_short(winner.get('text'))}” "
            f"(trust {float(winner.get('trust_score', 0)):.2f} vs {float(mem.get('trust_score', 0)):.2f}).",
            "block",
        )
    return CheckOutcome("contradiction", True, "No contradiction with established memories.", "info")


async def _llm_contradiction(
    mem: Dict[str, Any], peers: List[Dict[str, Any]]
) -> Optional[CheckOutcome]:
    peer_lines = "\n".join(
        f'- id={p.get("memory_id")} trust={float(p.get("trust_score", 0)):.2f} '
        f'date={p.get("created_at")}: "{_short(p.get("text"), 160)}"'
        for p in peers[:6]
    )
    system = (
        "You audit memories for an AI coding agent. Decide whether the CANDIDATE memory is "
        "directly CONTRADICTED by any ESTABLISHED memory (states something logically "
        "incompatible, not merely different or more detailed). Prefer the memory backed by "
        "more evidence/higher trust. Respond ONLY with compact JSON: "
        '{"contradicted": true|false, "by_memory_id": "<id>"|null, "reason": "<short reason>"}.'
    )
    user = (
        f'CANDIDATE (id={mem.get("memory_id")}, trust={float(mem.get("trust_score", 0)):.2f}, '
        f'date={mem.get("created_at")}): "{_short(mem.get("text"), 160)}"\n\n'
        f"ESTABLISHED:\n{peer_lines}"
    )
    data = await chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        default={},
        max_tokens=200,
    )
    if not data:
        return None  # LLM unavailable -> caller uses deterministic fallback
    if data.get("contradicted") is True:
        reason = str(data.get("reason") or "Contradicted by an established memory.").replace(" \u2014 ", ": ").replace("\u2014", ", ")  # keep reasons em-dash-free
        return CheckOutcome("contradiction", False, f"Contradiction: {reason}", "block")
    return CheckOutcome("contradiction", True, "No contradiction (LLM-adjudicated).", "info")


# --- check 4: evidence / trust ------------------------------------------------
def evidence_check(mem: Dict[str, Any], *, min_trust: float = MIN_TRUST) -> CheckOutcome:
    trust = float(mem.get("trust_score", 0.5) or 0.0)
    has_evidence = bool(mem.get("evidence_event_ids"))
    if trust < VERY_LOW_TRUST:
        return CheckOutcome(
            "evidence",
            False,
            f"Unsupported: trust {trust:.2f} is below {VERY_LOW_TRUST:.2f}; not enough support to pass.",
            "block",
        )
    if trust < min_trust and not has_evidence:
        return CheckOutcome(
            "evidence",
            False,
            f"Unsupported: trust {trust:.2f} < {min_trust:.2f} and no evidence recorded in the session.",
            "block",
        )
    detail = f"trust {trust:.2f}" + (", evidence linked" if has_evidence else "")
    return CheckOutcome("evidence", True, f"Supported ({detail}).", "info")
