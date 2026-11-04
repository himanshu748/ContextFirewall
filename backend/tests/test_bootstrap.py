from __future__ import annotations

import os

import pytest

from app.cognee_runtime import bootstrap


@pytest.fixture(autouse=True)
def _reset_configure_cache():
    bootstrap.configure_cognee.cache_clear()
    yield
    bootstrap.configure_cognee.cache_clear()


def test_telemetry_disabled_by_default(monkeypatch):
    # The README promises local-first; Cognee telemetry must be off unless
    # the user explicitly opts in (#47).
    monkeypatch.delenv("TELEMETRY_DISABLED", raising=False)
    bootstrap.configure_cognee()
    assert os.environ.get("TELEMETRY_DISABLED") == "1"


def test_telemetry_explicit_disable_is_kept(monkeypatch):
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")
    bootstrap.configure_cognee()
    assert os.environ.get("TELEMETRY_DISABLED") == "1"


def test_telemetry_explicit_opt_in_is_honoured(monkeypatch):
    # Cognee treats ANY non-empty TELEMETRY_DISABLED value as "disabled",
    # so opting in (0/false/no/off) must remove the flag entirely —
    # otherwise the opt-in would silently do nothing.
    monkeypatch.setenv("TELEMETRY_DISABLED", "0")
    bootstrap.configure_cognee()
    assert not os.getenv("TELEMETRY_DISABLED")
