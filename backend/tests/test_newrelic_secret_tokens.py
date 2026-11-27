"""Regression coverage for New Relic user (NRAK-) and Insights insert (NRII-) credentials; all credentials are synthetic."""
from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_newrelic_keys_are_classified_and_redacted():
    for token in ["NRAK-Ab3Ab3Ab3Ab3Ab3Ab3Ab3Ab3Ab3","NRII-Ab3Ab3Ab3Ab3Ab3Ab3Ab3Ab3Ab3Ab3"]:
        for original in (token, f"credential: {token}"):
            findings = find_secrets(original)
            assert [item.kind for item in findings] == ["newrelic_api_key"]
            assert findings[0].label == "New Relic API key"
            masked = redact_text(original)
            assert masked == original.replace(token, "«REDACTED:newrelic_api_key»")
            assert token not in masked
            assert redacted_kinds(masked) == ["newrelic_api_key"]
            assert not has_secret(masked)
    assert label_for_kind("newrelic_api_key") == "New Relic API key"


def test_newrelic_rejects_partial_tokens_and_near_misses():
    for value in ["NRAK-aaaaaaaaaaaaaaaaaaaaaaaaaa","NRII-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","XXNRAK-aaaaaaaaaaaaaaaaaaaaaaaaaaa","NRAK-aaaaaaaaaaaaaaaaaaaaaaaaaaa_suffix"]:
        assert all(hit.kind != "newrelic_api_key" for hit in find_secrets(value)), value[:80]
