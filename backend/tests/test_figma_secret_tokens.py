"""Synthetic Figma PAT detection tests; no real access tokens."""
from app.firewall.secrets import find_secrets, redact_text, redacted_kinds, has_secret


def test_figma_pat_is_fully_redacted():
    # The figd_ prefix is community-observed, not a fixed published token schema.
    for n in (40, 44, 48, 160, 200):
        token = "figd_" + "Ab3x" * (n // 4) + "A" * (n % 4)
        for text in (token, f"Figma PAT: {token}."):
            hits = find_secrets(text)
            assert [f.kind for f in hits] == ["figma_personal_access_token"]
            safe = redact_text(text)
            assert safe == text.replace(token, "«REDACTED:figma_personal_access_token»")
            assert token not in safe
            assert redacted_kinds(safe) == ["figma_personal_access_token"]
            assert not has_secret(safe)


def test_figma_pat_partial_matches_are_rejected():
    token = "figd_" + "Ab3x" * 10
    for candidate in (
        "figd_",
        "figd_" + "A" * 39,
        "figd_" + "A" * 201,
        "figx_" + "A" * 48,
        "prefix_" + token,
        "x" + token,
        "figd_" + "A" * 100_000,
    ):
        assert all(f.kind != "figma_personal_access_token" for f in find_secrets(candidate)), candidate[:60]


def test_figma_pat_with_opaque_underscore_suffix_is_redacted_whole():
    # Underscores are valid payload characters; suffixes must not leak.
    token = "figd_" + "Ab3x" * 10 + "_suffix"
    assert [f.kind for f in find_secrets(token)] == ["figma_personal_access_token"]
    assert redact_text(token) == "«REDACTED:figma_personal_access_token»"
