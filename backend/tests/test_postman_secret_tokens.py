"""Verify Postman PMAK keys with their two fixed-length hex segments; no secret-shaped literals are committed."""
from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_postman_key_is_detected_and_redacted():
    token = "PMAK-" + "a1" * 12 + "-" + "b2" * 17
    for text in (token, f"credential: {token}"):
        found = find_secrets(text)
        assert [item.kind for item in found] == ["postman_api_key"]
        assert found[0].label == "Postman API key"
        safe = redact_text(text)
        assert safe == text.replace(token, "«REDACTED:postman_api_key»")
        assert token not in safe
        assert redacted_kinds(safe) == ["postman_api_key"]
        assert not has_secret(safe)
    assert label_for_kind("postman_api_key") == "Postman API key"


def test_postman_rejects_partial_and_embedded_values():
    token = "PMAK-" + "a1" * 12 + "-" + "b2" * 17
    for value in ["PMAK-" + "a1" * 11 + "-" + "b2" * 17, "PMAK-" + "a1" * 12 + "-" + "b2" * 16, token + "_suffix"]:
        assert all(item.kind != "postman_api_key" for item in find_secrets(value)), value[:80]
