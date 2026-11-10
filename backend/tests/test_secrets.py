"""Unit tests for the firewall secret detector. Pure-Python, no network/cognee.

Every "secret" here is ASSEMBLED at runtime from harmless fragments, so no
credential-shaped literal is ever committed to the repo. That keeps secret
scanners (GitGuardian etc.) quiet while still feeding the detector a complete,
realistic string to match — the detector under test is what builds the full value.
"""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds, label_for_kind


def _uri(scheme: str, user: str, pwd: str, host: str, tail: str = "") -> str:
    """Assemble a connection URI from fragments so no full credential-URI literal is committed."""
    return scheme + "://" + user + ":" + pwd + "@" + host + tail


# --- positives: each should be detected (values assembled at runtime) ---------
def test_detects_huggingface_token():
    tok = "hf_" + "ABCdef0123456789ABCDEFGHIJ"
    assert any(x.kind == "huggingface_token" for x in find_secrets(f"set the key to {tok} first"))


def test_detects_openai_key():
    key = "sk-" + "proj-" + "AbCd1234EfGh5678IjKl9012MnOp"
    assert has_secret(f"the key was {key}")


def test_detects_and_redacts_gitlab_access_token():
    token = "glpat-" + "Ab12" * 5  # Deliberately synthetic; no usable credentials.
    findings = find_secrets(f"GITLAB_TOKEN={token}")
    assert len(findings) == 1
    assert findings[0].kind == "gitlab_token"
    assert token not in findings[0].redacted
    redacted = redact_text(f"GITLAB_TOKEN={token}")
    assert token not in redacted
    assert redacted_kinds(redacted) == ["gitlab_token"]
    assert label_for_kind("gitlab_token") == "GitLab access token"


def test_gitlab_prefix_without_a_full_token_is_not_a_secret():
    assert not has_secret("glpat-" + "a" * 19)


def test_detects_and_redacts_sendgrid_api_key():
    # Assemble a synthetic key from fragments to avoid committed credentials.
    key = "SG." + "Ab3_" * 5 + "Q-" + "." + "Cd4-" * 10 + "x_7"
    raw = f"SendGrid credential: {key}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "sendgrid_api_key"
    assert key not in findings[0].redacted
    redacted = redact_text(raw)
    assert redacted == "SendGrid credential: «REDACTED:sendgrid_api_key»"
    assert key not in redacted
    assert redacted_kinds(redacted) == ["sendgrid_api_key"]
    assert label_for_kind("sendgrid_api_key") == "SendGrid API key"


def test_sendgrid_incomplete_or_extended_key_is_not_a_secret():
    assert not has_secret("SendGrid is a service, not a credential")
    assert not has_secret("SG." + "A" * 21 + "." + "B" * 43)
    assert not has_secret("SG." + "A" * 22 + "." + "B" * 42)
    assert not has_secret("SG." + "A" * 22 + "." + "B" * 44)


def test_detects_and_redacts_npm_access_token():
    # Synthetic fragments: no credential-shaped token literal is committed.
    token = "npm_" + "Ab3x" * 9
    raw = f"Use this npm credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "npm_token"
    assert token not in findings[0].redacted
    redacted = redact_text(raw)
    assert redacted == "Use this npm credential: «REDACTED:npm_token»"
    assert token not in redacted
    assert redacted_kinds(redacted) == ["npm_token"]
    assert label_for_kind("npm_token") == "npm access token"


def test_npm_prose_and_wrong_length_tokens_are_not_flagged():
    assert not has_secret("Run npm install before npm test")
    assert not has_secret("npm_" + "A" * 35)
    assert not has_secret("npm_" + "A" * 37)
    assert not has_secret("notnpm_" + "A" * 36)


