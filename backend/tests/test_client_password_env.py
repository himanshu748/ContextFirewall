"""Standard client password environment variables require named redaction."""

from app.firewall.secrets import find_secrets, has_secret, redact_text


def test_database_client_env_passwords_redact_low_entropy_and_quoted_values():
    for line in (
        "PGPASSWORD=plain",
        "MYSQL_PWD='human readable value with spaces'",
        'REDISCLI_AUTH="another readable value"',
        "export PGPASSWORD=x",
    ):
        raw = line + "\nkeep=visible"
        redacted = redact_text(raw)
        assert any(f.kind == "service_password_env" for f in find_secrets(raw)), line
        assert redacted.endswith("«REDACTED:service_password_env»\nkeep=visible")
        assert not has_secret(redacted)


def test_truncated_env_password_quotes_do_not_expose_the_rest_of_the_value():
    raw = 'PGPASSWORD="a phrase without closing quote' + "\n" + "keep=visible"
    assert redact_text(raw) == "«REDACTED:service_password_env»\nkeep=visible"


def test_env_placeholders_and_nonmatching_variable_names_are_not_masked():
    for text in (
        "PGPASSWORD=${PGPASSWORD}",
        "MYSQL_PWD=${MYSQL_PWD}",
        "PREFIX_PGPASSWORD=plain",
        "PGPASSWORD_HINT=safe",
        "REDISCLI_AUTH=",
    ):
        assert all(f.kind != "service_password_env" for f in find_secrets(text)), text
