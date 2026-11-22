"""Mailchimp Marketing API credentials must not enter trusted agent memory."""
from __future__ import annotations

from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_mailchimp_keys_are_classified_and_redacted_without_leaking_the_value():
    # Entirely synthetic 32-hex key bodies with documented datacenter suffixes.
    for dc in ("us1", "us22", "us123"):
        token = "a0B1" * 8 + "-" + dc
        for input_text in (token, f"Mailchimp: {token}", f"Authorization: Basic {token}"):
            findings = find_secrets(input_text)
            assert len(findings) == 1
            assert findings[0].kind == "mailchimp_api_key"
            assert findings[0].label == "Mailchimp Marketing API key"
            masked = redact_text(input_text)
            assert masked == input_text.replace(token, "«REDACTED:mailchimp_api_key»")
            assert token not in masked
            assert redacted_kinds(masked) == ["mailchimp_api_key"]
            assert not has_secret(masked)
    assert label_for_kind("mailchimp_api_key") == "Mailchimp Marketing API key"


def test_mailchimp_key_near_misses_are_not_mistyped_as_credentials():
    value = "a0B1" * 8 + "-us22"
    for non_key in (
        "A Mailchimp API key includes a -usNN server suffix",
        "a0B1" * 7 + "-us22",  # short body
        "g0B1" * 8 + "-us22",  # non-hex
        "a0B1" * 8 + "-us",  # no datacenter number
        "a0B1" * 8 + "-us1234",  # out of range for this bounded detector
        "a0B1" * 8 + "-eu22",  # not a US data center
        "prefix_" + value,
        value + "_suffix",
        "a0B1" * 8,  # bare hex identifier is not itself a Mailchimp key
    ):
        assert all(f.kind != "mailchimp_api_key" for f in find_secrets(non_key)), non_key[:80]
