from __future__ import annotations

import builtins
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.cognee_runtime import bootstrap


@pytest.fixture(autouse=True)
def _reset_configure_cache():
    bootstrap.configure_cognee.cache_clear()
    yield
    bootstrap.configure_cognee.cache_clear()


@pytest.fixture(autouse=True)
def _mock_cognee_import(monkeypatch, _reset_configure_cache, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(bootstrap, "ENV_PATH", env_path)
    monkeypatch.setenv("CF_DATA_DIR", str(tmp_path / "cf-data"))

    cognee = SimpleNamespace(config=Mock())
    original_import = builtins.__import__

    def import_with_dotenv_reload(
        name, globals=None, locals=None, fromlist=(), level=0
    ):
        if name == "cognee":
            bootstrap.load_dotenv(bootstrap.ENV_PATH, override=True)
            return cognee
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_dotenv_reload)
    monkeypatch.setattr(bootstrap, "_install_hf_router_embeddings", lambda **_: None)


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


@pytest.mark.parametrize(
    ("dotenv_line", "expected"),
    [
        ("TELEMETRY_DISABLED=0\n", None),
        ("TELEMETRY_DISABLED=\n", "1"),
        ('TELEMETRY_DISABLED="   "\n', "1"),
    ],
)
def test_dotenv_telemetry_setting_is_normalized_after_cognee_import(
    monkeypatch, tmp_path, dotenv_line, expected
):
    env_path = tmp_path / "telemetry.env"
    env_path.write_text(dotenv_line)
    monkeypatch.setattr(bootstrap, "ENV_PATH", env_path)
    monkeypatch.delenv("TELEMETRY_DISABLED", raising=False)

    bootstrap.configure_cognee()

    assert os.environ.get("TELEMETRY_DISABLED") == expected
