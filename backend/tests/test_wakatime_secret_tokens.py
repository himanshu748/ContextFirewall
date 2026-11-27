"""Verify WakaTime's waka_-prefixed UUID credential; no secret-shaped literals are committed."""
from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_wakatime_key_is_detected_and_redacted():
    token = "waka_" + "f00dba11-" + "1234-4abc-8def-" + "123456789abc"
    for text in (token, f"credential: {token}"):
        found = find_secrets(text)
        assert [item.kind for item in found] == ["wakatime_api_key"]
        assert found[0].label == "WakaTime API key"
        safe = redact_text(text)
        assert safe == text.replace(token, "«REDACTED:wakatime_api_key»")
        assert token not in safe
        assert redacted_kinds(safe) == ["wakatime_api_key"]
        assert not has_secret(safe)
    assert label_for_kind("wakatime_api_key") == "WakaTime API key"


def test_wakatime_rejects_partial_and_embedded_values():
    token = "waka_" + "f00dba11-" + "1234-4abc-8def-" + "123456789abc"
    for value in ["waka_" + "f00dba11-" + "1234-4abc-8def-" + "123456789ab", "waka_" + "zzzzzzzz-" + "1234-4abc-8def-" + "123456789abc", token + "_suffix"]:
        assert all(item.kind != "wakatime_api_key" for item in find_secrets(value)), value[:80]
