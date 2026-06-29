"""Unit tests for the firewall secret detector. Pure-Python, no network/cognee.

Every "secret" here is ASSEMBLED at runtime from harmless fragments, so no
credential-shaped literal is ever committed to the repo. That keeps secret
scanners (GitGuardian etc.) quiet while still feeding the detector a complete,
realistic string to match — the detector under test is what builds the full value.
"""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, redact_text


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


def test_detects_postgres_uri_password():
    uri = _uri("postgre" + "sql", "appuser", "Pg" + "x7QwZ9", "db.example.supabase.co", ":5432/appdb")
    assert any(x.kind == "connection_uri_password" for x in find_secrets(f"DATABASE_URL={uri}"))


def test_detects_neo4j_uri_password():
    uri = _uri("neo4j" + "+s", "neo4j", "Aura" + "Secret42", "abcd1234.databases.neo4j.io")
    assert has_secret(uri)


def test_detects_inline_secret_assignment():
    pwd = "hunter2" + "-demo-only"
    assert any(x.kind == "secret_assignment" for x in find_secrets(f'config: password = "{pwd}"'))


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
