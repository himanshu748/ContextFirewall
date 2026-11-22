"""Low-entropy synthetic values must not bypass named credential assignments."""

from app.firewall.secrets import find_secrets, has_secret, redact_text


def test_aws_and_oauth_secret_assignments_are_masked():
    assignments = (
        "AWS_SECRET_ACCESS_KEY=aaaaaaaaaaaa",
        'AWS_SESSION_TOKEN="simple temporary session value"',
        "OAUTH_REFRESH_TOKEN='readable refresh value with spaces'",
        "SERVICE_API_TOKEN=bbbbbbbbbbbb",
    )
    for line in assignments:
        raw = line + "\nkeep=visible"
        findings = find_secrets(raw)
        assert any(f.kind == "secret_assignment" for f in findings), line
        assert redact_text(raw) == "«REDACTED:secret_assignment»\nkeep=visible"
        assert not has_secret(redact_text(raw))


def test_nonsecret_identifier_names_are_not_matched_as_assignments():
    for value in (
        "AWS_ACCESS_KEY_ID=not-a-secret",
        "AWS_SESSION_TOKEN_COUNT=4",
        "SERVICE_API_TOKEN_ENABLED=true",
    ):
        assert all(f.kind != "secret_assignment" for f in find_secrets(value))

def test_provider_token_assignments_are_masked_even_when_low_entropy():
    # These recognized provider variable names carry credentials, even when
    # their synthetic values are too short/simple for high-entropy detection.
    for line in (
        "GITHUB_TOKEN=simplevalue",
        'GITLAB_TOKEN="temporary readable value"',
        "SLACK_TOKEN='sample credential'",
        "HF_TOKEN=localexample",
        "NPM_TOKEN=example123",
    ):
        raw = line + "\nkeep=visible"
        findings = find_secrets(raw)
        assert any(f.kind == "secret_assignment" for f in findings), line
        assert redact_text(raw) == "«REDACTED:secret_assignment»\nkeep=visible"
        assert not has_secret(redact_text(raw))

    for ordinary in (
        "GITHUB_TOKEN_COUNT=4",
        "SLACK_TOKEN_ENABLED=true",
        "The NPM_TOKEN variable is required",
    ):
        assert all(f.kind != "secret_assignment" for f in find_secrets(ordinary))

