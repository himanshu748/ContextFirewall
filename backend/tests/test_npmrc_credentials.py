"""Redact credentials in .npmrc registry-specific configuration directives."""

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


def test_scoped_registry_auth_tokens_and_passwords_are_redacted():
    # Construct test-only values at runtime; never commit a credential-shaped
    # literal that generic password scanners can mistake for a live secret.
    for name, value in (("_authToken", "a" * 12), ("_password", "Q" * 12), ("_authToken", "x")):
        raw = "//registry.npmjs.org/:" + name + "=" + value + "\nalways-auth=true"
        redacted = redact_text(raw)
        assert redacted == "//registry.npmjs.org/:«REDACTED:npmrc_auth»\nalways-auth=true"
        assert any(f.kind == "npmrc_auth" for f in find_secrets(raw))
        assert redacted_kinds(redacted) == ["npmrc_auth"]
        assert not has_secret(redacted)


def test_registry_auth_placeholder_and_similarly_named_fields_are_not_secrets():
    for value in (
        "_authToken=${NPM_TOKEN}",
        "prefix_authToken=aaaaaaaaaaaa",
        "_authToken=",
        "_authToken=${CI_SECRET}",
    ):
        assert all(f.kind != "npmrc_auth" for f in find_secrets(value)), value
