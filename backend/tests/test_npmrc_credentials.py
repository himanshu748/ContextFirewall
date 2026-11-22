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


def test_quoted_npmrc_credentials_are_fully_redacted():
    # Both INI quoting styles can contain spaces and comment characters.
    value = "a" * 10 + " ;# !@?&=/+ (spaces) " + "b" * 10
    for name in ("_authToken", "_password"):
        for quote in ('"', "'"):
            raw = "//registry.npmjs.org/:" + name + "=" + quote + value + quote
            redacted = redact_text(raw)
            assert redacted == "//registry.npmjs.org/:«REDACTED:npmrc_auth»"
            assert value not in redacted
            assert [f.kind for f in find_secrets(raw)] == ["npmrc_auth"]
            assert not has_secret(redacted)


def test_escaped_quotes_and_inline_comments_keep_value_boundaries():
    # An escaped closing quote and embedded # / ; are part of the credential.
    for quote in ('"', "'"):
        value = quote + "a" * 8 + "\\" + quote + ";# !=? " + "b" * 8 + quote
        raw = "//registry.npmjs.org/:_authToken = " + value + "  # comment\nalways-auth=true"
        expected = "//registry.npmjs.org/:«REDACTED:npmrc_auth»  # comment\nalways-auth=true"
        assert redact_text(raw) == expected


def test_unquoted_npmrc_credential_redacts_punctuation_whitespace_and_escapes():
    value = "a" * 8 + " /?!=:@ (spaces) " + r"\#kept\;inside" + "b" * 8
    raw = "//registry.npmjs.org/:_password=" + value + "  ; comment\r\nalways-auth=true"
    expected = "//registry.npmjs.org/:«REDACTED:npmrc_auth»  ; comment\r\nalways-auth=true"
    assert redact_text(raw) == expected
    assert value not in redact_text(raw)


def test_unclosed_quoted_value_is_not_partially_redacted():
    raw = "//registry.npmjs.org/:_authToken=\"" + "a" * 12 + ";# rest of secret"
    assert redact_text(raw) == "//registry.npmjs.org/:«REDACTED:npmrc_auth»"


def test_bare_and_quoted_npmrc_environment_references_are_unchanged():
    variable = "$" + "{NPM_TOKEN}"
    optional_variable = "$" + "{CI_TOKEN?}"
    for name in ("_authToken", "_password"):
        for value in (variable, '"' + variable + '"', "'" + variable + "'", optional_variable):
            raw = "//registry.npmjs.org/:" + name + " = " + value + "  # reference"
            assert find_secrets(raw) == []
            assert redact_text(raw) == raw


def test_mixed_environment_reference_and_literal_is_redacted():
    variable = "$" + "{NPM_TOKEN}"
    raw = "//registry.npmjs.org/:_authToken=\"" + variable + "literal" + "\""
    assert redact_text(raw) == "//registry.npmjs.org/:«REDACTED:npmrc_auth»"
