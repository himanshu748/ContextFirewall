"""Fast deployment-setting regression tests without managed storage."""
from __future__ import annotations

import pytest

from app.deployment import api_key_db_ssl_mode, cors_allowed_origins


def test_cors_default_keeps_public_demo(monkeypatch):
    monkeypatch.delenv("CF_CORS_ORIGINS", raising=False)
    assert cors_allowed_origins() == ["*"]


def test_cors_explicit_origins_trim_and_deduplicate(monkeypatch):
    monkeypatch.setenv(
        "CF_CORS_ORIGINS",
        " https://console.example.com, http://localhost:3000,https://console.example.com ",
    )
    assert cors_allowed_origins() == ["https://console.example.com", "http://localhost:3000"]


def test_cors_explicit_empty_disables_cross_origin(monkeypatch):
    monkeypatch.setenv("CF_CORS_ORIGINS", " ")
    assert cors_allowed_origins() == []


def test_db_ssl_mode_default_and_local_override(monkeypatch):
    monkeypatch.delenv("CF_DB_SSLMODE", raising=False)
    assert api_key_db_ssl_mode() == "require"
    monkeypatch.setenv("CF_DB_SSLMODE", " disable ")
    assert api_key_db_ssl_mode() == "disable"
    monkeypatch.setenv("CF_DB_SSLMODE", "VERIFY-FULL")
    assert api_key_db_ssl_mode() == "verify-full"


@pytest.mark.parametrize("mode", ["", "not-tls", "none", "false"])
def test_invalid_db_ssl_modes_fail_closed(mode):
    with pytest.raises(ValueError, match="CF_DB_SSLMODE"):
        api_key_db_ssl_mode(mode)
