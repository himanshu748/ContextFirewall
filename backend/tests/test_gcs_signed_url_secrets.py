"""Regressions for Google Cloud Storage V4 signed URL redaction."""

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds


def test_gcs_signed_url_hmac_and_rsa_signatures_are_redacted():
    for signature in ("a1" * 32, "ab" * 256):
        raw = (
            "https://storage.googleapis.com/example-bucket/object?"
            "X-Goog-Algorithm=GOOG4-HMAC-SHA256&"
            "X-Goog-Signature=" + signature + "&X-Goog-Expires=600"
        )
        findings = find_secrets(raw)
        assert [f.kind for f in findings] == ["gcs_signed_url_signature"]
        redacted = redact_text(raw)
        assert "X-Goog-Signature=«REDACTED:gcs_signed_url_signature»&" in redacted
        assert signature not in redacted
        assert redacted_kinds(redacted) == ["gcs_signed_url_signature"]
        assert redact_text(redacted) == redacted
        assert not has_secret(redacted)


def test_gcs_signed_url_signature_requires_hex_boundary_and_length():
    signature = "a1" * 32
    for ordinary in (
        "X-Goog-Signature=" + "a" * 63,
        "X-Goog-Signature=" + "z" * 64,
        "X-Goog-Signature=" + signature + "_suffix",
        "X-Goog-Signature=" + "a" * 1025,
        "X-Goog-SignedHeaders=host",
        "commit " + "f" * 40,
    ):
        assert not has_secret(ordinary), ordinary[:85]


def test_gcs_signed_url_signature_case_insensitive():
    raw = "https://storage.googleapis.com/object?x-goog-signature=" + "b" * 64
    assert [f.kind for f in find_secrets(raw)] == ["gcs_signed_url_signature"]
