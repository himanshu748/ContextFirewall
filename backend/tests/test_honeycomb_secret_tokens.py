"""Regression coverage for Honeycomb complete ingest keys (not the public hcaik_ identifiers); all credentials are synthetic."""
from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_honeycomb_keys_are_classified_and_redacted():
    for token in ["hcaik_ab12cdab12cdab12cdab12cdab12cdab12cdab12cdab12cdab12cdabcd","hcbic_ab12cdab12cdab12cdab12cdab12cdab12cdab12cdab12cdab12cdabcd"]:
        for original in (token, f"credential: {token}"):
            findings = find_secrets(original)
            assert [item.kind for item in findings] == ["honeycomb_ingest_key"]
            assert findings[0].label == "Honeycomb ingest API key"
            masked = redact_text(original)
            assert masked == original.replace(token, "«REDACTED:honeycomb_ingest_key»")
            assert token not in masked
            assert redacted_kinds(masked) == ["honeycomb_ingest_key"]
            assert not has_secret(masked)
    assert label_for_kind("honeycomb_ingest_key") == "Honeycomb ingest API key"


def test_honeycomb_rejects_partial_tokens_and_near_misses():
    for value in ["hcaik_01hj41kvak3fg7y0295rzfh4bf","hcaik_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","hcaik_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","hcaik_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_suffix"]:
        assert all(hit.kind != "honeycomb_ingest_key" for hit in find_secrets(value)), value[:80]