def test_detects_stripe_live_secret_and_restricted_keys_without_leaking():
    for prefix in ("sk_live_", "rk_live_"):
        fake_value = prefix + "A" * 24  # Synthetic fixture, no live credentials.
        findings = find_secrets(f"payment processor key: {fake_value}")
        assert len(findings) == 1
        assert findings[0].kind == "stripe_live_key"
        assert fake_value not in findings[0].redacted
        redacted = redact_text(f"payment processor key: {fake_value}")
        assert fake_value not in redacted
        assert redacted_kinds(redacted) == ["stripe_live_key"]
    assert label_for_kind("stripe_live_key") == "Stripe live secret or restricted key"


def test_stripe_public_and_short_keys_are_not_flagged():
    assert not has_secret("pk_live_" + "A" * 24)  # Publishable, not a secret.
    assert not has_secret("sk_live_" + "A" * 15)  # Too short to be a key.
    assert not has_secret("rk_test_" + "A" * 24)  # Only live keys in this scope.


def test_detects_postgres_uri_password():
    uri = _uri("postgre" + "sql", "appuser", "Pg" + "x7QwZ9", "db.example.supabase.co", ":5432/appdb")
    assert any(x.kind == "connection_uri_password" for x in find_secrets(f"DATABASE_URL={uri}"))


def test_detects_neo4j_uri_password():
    uri = _uri("neo4j" + "+s", "neo4j", "Aura" + "Secret42", "abcd1234.databases.neo4j.io")
    assert has_secret(uri)


def test_detects_inline_secret_assignment():
    pwd = "hunter2" + "-demo-only"
    assert any(x.kind == "secret_assignment" for x in find_secrets(f'config: password = "{pwd}"'))


def test_detects_provider_prefixed_secret_assignments():
    # Hexadecimal auth tokens are not reliably detected by the entropy fallback.
    fake_twilio_token = "a1b2c3d4" * 4
    for key, value in [
        ("TWILIO_AUTH_TOKEN", fake_twilio_token),
        ("DB_PASSWORD", "fake-secret-12345"),
        ("OPENAI_API_KEY", "example-placeholder-key-123"),
        ("PAYMENTS_CLIENT_SECRET", "not-a-real-secret-987"),
    ]:
        raw = f"{key}={value}"
        findings = find_secrets(raw)
        assert any(f.kind == "secret_assignment" for f in findings), key
        assert value not in redact_text(raw), key
        assert redact_text(raw) == "«REDACTED:secret_assignment»", key


def test_provider_prefixed_assignment_negatives():
    for ordinary in [
        "GIT_COMMIT_SHA=" + "a1b2c3d4" * 4,
        "FEATURE_FLAG_ENABLED=abcdefgh12345678",
        "SECRET_HINT=not-a-credential",
        "myapisecret=just-a-description",
        "PAYMENTS_CLIENT_SECRET_HINT=use-the-vault",
    ]:
        assert not has_secret(ordinary), ordinary


def test_detects_private_key_block():
    header = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
    assert has_secret(header + "\nMIIEog...")


# --- redaction never leaks the value -----------------------------------------
def test_redaction_hides_value():
    tok = "hf_" + "ABCdef0123456789ABCDEFGHIJ"
    raw = f"token {tok} here"
    red = redact_text(raw)
    assert tok not in red
    assert "REDACTED" in red
    for f in find_secrets(raw):
        assert "0123456789" not in f.redacted


# --- negatives: should NOT be flagged ----------------------------------------
def test_ignores_plain_prose():
    assert not has_secret("The deploy command changed from make deploy-v1 to make deploy-v2.")


def test_ignores_git_sha():
    # 40-char hex commit sha — lowercase+digit only, must not trip the entropy fallback
    assert not has_secret("fixed in commit c5e8b8dc4c7d4ba81b1d9ad9450b01217a28c093 on dev")


def test_ignores_uuid():
    assert not has_secret("session id 9f8b7c6d-5e4f-3a2b-1c0d-abcdef012345 recorded")


if __name__ == "__main__":  # allow running without pytest
    import sys

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
