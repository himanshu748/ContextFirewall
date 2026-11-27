"""Verify Sentry sntryu_-prefixed user auth tokens; no secret-shaped literals are committed."""
from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_sentryuser_key_is_detected_and_redacted():
    token = "sntryu_" + "a1" * 32
    for text in (token, f"credential: {token}"):
        found = find_secrets(text)
        assert [item.kind for item in found] == ["sentry_user_token"]
        assert found[0].label == "Sentry user auth token"
        safe = redact_text(text)
        assert safe == text.replace(token, "«REDACTED:sentry_user_token»")
        assert token not in safe
        assert redacted_kinds(safe) == ["sentry_user_token"]
        assert not has_secret(safe)
    assert label_for_kind("sentry_user_token") == "Sentry user auth token"


def test_sentryuser_rejects_partial_and_embedded_values():
    token = "sntryu_" + "a1" * 32
    for value in ["sntryu_" + "a1" * 31, "sntryu_" + "z1" * 32, token + "_suffix"]:
        assert all(item.kind != "sentry_user_token" for item in find_secrets(value)), value[:80]
