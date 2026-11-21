"""Check that low-entropy HTTP authentication credentials cannot enter context."""
from __future__ import annotations

import pytest

from app.firewall.secrets import find_secrets, has_secret, redact_text


@pytest.mark.parametrize("header", [
    "Authorization: Bearer abc123",
    "authorization: Basic dXNlcjpwYXNz",
    "Proxy-Authorization: Token shortvalue",
    "  Authorization: Bearer short",
])
def test_http_authorization_headers_are_redacted_without_preview(header: str):
    source = f"before\n{header}\nafter"
    findings = find_secrets(source)
    assert len(findings) == 1
    assert findings[0].kind == "http_authorization_header"
    assert findings[0].redacted == "***"
    clean = redact_text(source)
    assert clean == "before\n«REDACTED:http_authorization_header»\nafter"
    assert not has_secret(clean)


@pytest.mark.parametrize("ordinary", [
    "Authorization: use the configured policy",
    "Authorization: Bearer",
    "This sample mentions Authorization: Bearer abc123",
    "X-Authorization: Bearer abc123",
])
def test_non_header_prose_and_missing_tokens_are_not_flagged(ordinary: str):
    assert find_secrets(ordinary) == []
    assert redact_text(ordinary) == ordinary
