"""Short database URI passwords must not bypass shared-memory redaction."""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, redact_text


def test_database_uri_passwords_of_one_or_two_characters_are_redacted():
    uris = [
        "postgres://app:p@db.example/test",
        "postgresql://app:xy@db.example/test",
        "mysql://user:1@db.example",
        "mongodb+srv://app:a@cluster.example/test",
        "redis://app:ab@cache.example",
        "neo4j+s://neo:p@graph.example",
    ]
    for uri in uris:
        matches = find_secrets(uri)
        assert [finding.kind for finding in matches] == ["connection_uri_password"]
        assert has_secret(uri)
        redacted = redact_text(uri)
        assert uri not in redacted
        assert "«REDACTED:connection_uri_password»" in redacted
        assert not has_secret(redacted)
        assert redact_text(redacted) == redacted


def test_missing_password_and_unrelated_urls_are_not_database_passwords():
    for text in [
        "postgres://app@db.example/test",
        "postgres://app:@db.example/test",
        "postgres://host.example/test",
        "https://user:p@public.example/",
    ]:
        assert all(f.kind != "connection_uri_password" for f in find_secrets(text))
