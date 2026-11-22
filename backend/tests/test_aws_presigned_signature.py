"""Regressions for redaction of hex-only AWS SigV4 presigned URL signatures."""

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


def test_aws_sigv4_presigned_query_signature_is_redacted():
    signature = "a1" * 32  # Synthetic 64-hex signature, never a credential.
    url = (
        "https://example-bucket.s3.amazonaws.com/object?"
        "X-Amz-Algorithm=AWS4-HMAC-SHA256&"
        "X-Amz-Signature=" + signature + "&X-Amz-Expires=60"
    )
    findings = find_secrets(url)
    assert len(findings) == 1
    assert findings[0].kind == "aws_presigned_signature"
    redacted = redact_text(url)
    assert "X-Amz-Signature=«REDACTED:aws_presigned_signature»&" in redacted
    assert signature not in redacted
    assert redacted_kinds(redacted) == ["aws_presigned_signature"]
    assert not has_secret(redacted)
    assert redact_text(redacted) == redacted


def test_aws_sigv4_signature_requires_exact_hex_and_identifier_boundary():
    valid = "ab" * 32
    for invalid in (
        "X-Amz-Signature=" + "a" * 63,
        "X-Amz-Signature=" + "a" * 65,
        "X-Amz-Signature=" + "z" * 64,
        "X-Amz-Signature=" + valid + "_suffix",
        "X-Amz-SignedHeaders=host",
        "Ordinary commit SHA " + "a" * 40,
    ):
        assert not has_secret(invalid), invalid[:90]


def test_aws_sigv4_signature_match_is_case_insensitive():
    raw = "https://example.com/?x-amz-signature=" + "f" * 64
    assert "aws_presigned_signature" in [f.kind for f in find_secrets(raw)]
