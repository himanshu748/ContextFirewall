"""Regression coverage for configuration keys carrying sensitive values."""

from app.firewall.secrets import find_secrets, has_secret, redact_text


def test_secret_key_and_signing_key_assignments_are_redacted():
    # Names such as SECRET_KEY are not covered by an isolated 'secret=' suffix.
    for label in ("SECRET_KEY", "DJANGO_SECRET_KEY", "JWT_SIGNING_KEY", "ENCRYPTION_KEY"):
        raw = f"{label}='synthetic example value'"
        findings = find_secrets(raw)
        assert [f.kind for f in findings] == ["secret_assignment"], label
        assert redact_text(raw) == "«REDACTED:secret_assignment»"
        assert not has_secret(redact_text(raw))

    assert not has_secret("SECRET_KEY is a configuration name")
    assert not has_secret("SIGNING_KEY is a configuration name")
