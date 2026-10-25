"""Unit tests for the four firewall checks (deterministic; no network/cognee).

contradiction_check is exercised via its no-LLM fallback (use_llm=False) so these
stay fast and offline. The live LLM adjudication is covered by the integration run.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from app.firewall.checks import (
    _authority,
    _date_key,
    _parse_date,
    contradiction_check,
    evidence_check,
    secret_check,
    staleness_check,
)


def _run(coro):
    return asyncio.run(coro)


# --- dates --------------------------------------------------------------------
def test_parse_date_normalizes_offsets_and_date_only_values_to_utc():
    utc = dt.timezone.utc
    assert _parse_date("2026-06-01T10:00:00Z") == dt.datetime(
        2026, 6, 1, 10, tzinfo=utc
    )
    assert _parse_date("2026-06-01T10:00:00+05:30") == dt.datetime(
        2026, 6, 1, 4, 30, tzinfo=utc
    )
    assert _parse_date("2026-02-01") == dt.datetime(2026, 2, 1, tzinfo=utc)
    assert _parse_date(None) is None


def test_date_key_uses_aware_minimum_for_missing_dates():
    assert _date_key(None) == dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def test_authority_sorts_mixed_timestamp_formats_by_utc_instant():
    memories = [
        {"created_at": "2026-06-01T10:00:00Z", "trust_score": 0.8},
        {"created_at": "2026-06-01T10:00:00+05:30", "trust_score": 0.8},
        {"created_at": "2026-06-01", "trust_score": 0.8},
        {"created_at": None, "trust_score": 0.8},
    ]

    ordered = sorted(memories, key=_authority)

    assert [memory["created_at"] for memory in ordered] == [
        None,
        "2026-06-01",
        "2026-06-01T10:00:00+05:30",
        "2026-06-01T10:00:00Z",
    ]


# --- secret -------------------------------------------------------------------
def test_secret_blocks_leaked_key():
    tok = "hf_" + "ABCdef0123456789ABCDEFGHIJ"  # assembled — no literal token in source
    out = secret_check({"text": f"key is {tok} ok"})
    assert not out.passed and out.check == "secret"


def test_secret_passes_clean_text():
    assert secret_check({"text": "deploy with make release"}).passed


# --- staleness ----------------------------------------------------------------
def test_staleness_blocks_when_newer_value_exists():
    old = {"memory_id": "a", "subject": "deploy command", "created_at": "2026-06-20", "text": "use v1"}
    new = {"memory_id": "b", "subject": "deploy command", "created_at": "2026-06-28", "text": "use v2"}
    out = staleness_check(old, [old, new])
    assert not out.passed and out.check == "staleness"


def test_staleness_passes_for_newest():
    old = {"memory_id": "a", "subject": "deploy command", "created_at": "2026-06-20", "text": "use v1"}
    new = {"memory_id": "b", "subject": "deploy command", "created_at": "2026-06-28", "text": "use v2"}
    assert staleness_check(new, [old, new]).passed


def test_staleness_passes_without_subject():
    m = {"memory_id": "a", "subject": None, "created_at": "2026-06-20", "text": "x"}
    assert staleness_check(m, [m]).passed


def test_staleness_handles_mixed_formats_offsets_and_missing_dates():
    old = {
        "memory_id": "old",
        "subject": "release",
        "created_at": "2026-02-01",
        "text": "v1",
    }
    newer = {
        "memory_id": "new",
        "subject": "release",
        "created_at": "2026-06-01T10:00:00Z",
        "text": "v3",
    }
    offset = {
        "memory_id": "offset",
        "subject": "release",
        "created_at": "2026-06-01T10:00:00+05:30",
        "text": "v2",
    }
    undated = {
        "memory_id": "unknown",
        "subject": "release",
        "created_at": None,
        "text": "unknown",
    }

    cluster = [old, newer, offset, undated]
    assert not staleness_check(old, cluster).passed
    assert not staleness_check(offset, cluster).passed
    assert staleness_check(newer, cluster).passed
    assert staleness_check(undated, cluster).passed


# --- evidence -----------------------------------------------------------------
def test_evidence_blocks_unsupported_low_trust():
    out = evidence_check({"text": "claim", "trust_score": 0.1, "evidence_event_ids": []})
    assert not out.passed and out.check == "evidence"


def test_evidence_passes_supported():
    assert evidence_check({"text": "claim", "trust_score": 0.8, "evidence_event_ids": ["e1"]}).passed


def test_evidence_passes_midtrust_with_evidence():
    assert evidence_check({"text": "claim", "trust_score": 0.55, "evidence_event_ids": ["e1"]}).passed


# --- contradiction (deterministic fallback) -----------------------------------
def test_contradiction_fallback_blocks_lower_trust_peer():
    weak = {"memory_id": "a", "subject": "exit 137 cause", "created_at": "2026-06-29",
            "text": "it was OOM", "trust_score": 0.4}
    strong = {"memory_id": "b", "subject": "exit 137 cause", "created_at": "2026-06-29",
              "text": "it was a user interrupt", "trust_score": 0.85}
    out = _run(contradiction_check(weak, [weak, strong], use_llm=False))
    assert not out.passed and out.check == "contradiction"


def test_contradiction_passes_without_same_subject_peer():
    a = {"memory_id": "a", "subject": "topic A", "created_at": "2026-06-29", "text": "x", "trust_score": 0.4}
    b = {"memory_id": "b", "subject": "topic B", "created_at": "2026-06-29", "text": "y", "trust_score": 0.9}
    assert _run(contradiction_check(a, [a, b], use_llm=False)).passed


def test_contradiction_passes_for_stronger_memory():
    weak = {"memory_id": "a", "subject": "s", "created_at": "2026-06-29", "text": "p", "trust_score": 0.4}
    strong = {"memory_id": "b", "subject": "s", "created_at": "2026-06-29", "text": "q", "trust_score": 0.85}
    # the strong one should NOT be flagged
    assert _run(contradiction_check(strong, [weak, strong], use_llm=False)).passed


def test_contradiction_handles_mixed_formats_offsets_and_missing_dates():
    weak = {
        "memory_id": "weak",
        "subject": "release",
        "created_at": "2026-06-01T04:30:00Z",
        "text": "release v1",
        "trust_score": 0.4,
    }
    equally_recent = {
        "memory_id": "strong",
        "subject": "release",
        "created_at": "2026-06-01T10:00:00+05:30",
        "text": "release v2",
        "trust_score": 0.85,
    }
    date_only = {
        "memory_id": "date-only",
        "subject": "release",
        "created_at": "2026-06-01",
        "text": "release v3",
        "trust_score": 0.8,
    }
    undated = {
        "memory_id": "undated",
        "subject": "release",
        "created_at": None,
        "text": "release v4",
        "trust_score": 0.7,
    }

    out = _run(
        contradiction_check(
            weak, [weak, equally_recent, date_only, undated], use_llm=False
        )
    )

    assert not out.passed and out.check == "contradiction"


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
