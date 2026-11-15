"""Regression coverage for metadata secret redaction at ingest and graph reads."""
from __future__ import annotations

from app.cognee_runtime.graph import _safe_props
from app.cognee_runtime.ingest import _redact_session_secrets, build_nodes
from app.firewall.checks import secret_check


def test_ingest_redacts_all_session_strings_before_building_nodes():
    aws_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    github_key = "ghp_" + "Ab12" * 10
    session = {
        "session_id": "s1",
        "task": f"Inspect {aws_key}",
        "agent": f"agent {aws_key}",
        "started_at": "2026-06-01",
        "repo": {
            "name": f"repository {aws_key}",
            "url": f"https://user:{github_key}@github.com/example/repo",
            "description": f"contains {aws_key}",
        },
        "events": [{
            "event_id": "s1:e1", "kind": f"kind {aws_key}",
            "content": "sanitized event", "timestamp": "2026-06-01",
        }],
        "memories": [{
            "memory_id": "s1:m1", "text": "Ordinary fact",
            "subject": f"subject {aws_key}", "kind": "fact",
            "evidence_event_ids": ["s1:e1"],
        }],
        "metadata": {"nested": [f"note {github_key}"]},
    }
    memory_ref = session["memories"][0]

    _redact_session_secrets(session)

    assert aws_key not in repr(session)
    assert github_key not in repr(session)
    assert "REDACTED:" in session["repo"]["url"]
    assert "REDACTED:" in session["task"]
    assert "REDACTED:" in session["events"][0]["kind"]
    assert "REDACTED:" in memory_ref["subject"]
    assert "REDACTED:" in session["metadata"]["nested"][0]
    nodes, memories = build_nodes(session, namespace="tenant")
    assert aws_key not in repr(nodes)
    assert github_key not in repr(nodes)
    assert not secret_check({"text": memories[0].text, "subject": memories[0].subject}).passed


def test_graph_read_redacts_arbitrary_nested_string_properties():
    aws_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    props = {
        "type": "Repo", "task": f"inspect {aws_key}",
        "repo_url": f"https://user:{aws_key}@example.com/repo",
        "custom": ["ok", {"notes": aws_key}],
        "embedding": [0.1, 0.2],
    }

    cleaned = _safe_props(props)

    assert aws_key not in repr(cleaned)
    assert cleaned["custom"][0] == "ok"
    assert "REDACTED:" in cleaned["custom"][1]["notes"]
    assert "embedding" not in cleaned
    assert aws_key in props["task"]  # read-path defence does not mutate source data


def test_secret_check_blocks_redacted_subject_even_when_text_is_clean():
    assert not secret_check({
        "text": "A harmless command",
        "subject": "«REDACTED:aws_access_key»",
    }).passed
