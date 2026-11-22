"""Regression tests for typed Netlify credentials (synthetic tokens only)."""

from app.firewall.secrets import find_secrets, has_secret, label_for_kind, redact_text, redacted_kinds


def test_netlify_authentication_tokens_are_classified_and_fully_redacted():
    # Netlify publishes five typed prefixes; token values are synthetic.
    for prefix in ("nfp", "nfc", "nfo", "nfu", "nfb"):
        token = prefix + "_" + "Ab3x" * 9
        for raw in (token, f"Netlify: {token} here"):
            findings = find_secrets(raw)
            assert [f.kind for f in findings] == ["netlify_access_token"]
            assert redact_text(raw) == raw.replace(token, "«REDACTED:netlify_access_token»")
            assert redacted_kinds(redact_text(raw)) == ["netlify_access_token"]
            assert not has_secret(redact_text(raw))
            assert redact_text(redact_text(raw)) == redact_text(raw)
    assert label_for_kind("netlify_access_token") == "Netlify authentication token"


def test_netlify_token_prefixes_do_not_match_incomplete_or_embedded_values():
    token = "nfp_" + "Ab3x" * 9
    for ordinary in (
        "nfp_ is a Netlify personal token prefix",
        "nfp_" + "a" * 35,
        "nfp_" + "a" * 37,
        "nfx_" + "Ab3x" * 9,
        "prefix_" + token,
        token + "_suffix",
        "nfp_" + "a" * 100_000,
    ):
        assert all(f.kind != "netlify_access_token" for f in find_secrets(ordinary)), ordinary[:80]
