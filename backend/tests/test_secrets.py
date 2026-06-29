"""Unit tests for the firewall secret detector. Pure-Python, no network/cognee.

All "secrets" below are synthetic, non-functional placeholders — never real keys.
"""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, redact_text


# --- positives: each should be detected ---------------------------------------
def test_detects_huggingface_token():
    f = find_secrets("set HUGGINGFACE_API_KEY to hf_ABCdef0123456789ABCDEFGHIJ before deploy")
    assert any(x.kind == "huggingface_token" for x in f)


def test_detects_openai_key():
    assert has_secret("the key was sk-proj-AbCd1234EfGh5678IjKl9012MnOp")


def test_detects_postgres_uri_password():
    text = "DATABASE_URL=postgresql://postgres:S3cretP%40ss@db.abcdefgh.supabase.co:5432/postgres"
    f = find_secrets(text)
    assert any(x.kind == "connection_uri_password" for x in f)


def test_detects_neo4j_uri_password():
    assert has_secret("neo4j+s://neo4j:my-aura-password@abcd1234.databases.neo4j.io")


def test_detects_inline_secret_assignment():
    f = find_secrets('config: password = "hunter2-very-secret"')
    assert any(x.kind == "secret_assignment" for x in f)


def test_detects_private_key_block():
    assert has_secret("-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQ...")


# --- redaction never leaks the value -----------------------------------------
def test_redaction_hides_value():
    raw = "token hf_ABCdef0123456789ABCDEFGHIJ here"
    red = redact_text(raw)
    assert "hf_ABCdef0123456789ABCDEFGHIJ" not in red
    assert "REDACTED" in red
    # finding preview is also redacted
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
        except AssertionError as e:  # noqa: PERF203
            failed += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
