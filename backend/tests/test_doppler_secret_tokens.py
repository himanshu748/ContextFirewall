"""Synthetic Doppler token tests; no live credentials are used."""
from app.firewall.secrets import find_secrets, redact_text, redacted_kinds, has_secret


def test_doppler_token_families_are_fully_redacted():
    # Doppler documents seven token families and an optional service scope.
    suffix = "Ab3x" * 10
    for prefix in (
        "dp.ct.", "dp.pt.", "dp.st.", "dp.st.dev.",
        "dp.sa.", "dp.said.", "dp.scim.", "dp.audit.",
    ):
        token = prefix + suffix
        for text in (token, f"token: {token}; rotate it"):
            hits = find_secrets(text)
            assert [hit.kind for hit in hits] == ["doppler_auth_token"], prefix
            safe = redact_text(text)
            assert safe == text.replace(token, "«REDACTED:doppler_auth_token»")
            assert token not in safe
            assert redacted_kinds(safe) == ["doppler_auth_token"]
            assert not has_secret(safe)


def test_doppler_boundaries_and_shape_prevent_partial_matches():
    token = "dp.st.dev." + "Ab3x" * 10
    for candidate in (
        "dp.st.dev." + "A" * 39,        # Too short
        "dp.st.dev." + "A" * 45,        # Too long
        "dp.st.d." + "A" * 40,          # Scope too short
        "dp.st." + "d" * 36 + "." + "A" * 40,  # Scope too long
        "dp.invalid." + "A" * 40,
        "prefix_" + token,
        token + "_suffix",
        token + ".other",
        "dp.ct." + "A" * 100_000,     # Must not redact a secret prefix
    ):
        assert all(hit.kind != "doppler_auth_token" for hit in find_secrets(candidate)), candidate[:60]


def test_doppler_scope_and_payload_length_edges():
    for length in (40, 44):
        token = "dp.st." + "a" * 35 + "." + "B" * length
        assert [hit.kind for hit in find_secrets(token)] == ["doppler_auth_token"]
        assert redact_text(token) == "«REDACTED:doppler_auth_token»"
