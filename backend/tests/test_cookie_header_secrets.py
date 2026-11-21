"""Regression tests for low-entropy session credentials in HTTP headers."""
from __future__ import annotations

import pytest

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


@pytest.mark.parametrize("header", [
    "Cookie: session=abc123; csrf=xyz789",
    "set-cookie: sid=abc123; HttpOnly; SameSite=Strict",
    "  Cookie: bearer=lowentropy",
])
def test_cookie_headers_are_fully_redacted(header: str):
    raw = "before\n" + header + "\nafter"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "http_cookie_header"
    assert findings[0].redacted == "***"  # do not preview cookie fragments
    sanitized = redact_text(raw)
    assert sanitized == "before\n«REDACTED:http_cookie_header»\nafter"
    assert "abc123" not in sanitized
    assert redacted_kinds(sanitized) == ["http_cookie_header"]
    assert not has_secret(sanitized)


@pytest.mark.parametrize("ordinary", [
    "Cookie: oatmeal raisin",
    "Set-Cookie: not a header value",
    "Use cookies for this feature",
    "The example says Cookie: session=abc123",
    "X-Cookie: session=abc123",
])
def test_non_header_prose_is_preserved(ordinary: str):
    assert not find_secrets(ordinary)
    assert redact_text(ordinary) == ordinary
