"""Unit tests for the firewall secret detector. Pure-Python, no network/cognee.

Every "secret" here is ASSEMBLED at runtime from harmless fragments, so no
credential-shaped literal is ever committed to the repo. That keeps secret
scanners (GitGuardian etc.) quiet while still feeding the detector a complete,
realistic string to match — the detector under test is what builds the full value.
"""
from __future__ import annotations

import base64
import os
from unittest.mock import patch

from app.firewall.secrets import find_secrets, has_secret, redact_text, redacted_kinds, label_for_kind


def test_circleci_personal_and_project_tokens_are_fully_redacted():
    # Matches CircleCI's published UUID + 40-hex suffix shape; fake values.
    uid = "ULUhR6rJLxYbyzyrP19iMZ"
    for prefix in ("CCIPAT", "CCIPRJ"):
        token = f"{prefix}_{uid}_" + "a1b2c3d4" * 5
        text = f"CircleCI credential: {token}"
        findings = find_secrets(text)
        assert len(findings) == 1
        assert findings[0].kind == "circleci_api_token"
        assert findings[0].label == "CircleCI API token"
        masked = redact_text(text)
        assert masked == "CircleCI credential: «REDACTED:circleci_api_token»"
        assert token not in masked
        assert redacted_kinds(masked) == ["circleci_api_token"]
        assert not has_secret(masked)
    assert label_for_kind("circleci_api_token") == "CircleCI API token"


def test_circleci_token_near_misses_do_not_match_partial_credentials():
    uid = "ULUhR6rJLxYbyzyrP19iMZ"
    token = "CCIPAT_" + uid + "_" + "a1b2c3d4" * 5
    for ordinary in (
        "CCIPAT_ is CircleCI's personal token prefix",
        "CCIPAT_" + uid + "_" + "a1b2c3d4" * 4,
        "CCIPAT_" + uid + "_" + "z" * 40,
        "prefix_" + token,
        token + "_suffix",
        "CCIPAT_" + uid + "0_" + "a1b2c3d4" * 5,
    ):
        assert all(f.kind != "circleci_api_token" for f in find_secrets(ordinary)), ordinary[:80]


def test_supabase_secret_keys_are_classified_and_redacted():
    # Assemble a synthetic server-only key; public sb_publishable_ keys are distinct.
    token = "sb_" + "secret_" + "Ab3x" * 8
    raw = f"Bearer {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "supabase_secret_key"
    assert findings[0].label == "Supabase secret API key"
    assert redact_text(raw) == "Bearer «REDACTED:supabase_secret_key»"
    assert token not in redact_text(raw)
    assert redacted_kinds(redact_text(raw)) == ["supabase_secret_key"]
    assert not has_secret(redact_text(raw))
    assert label_for_kind("supabase_secret_key") == "Supabase secret API key"


def test_supabase_secret_key_near_misses_are_not_typed_as_secrets():
    token = "sb_" + "secret_" + "Ab3x" * 8
    for ordinary in (
        "sb_" + "publishable_" + "Ab3x" * 8,
        "sb_" + "secret_" + "a" * 23,
        "prefix_" + token,
        "sb_" + "secret_" + "a" * 129,
    ):
        assert all(f.kind != "supabase_secret_key" for f in find_secrets(ordinary)), ordinary[:80]


def test_supabase_publishable_realistic_public_key_is_not_a_secret():
    # Supabase publishes keys with 22 random characters and an 8-char checksum.
    # This varied synthetic key has enough entropy to trip the generic scanner
    # without the public-key shape exemption.
    random_body = "uJ9pE3yL6dA8qX4kB1mY7v"
    checksum = "R2nC5tS0"
    assert len(random_body) == 22
    assert len(checksum) == 8
    public = "sb_publishable_" + random_body + "_" + checksum
    secret = "sb_secret_" + random_body + "_" + checksum
    assert [f.kind for f in find_secrets("rnd_" + random_body + "_" + checksum)] == [
        "high_entropy_token"
    ]

    for raw in (public, f"createClient('{public}')", f"public key: {public}."):
        assert find_secrets(raw) == []
        assert not has_secret(raw)
        assert redact_text(raw) == raw

    mixed = f"Public key: {public}; private key: {secret}"
    assert [f.kind for f in find_secrets(mixed)] == ["supabase_secret_key"]
    assert redact_text(mixed) == (
        f"Public key: {public}; private key: «REDACTED:supabase_secret_key»"
    )

    # Incomplete or extended lookalikes must not bypass generic scanning.
    for malformed in (public + "_suffix", "not" + public):
        assert [f.kind for f in find_secrets(malformed)] == ["high_entropy_token"]


def test_vercel_prefixed_credentials_are_classified_and_redacted():
    # Vercel's five credential prefixes were introduced in 2026.
    for prefix in ("vcp", "vci", "vca", "vcr", "vck"):
        token = prefix + "_" + "Ab3x" * 12  # Entirely synthetic body.
        raw = f"Vercel credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "vercel_credential"
        assert redact_text(raw) == "Vercel credential: «REDACTED:vercel_credential»"
        assert token not in redact_text(raw)
        assert redacted_kinds(redact_text(raw)) == ["vercel_credential"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("vercel_credential") == "Vercel API credential"


def test_vercel_token_near_misses_are_not_flagged():
    token = "vcp_" + "Ab3x" * 12
    for ordinary in (
        "Vercel tokens should be private",
        "vcp_" + "A" * 39,
        "vca_" + "A" * 81,
        "vcx_" + "Ab3x" * 12,
        "prefix_" + token,
        token + "_suffix",
        "vcp_" + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_gitlab_deploy_tokens_are_classified_and_redacted():
    token = "gldt-" + "a1B2" * 8  # Synthetic, never an issued token.
    raw = f"GitLab deploy credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "gitlab_deploy_token"
    assert redact_text(raw) == "GitLab deploy credential: «REDACTED:gitlab_deploy_token»"
    assert token not in redact_text(raw)
    assert redacted_kinds(redact_text(raw)) == ["gitlab_deploy_token"]
    assert not has_secret(redact_text(raw))
    assert label_for_kind("gitlab_deploy_token") == "GitLab deploy token"


def test_gitlab_deploy_token_near_misses_remain_unchanged():
    token = "gldt-" + "a1B2" * 8
    for ordinary in (
        "GitLab deploy token documentation",
        "gldt-" + "a" * 15,
        "gldt-" + "a" * 129,
        "not" + token,
        "prefix_" + token,
        "gldt-" + "a" * 8 + "!" + "b" * 8,
        "glpt-" + "a1B2" * 8,
        "gldt-" + "a" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]



def test_openrouter_api_keys_are_classified_without_openai_overlap():
    token = "sk-" + "or-v1-" + "a1B2" * 16  # Synthetic 64-hex payload.
    for raw in (token, f"Bearer {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "openrouter_api_key"
        assert findings[0].label == "OpenRouter API key"
        assert redact_text(raw) == raw.replace(token, "«REDACTED:openrouter_api_key»")
        assert token not in redact_text(raw)
        assert redacted_kinds(redact_text(raw)) == ["openrouter_api_key"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("openrouter_api_key") == "OpenRouter API key"


def test_openrouter_key_near_misses_do_not_match_openai_rule():
    token = "sk-" + "or-v1-" + "a1B2" * 16
    for ordinary in (
        "sk-or-v1- is an OpenRouter key prefix",
        "sk-" + "or-v1-" + "a" * 63,
        "sk-" + "or-v1-" + "a" * 65,
        "prefix_" + token,
        token + "_suffix",
        "sk-" + "or-v1-" + "z" * 64,
        "sk-" + "or-v1-" + "a" * 100_000,
    ):
        assert all(f.kind not in {"openrouter_api_key", "openai_key"} for f in find_secrets(ordinary)), ordinary[:80]




def test_firecrawl_api_keys_are_classified_and_redacted():
    token = "fc-" + "Ab3x" * 9  # Synthetic payload; never an issued credential.
    raw = f"Firecrawl key: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "firecrawl_api_key"
    assert findings[0].label == "Firecrawl API key"
    assert redact_text(raw) == "Firecrawl key: «REDACTED:firecrawl_api_key»"
    assert token not in redact_text(raw)
    assert redacted_kinds(redact_text(raw)) == ["firecrawl_api_key"]
    assert not has_secret(redact_text(raw))
    assert label_for_kind("firecrawl_api_key") == "Firecrawl API key"


def test_firecrawl_key_near_misses_are_not_classified():
    token = "fc-" + "Ab3x" * 9
    for ordinary in (
        "Firecrawl key format starts with fc-",
        "fc-" + "a" * 23,
        "fc-" + "a" * 257,
        "fca-" + "a" * 36,
        "prefix_" + token,
        "fc-" + "a" * 100_000,
    ):
        assert all(f.kind != "firecrawl_api_key" for f in find_secrets(ordinary)), ordinary[:80]
    # A trailing underscore is allowed in the opaque payload; never redact
    # only a token prefix while leaving an unknown possible suffix visible.
    extended = token + "_suffix"
    assert redact_text(extended) == "«REDACTED:firecrawl_api_key»"




def test_pinecone_api_key_is_fully_classified_and_redacted():
    token = "pcsk_" + "Ab3_x" * 8
    raw = f"Pinecone credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "pinecone_api_key"
    assert findings[0].label == "Pinecone API key"
    assert redact_text(raw) == "Pinecone credential: «REDACTED:pinecone_api_key»"
    assert redacted_kinds(redact_text(raw)) == ["pinecone_api_key"]
    assert not has_secret(redact_text(raw))
    assert label_for_kind("pinecone_api_key") == "Pinecone API key"


def test_pinecone_api_key_near_misses_are_not_typed_as_secrets():
    token = "pcsk_" + "Ab3_x" * 8
    for ordinary in (
        "Configure your Pinecone pcsk_ credential",
        "pcsk_" + "a" * 15,
        "pcsk_" + "a" * 257,
        "not" + token,
        "prefix_" + token,
        "pcsk_" + "a" * 8 + "!" + "b" * 8,
    ):
        assert all(f.kind != "pinecone_api_key" for f in find_secrets(ordinary))




def test_langsmith_personal_and_service_keys_are_fully_redacted():
    for kind in ("pt", "sk"):
        token = "lsv2_" + kind + "_" + "Ab3x" * 12
        raw = f"LangSmith credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "langsmith_key"
        assert findings[0].label == "LangSmith API key"
        assert redact_text(raw) == "LangSmith credential: «REDACTED:langsmith_key»"
        assert redacted_kinds(redact_text(raw)) == ["langsmith_key"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("langsmith_key") == "LangSmith API key"


def test_langsmith_key_near_misses_are_not_typed_as_secrets():
    token = "lsv2_pt_" + "Ab3x" * 12
    for ordinary in (
        "LangSmith personal access tokens start with lsv2_pt_",
        "lsv2_pt_" + "A" * 23,
        "lsv2_other_" + "A" * 48,
        "prefix_" + token,
        "lsv2_sk_" + "A" * 257,
    ):
        assert all(f.kind != "langsmith_key" for f in find_secrets(ordinary))




def test_tavily_api_keys_are_classified_and_redacted():
    token = "tvly-" + "Ab3x" * 10  # Synthetic; never use real API keys in tests.
    for content in (token, f"Search credential: {token}", f"Bearer {token}"):
        findings = find_secrets(content)
        assert len(findings) == 1
        assert findings[0].kind == "tavily_api_key"
        assert findings[0].label == "Tavily API key"
        redacted = redact_text(content)
        assert redacted == content.replace(token, "«REDACTED:tavily_api_key»")
        assert redacted_kinds(redacted) == ["tavily_api_key"]
        assert not has_secret(redacted)
    assert label_for_kind("tavily_api_key") == "Tavily API key"


def test_tavily_token_boundaries_and_near_misses():
    token = "tvly-" + "Ab3x" * 10
    for near_miss in (
        "tvly-" + "A" * 31,
        "tvly-" + "A" * 129,
        "prefix_" + token,
        "not" + token,
        "tvly-" + "A" * 100_000,
    ):
        assert all(f.kind != "tavily_api_key" for f in find_secrets(near_miss)), near_miss[:80]




def test_gitlab_pipeline_trigger_tokens_are_redacted():
    token = "glptt-" + "Ab3_" * 8  # Synthetic; no real credentials.
    for raw in (token, f"Pipeline trigger: {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "gitlab_trigger_token"
        assert findings[0].label == "GitLab pipeline trigger token"
        assert redact_text(raw) == raw.replace(token, "«REDACTED:gitlab_trigger_token»")
        assert redacted_kinds(redact_text(raw)) == ["gitlab_trigger_token"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("gitlab_trigger_token") == "GitLab pipeline trigger token"


def test_gitlab_pipeline_trigger_token_near_misses_are_unchanged():
    token = "glptt-" + "Ab3_" * 8
    for ordinary in (
        "GitLab trigger tokens start with glptt-",
        "glptt-" + "A" * 19,
        "glptt-" + "A" * 129,
        "not" + token,
        "prefix_" + token,
        "glptt-" + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]
    extended = token + "_suffix"
    assert redact_text(extended) == "«REDACTED:gitlab_trigger_token»"




def _uri(scheme: str, user: str, pwd: str, host: str, tail: str = "") -> str:
    """Assemble a connection URI from fragments so no full credential-URI literal is committed."""
    return scheme + "://" + user + ":" + pwd + "@" + host + tail


def test_databricks_personal_access_token_is_classified_and_redacted():
    # Databricks documents legacy PATs with a dapi prefix and 32 hex digits.
    token = "dapi" + "a1B2" * 8
    raw = f"Databricks credential: {token}"
    matches = find_secrets(raw)
    assert len(matches) == 1
    assert matches[0].kind == "databricks_pat"
    assert matches[0].label == "Databricks personal access token"
    assert redact_text(raw) == "Databricks credential: «REDACTED:databricks_pat»"
    assert redacted_kinds(redact_text(raw)) == ["databricks_pat"]
    assert label_for_kind("databricks_pat") == "Databricks personal access token"


def test_databricks_pat_near_misses_are_ignored():
    token = "dapi" + "a1B2" * 8
    for ordinary in (
        "Databricks PATs may begin with dapi",
        "dapi" + "a" * 31,
        "dapi" + "a" * 33,
        "dapi" + "g" * 32,
        "pre" + token,
        token + "_suffix",
        "dapi" + "a" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_hashicorp_vault_tokens_are_classified_and_redacted():
    for prefix in ("hvs", "hvb", "hvr"):
        token = prefix + "." + "Ab3_" * 8
        raw = f"Vault credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "hashicorp_vault_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "Vault credential: «REDACTED:hashicorp_vault_token»"
        assert redacted_kinds(redact_text(raw)) == ["hashicorp_vault_token"]
    assert label_for_kind("hashicorp_vault_token") == "HashiCorp Vault token"


def test_hashicorp_vault_token_near_misses_are_not_secret_matches():
    token = "hvs." + "Ab3_" * 8
    for ordinary in (
        "Use Vault service tokens in development",
        "hvs." + "A" * 23,
        "hvb." + "A" * 129,
        "hva." + "Ab3_" * 8,
        "prefix_" + token,
        "hvs-" + "Ab3_" * 8,
        "hvs." + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]



def test_detects_and_redacts_groq_api_keys():
    token = "gsk_" + "Ab3x" * 10  # Synthetic; not a live credential.
    for content in (token, f"Groq API credential: {token}"):
        findings = find_secrets(content)
        assert len(findings) == 1
        assert findings[0].kind == "groq_api_key"
        assert token not in findings[0].redacted
        assert redact_text(content) == content.replace(token, "«REDACTED:groq_api_key»")
        assert redacted_kinds(redact_text(content)) == ["groq_api_key"]
        assert not has_secret(redact_text(content))
    assert label_for_kind("groq_api_key") == "Groq API key"


def test_groq_key_boundaries_and_near_misses():
    token = "gsk_" + "Ab3x" * 10
    for ordinary in (
        "Groq API keys should stay private",
        "gsk_" + "A" * 29,
        "not" + token,
        "prefix_" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary



def test_xai_api_keys_are_classified_and_redacted():
    token = "xai-" + "Ab3x" * 9  # Synthetic credential-shaped fixture.
    for raw in (token, f"xAI credential: {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "xai_api_key"
        assert token not in findings[0].redacted
        assert redact_text(raw) == raw.replace(token, "«REDACTED:xai_api_key»")
        assert redacted_kinds(redact_text(raw)) == ["xai_api_key"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("xai_api_key") == "xAI API key"


def test_xai_api_key_boundaries_and_long_values():
    token = "xai-" + "Ab3x" * 9
    for ordinary in (
        "xAI API credentials use the xai- prefix",
        "xai-" + "A" * 23,
        "xai-" + "A" * 129,
        "prefix_" + token,
        "not" + token,
        "xai_" + "A" * 36,
        "xai-" + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_detects_and_redacts_resend_api_key():
    # Resend documents the re_ prefix; use an entirely synthetic opaque payload.
    token = "re_" + "Ab3x" * 8
    content = f"Resend credential: {token}"
    findings = find_secrets(content)
    assert len(findings) == 1
    assert findings[0].kind == "resend_api_key"
    assert token not in findings[0].redacted
    redacted = redact_text(content)
    assert redacted == "Resend credential: «REDACTED:resend_api_key»"
    assert token not in redacted
    assert redacted_kinds(redacted) == ["resend_api_key"]
    assert label_for_kind("resend_api_key") == "Resend API key"


def test_resend_api_key_does_not_match_short_or_embedded_identifiers():
    token = "re_" + "Ab3x" * 8
    for ordinary in (
        "Resend API keys start with re_",
        "re_" + "A" * 23,
        "prefix_" + token,
        "pre_" + "Ab3x" * 8,
        "key_" + token,
    ):
        assert not has_secret(ordinary), ordinary



def test_nvidia_ngc_api_keys_are_classified_and_redacted():
    # Synthetic credentials; NGC API keys use the nvapi- provider prefix.
    token = "nvapi-" + "Ab3x" * 10
    for raw in (token, f"NVIDIA key: {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "nvidia_ngc_api_key"
        assert token not in findings[0].redacted
        assert redact_text(raw) == raw.replace(token, "«REDACTED:nvidia_ngc_api_key»")
        assert redacted_kinds(redact_text(raw)) == ["nvidia_ngc_api_key"]
        assert not has_secret(redact_text(raw))
    assert label_for_kind("nvidia_ngc_api_key") == "NVIDIA NGC API key"


def test_nvidia_ngc_api_key_near_misses_do_not_match():
    token = "nvapi-" + "Ab3x" * 10
    for ordinary in (
        "The NVIDIA NGC API key uses an nvapi- prefix",
        "nvapi-" + "A" * 23,
        "nvapi_" + "A" * 40,
        "prefix_" + token,
        "word" + token,
        "nvapi-" + "A" * 257,
    ):
        assert not has_secret(ordinary), ordinary[:80]


# --- positives: each should be detected (values assembled at runtime) ---------
def test_detects_and_redacts_slack_app_level_tokens():
    for prefix in ("xapp-", "xoxe.xapp-"):
        token = prefix + "1-" + "Ab3x-" * 7
        raw = f"Slack app credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "slack_app_level_token"
        assert redact_text(raw) == "Slack app credential: «REDACTED:slack_app_level_token»"
        assert token not in redact_text(raw)
        assert redacted_kinds(redact_text(raw)) == ["slack_app_level_token"]
    assert label_for_kind("slack_app_level_token") == "Slack app-level token"


def test_slack_app_level_tokens_exclude_public_text_and_identifier_lookalikes():
    token = "xapp-1-" + "Ab3x-" * 7
    for ordinary in (
        "xapp- app-level tokens must be kept private",
        "xapp-" + "A" * 19,
        "xapp-" + "A" * 257,
        "xoxe.xapp-" + "A" * 19,
        "prefix_" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_grafana_service_account_tokens_are_detected_and_redacted():
    token = "glsa_" + "Ab3D" * 8 + "_a1b2c3d4"
    for raw in (token, f"Grafana credential: {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "grafana_service_account_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == raw.replace(token, "«REDACTED:grafana_service_account_token»")
        assert redacted_kinds(redact_text(raw)) == ["grafana_service_account_token"]
    assert label_for_kind("grafana_service_account_token") == "Grafana service account token"


def test_grafana_service_account_token_shape_and_boundaries():
    token = "glsa_" + "Ab3D" * 8 + "_a1b2c3d4"
    for ordinary in (
        "Configure the Grafana service account token",
        "glsa_" + "A" * 31 + "_a1b2c3d4",
        "glsa_" + "A" * 33 + "_a1b2c3d4",
        "glsa_" + "A" * 32 + "_nothexzz",
        "prefix_" + token,
        token + "_extra",
        "glsa_" + "A" * 100_000 + "_a1b2c3d4",
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_tailscale_key_types_are_detected_and_redacted():
    # Synthetic two-component keys modeled on the documented tskey-* format.
    # No live credential string is stored in the test suite.
    for key_type in ("api", "auth", "client", "scim", "webhook"):
        token = "tskey-" + key_type + "-" + "aB3D" * 3 + "-" + "C4dE" * 5
        raw = "Tailscale credential: " + token
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "tailscale_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "Tailscale credential: «REDACTED:tailscale_token»"
        assert redacted_kinds(redact_text(raw)) == ["tailscale_token"]
    assert label_for_kind("tailscale_token") == "Tailscale API, auth, or integration key"


def test_tailscale_prefixes_and_near_misses_are_not_secrets():
    token = "tskey-api-" + "A" * 12 + "-" + "B" * 20
    for ordinary in (
        "Configure your Tailscale tskey-api access token",
        "tskey-api-" + "A" * 7 + "-" + "B" * 20,
        "tskey-api-" + "A" * 12 + "-" + "B" * 11,
        "tskey-unknown-" + "A" * 12 + "-" + "B" * 20,
        "prefix_" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary



def test_detects_and_redacts_cloudflare_api_credentials():
    # All three current Cloudflare prefixes use an alphanumeric body and a
    # hexadecimal checksum. These examples are synthetic and not usable keys.
    for prefix in ("cfk", "cfut", "cfat"):
        token = prefix + "_" + "Ab3x" * 10 + "a1b2c3d4"
        raw = f"Cloudflare credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "cloudflare_api_credential"
        assert token not in findings[0].redacted
        redacted = redact_text(raw)
        assert redacted == "Cloudflare credential: «REDACTED:cloudflare_api_credential»"
        assert token not in redacted
        assert redacted_kinds(redacted) == ["cloudflare_api_credential"]
    assert label_for_kind("cloudflare_api_credential") == "Cloudflare API credential"


def test_cloudflare_api_credential_shape_and_identifier_boundaries():
    token = "cfk_" + "Ab3x" * 10 + "a1b2c3d4"
    for ordinary in (
        "Cloudflare API credentials are secrets",
        "cfk_" + "A" * 39 + "a1b2c3d4",  # Too-short body.
        "cfut_" + "A" * 40 + "zzzzzzzz",  # Non-hex checksum.
        "cfat_" + "A" * 40 + "a1b2c3d",  # Too-short checksum.
        "prefix_" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_posthog_private_and_oauth_tokens():
    # phc_ is deliberately absent: that is a public ingestion/project key.
    for prefix in ("phx", "phs", "pha", "phr"):
        token = prefix + "_" + "Ab3_" * 8
        raw = f"PostHog private credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "posthog_secret_token"
        assert token not in findings[0].redacted
        redacted = redact_text(raw)
        assert redacted == "PostHog private credential: «REDACTED:posthog_secret_token»"
        assert token not in redacted
        assert redacted_kinds(redacted) == ["posthog_secret_token"]
    assert label_for_kind("posthog_secret_token") == "PostHog private API token"


def test_posthog_public_key_and_token_lookalikes_are_not_secret():
    token = "phx_" + "Ab3_" * 8
    for ordinary in (
        "phc_" + "A" * 32,  # Public project ingestion key.
        "phx_" + "A" * 19,
        "phs_" + "A" * 129,
        "prefix_" + token,
        "phx_" + "A" * 128 + "_suffix",  # Entire identifier exceeds bound.
        "PostHog API token setup",
    ):
        assert not has_secret(ordinary), ordinary


def test_high_entropy_posthog_public_tokens_are_not_redacted():
    # Varied synthetic bodies would trigger the generic entropy detector without
    # the public-token exemption; repeated "A" characters would not.
    for body in (
        "uJ9pE3yL6dA8qX4kB1mY7vR2nC5tS0wH3fZ9gP6",
        "F8w-2Nq_V5cM9rT1kY4zB7aE3pD6hJ0sL2xQ8",
    ):
        # Verify these fixtures actually exercise the default entropy fallback.
        assert [f.kind for f in find_secrets("rnd_" + body)] == ["high_entropy_token"]

        public = "phc_" + body
        for raw in (public, f"posthog.init('{public}')", f"project token: {public}."):
            assert find_secrets(raw) == []
            assert not has_secret(raw)
            assert redact_text(raw) == raw

        # Exempting the public key must not hide private credentials nearby.
        private = "pha_" + "Ab3_" * 8
        mixed = f"Public: {public}; OAuth: {private}"
        assert [f.kind for f in find_secrets(mixed)] == ["posthog_secret_token"]
        assert redact_text(mixed) == f"Public: {public}; OAuth: «REDACTED:posthog_secret_token»"



def test_detects_and_redacts_current_notion_integration_token():
    token = "ntn_" + "Ab3_" * 8  # Entirely synthetic bearer-token example.
    raw = f"Notion credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "notion_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Notion credential: «REDACTED:notion_token»"
    assert redacted_kinds(redact_text(raw)) == ["notion_token"]
    assert label_for_kind("notion_token") == "Notion integration token"


def test_detects_and_redacts_1password_service_account_token():
    # Prefix and payload shape match the published detector; fake bytes only.
    token = "ops_eyJ" + "Ab3/" * 63
    raw = f"vault credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "onepassword_service_account_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "vault credential: «REDACTED:onepassword_service_account_token»"
    assert label_for_kind("onepassword_service_account_token") == "1Password service account token"


def test_1password_prefix_without_long_canonical_payload_is_not_a_secret():
    token = "ops_eyJ" + "Ab3/" * 63
    for ordinary in (
        "OP_SERVICE_ACCOUNT_TOKEN is configured by the operator",
        "ops_eyJ" + "a" * 249,
        "before_" + token,
        token + "_suffix",
        "ops_sample-placeholder",
    ):
        assert not has_secret(ordinary), ordinary[:60]


def test_notion_prefix_and_embedded_identifiers_are_not_tokens():
    token = "ntn_" + "Ab3_" * 8
    for ordinary in (
        "Configure your Notion integration token in the environment",
        "ntn_" + "A" * 19,
        "not" + token,
        "prefix_" + token,
        "ntn_example_key",
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_docker_hub_access_tokens():
    for token_type in ("pat", "oat"):
        token = "dckr_" + token_type + "_" + "Ab3_" * 8
        raw = f"Docker Hub credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "docker_hub_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "Docker Hub credential: «REDACTED:docker_hub_token»"
        assert redacted_kinds(redact_text(raw)) == ["docker_hub_token"]
    assert label_for_kind("docker_hub_token") == "Docker Hub access token"


def test_docker_hub_token_lookalikes_are_not_redacted():
    token = "dckr_pat_" + "Ab3_" * 8
    for ordinary in (
        "Docker Hub personal access token",
        "dckr_pat_" + "A" * 19,
        "dckr_oat_" + "A" * 129,
        "dckr_bad_" + "Ab3_" * 8,
        "not" + token,
        "prefix_" + token,
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_linear_api_and_oauth_tokens():
    # Linear documents these prefixes; payloads are synthetic and opaque.
    for prefix in ("lin_api_", "lin_oauth_"):
        token = prefix + "Ab3_" * 8
        raw = f"Linear credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "linear_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "Linear credential: «REDACTED:linear_token»"
        assert redacted_kinds(redact_text(raw)) == ["linear_token"]
    assert label_for_kind("linear_token") == "Linear API or OAuth token"


def test_linear_token_near_misses_are_not_secrets():
    token = "lin_api_" + "Ab3_" * 8
    for ordinary in (
        "Configure Linear API authentication",
        "lin_api_" + "A" * 19,
        "lin_oauth_" + "A" * 19,
        "lin_api_placeholder",
        "not" + token,
        "prefix_" + token,
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_huggingface_token():
    tok = "hf_" + "ABCdef0123456789ABCDEFGHIJ"
    assert any(x.kind == "huggingface_token" for x in find_secrets(f"set the key to {tok} first"))


def test_detects_openai_key():
    key = "sk-" + "proj-" + "AbCd1234EfGh5678IjKl9012MnOp"
    assert has_secret(f"the key was {key}")


def test_detects_and_redacts_github_fine_grained_pat():
    # Assemble a fake PAT; GitHub documents github_pat_ as the token prefix.
    token = "github_" + "pat_" + "Ab3_" * 11
    raw = f"GitHub credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "github_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "GitHub credential: «REDACTED:github_token»"
    assert label_for_kind("github_token") == "GitHub token"


def test_github_pat_lookalikes_are_not_secrets():
    assert not has_secret("Configure GITHUB_PAT in your environment")
    assert not has_secret("github_" + "pat_" + "A" * 39)
    assert not has_secret("notgithub_" + "pat_" + "A" * 44)


def test_detects_and_redacts_gitlab_access_token():
    token = "glpat-" + "Ab12" * 5  # Deliberately synthetic; no usable credentials.
    findings = find_secrets(f"GITLAB_TOKEN={token}")
    assert len(findings) == 1
    assert findings[0].kind == "gitlab_token"
    assert token not in findings[0].redacted
    redacted = redact_text(f"GITLAB_TOKEN={token}")
    assert token not in redacted
    assert redacted_kinds(redacted) == ["gitlab_token"]
    assert label_for_kind("gitlab_token") == "GitLab access token"


def test_gitlab_ci_job_token_is_detected_and_redacted():
    # GitLab's glcbt- prefix identifies CI/CD job credentials; fixture is synthetic.
    token = "glcbt-" + "Ab3_" * 8
    for raw in (token, f"CI job credential: {token}"):
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "gitlab_ci_job_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == raw.replace(token, "«REDACTED:gitlab_ci_job_token»")
        assert redacted_kinds(redact_text(raw)) == ["gitlab_ci_job_token"]
    assert label_for_kind("gitlab_ci_job_token") == "GitLab CI/CD job token"


def test_gitlab_ci_job_token_lookalikes_are_kept():
    token = "glcbt-" + "Ab3_" * 8
    for ordinary in (
        "glcbt- is GitLab's CI job token prefix",
        "glcbt-" + "A" * 19,
        "glcbt-" + "A" * 129,
        "glcbt-" + "A" * 25 + ".unfinished-jwt",
        "prefix_" + token,
        "not" + token,
    ):
        assert not has_secret(ordinary), ordinary[:75]


def test_gitlab_jwt_job_token_is_redacted_as_one_jwt_not_a_partial_legacy_token():
    jwt = "eyJ" + "A" * 20 + "." + "eyJ" + "B" * 24 + "." + "Cd3_" * 12
    token = "glcbt-" + jwt
    findings = find_secrets(token)
    assert len(findings) == 1
    assert findings[0].kind == "jwt"
    assert redact_text(token) == "glcbt-«REDACTED:jwt»"
    assert jwt not in redact_text(token)


def test_detects_and_redacts_telegram_bot_token():
    secret = "Ab3_" * 8 + "xyz"  # Synthetic 35-character secret.
    # Include 11- and 12-digit IDs and the maximum Telegram 52-bit ID.
    for bot_id in ("12345678", "123456789", "1234567890", "12345678901", "123456789012", str((1 << 52) - 1)):
        token = bot_id + ":" + secret
        raw = f"Telegram bot credential {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "telegram_bot_token"
        assert token not in findings[0].redacted
        assert findings[0].start == raw.index(token)
        assert findings[0].end == len(raw)
        assert redact_text(raw) == "Telegram bot credential «REDACTED:telegram_bot_token»"
        assert label_for_kind("telegram_bot_token") == "Telegram bot token"

        url = "https://api.telegram.org/bot" + token + "/getMe"
        assert redact_text(url) == "https://api.telegram.org/bot«REDACTED:telegram_bot_token»/getMe"
        file_url = "https://api.telegram.org/file/bot" + token + "/image.jpg"
        assert redact_text(file_url) == "https://api.telegram.org/file/bot«REDACTED:telegram_bot_token»/image.jpg"


def test_telegram_bot_token_near_misses_are_not_secrets():
    secret = "Ab3_" * 8 + "xyz"
    token = "1234567890:" + secret
    for ordinary in (
        "Use a Telegram bot token in the API URL",
        "1234567:" + secret,
        "1234567890:" + secret[:-1],
        "not" + token,
        "prefix_" + token,
        "prefixbot" + token,
        token + "_suffix",
        token + "X",
        "１２３４５６７８:" + secret,  # Non-ASCII numeral lookalike.
    ):
        assert not has_secret(ordinary), ordinary


def test_telegram_bot_token_oversized_id_is_not_partially_redacted():
    secret = "Ab3_" * 8 + "xyz"
    # A 16-digit ID can exceed 52 bits; a 17+-digit ID must never match its suffix.
    for oversized_id in (str(1 << 52), "12345678901234567", "9" * 24):
        token = oversized_id + ":" + secret
        for raw in (token, "https://api.telegram.org/bot" + token + "/getMe"):
            assert not has_secret(raw), raw
            assert redact_text(raw) == raw


def test_gitlab_prefix_without_a_full_token_is_not_a_secret():
    assert not has_secret("glpat-" + "a" * 19)


def test_detects_gitlab_runner_authentication_tokens():
    # GitLab documents glrt- and legacy-registration glrtr- prefixes.
    for prefix in ("glrt-", "glrtr-"):
        token = prefix + "a1b2c3d4" * 4
        raw = f"Runner credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "gitlab_runner_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "Runner credential: «REDACTED:gitlab_runner_token»"
        assert redacted_kinds(redact_text(raw)) == ["gitlab_runner_token"]
    assert label_for_kind("gitlab_runner_token") == "GitLab runner authentication token"


def test_gitlab_runner_urlsafe_payloads_are_fully_redacted():
    # GitLab's runner token generator can include URL-safe Base64 "_" and "-".
    # A 20-character synthetic body deliberately stays below the generic
    # high-entropy detector's 32-character minimum for the complete token.
    for prefix in ("glrt-", "glrtr-"):
        for character in ("_", "-"):
            payload = "aB3d" * 2 + character + "aB3d" * 2 + "abc"
            assert len(payload) == 20
            token = prefix + payload
            raw = f"Runner credential: {token}"
            findings = find_secrets(raw)
            assert len(findings) == 1
            assert findings[0].kind == "gitlab_runner_token"
            assert (findings[0].start, findings[0].end) == (
                len("Runner credential: "), len(raw)
            )
            expected = "Runner credential: «REDACTED:gitlab_runner_token»"
            assert redact_text(raw) == expected
            assert token not in redact_text(raw)
            assert redacted_kinds(expected) == ["gitlab_runner_token"]


def test_gitlab_runner_token_near_misses_are_not_secrets():
    token = "glrt-" + "a1b2c3d4" * 4
    for ordinary in (
        "Set your glrt- token in CI",
        "glrt-" + "a" * 19,
        "glrtr-" + "a" * 129,
        "not" + token,
        "prefix_" + token,
        "glrt-" + "A" * 128 + "_suffix",  # exceeds max length, never partial
        "glrtr-" + "A" * 128 + "-suffix",  # "-" is valid within a token
        "glrt-" + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]



def test_detects_and_redacts_shopify_admin_access_token():
    token = "shpat_" + "a1B2" * 8  # Synthetic 32-character body.
    raw = f"Shopify credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "shopify_access_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Shopify credential: «REDACTED:shopify_access_token»"
    assert redacted_kinds(redact_text(raw)) == ["shopify_access_token"]
    assert label_for_kind("shopify_access_token") == "Shopify Admin API access token"


def test_shopify_token_near_misses_are_not_secrets():
    token = "shpat_" + "a1B2" * 8
    for ordinary in (
        "Shopify Admin API access token",
        "shpat_" + "A" * 31,
        "shppa_" + "a1B2" * 8,
        "not" + token,
        "prefix_" + token,
        token + "suffix",
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_discord_bot_token():
    # All three parts are synthetic and constructed at runtime.
    snowflake = base64.urlsafe_b64encode(b"123456789012345678").decode("ascii").rstrip("=")
    token = snowflake + "." + "Ab3_xY" + "." + "Cd4_" * 8
    raw = f"Discord bot credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "discord_bot_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Discord bot credential: «REDACTED:discord_bot_token»"
    assert redacted_kinds(redact_text(raw)) == ["discord_bot_token"]
    assert label_for_kind("discord_bot_token") == "Discord bot token"


def test_discord_token_shape_and_snowflake_false_positives():
    snowflake = base64.urlsafe_b64encode(b"123456789012345678").decode("ascii").rstrip("=")
    token = snowflake + "." + "Ab3_xY" + "." + "Cd4_" * 8
    for ordinary in (
        "Use a Discord bot token to authenticate the integration",
        "A" * 24 + "." + "b" * 6 + "." + "c" * 32,  # No encoded numeric snowflake.
        snowflake + "." + "A" * 5 + "." + "B" * 32,  # Too-short second segment.
        snowflake + "." + "A" * 6 + "." + "B" * 26,  # Too-short third segment.
        "prefix_" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_discord_incoming_webhooks():
    # Synthetic URL assembled from fragments, not a real webhook credential.
    for host in ("discord.com", "discordapp.com"):
        url = "https://" + host + "/api/webhooks/" + "123456789012345678" + "/" + "Ab3_" * 16
        raw = "Discord webhook: " + url + "?wait=true"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "discord_webhook_url"
        assert redact_text(raw) == "Discord webhook: «REDACTED:discord_webhook_url»?wait=true"
        assert url not in redact_text(raw)
        assert redacted_kinds(redact_text(raw)) == ["discord_webhook_url"]
    assert label_for_kind("discord_webhook_url") == "Discord incoming webhook URL"


def test_discord_webhook_url_near_misses_are_not_secrets():
    path = "/api/webhooks/123456789012345678/"
    for ordinary in (
        "https://discord.com" + path + "A" * 49,
        "https://discord.com" + path + "A" * 129,
        "https://discord.com/api/webhooks/1234/" + "A" * 64,
        "https://discord.com.evil.example" + path + "A" * 64,
        "https://example.org" + path + "A" * 64,
        "https://discord.com" + path + "A" * 64 + "_suffix" * 11,
    ):
        assert not has_secret(ordinary), ordinary[:100]


def test_detects_and_redacts_sentry_org_auth_token():
    token = "sntrys_" + "Ab12" * 6 + "_" + "Cd34" * 8  # Synthetic payload and secret.
    raw = f"Sentry organization auth: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "sentry_org_auth_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Sentry organization auth: «REDACTED:sentry_org_auth_token»"
    assert redacted_kinds(redact_text(raw)) == ["sentry_org_auth_token"]
    assert label_for_kind("sentry_org_auth_token") == "Sentry organization auth token"


def test_sentry_org_auth_token_near_misses_are_not_secrets():
    token = "sntrys_" + "Ab12" * 6 + "_" + "Cd34" * 8
    for ordinary in (
        "Sentry organization auth token", "sntrys_" + "A" * 9 + "_" + "B" * 32,
        "sntrys_" + "A" * 24 + "_" + "B" * 9,
        "sentry_" + "Ab12" * 6 + "_" + "Cd34" * 8,
        "not" + token,
        token + "_suffix",
    ):
        assert not has_secret(ordinary), ordinary


def test_sentry_org_auth_token_standard_base64_and_full_redaction():
    # Sentry encodes the JSON payload with standard Base64, retaining padding,
    # and the 32-byte secret with standard Base64, removing its final '='.
    # All credentials are synthetic and assembled at runtime.
    payloads = (
        base64.b64encode(b'{"iat": 1234567890.123456, "org": "sample"}').decode("ascii"),
        base64.b64encode(b'{"iat": 1234567890.123456, "org": "example"}').decode("ascii"),
        base64.b64encode(b'{"iat": 123, "org": "~~~~~~~"}').decode("ascii"),
        base64.b64encode(b'{"iat": 123, "org": "???????"}').decode("ascii"),
    )
    assert any(payload.endswith("==") for payload in payloads)
    assert any(payload.endswith("=") and not payload.endswith("==") for payload in payloads)
    assert any("+" in payload for payload in payloads)
    assert any("/" in payload for payload in payloads)

    secrets = (
        base64.b64encode(bytes([251, 255]) * 16).decode("ascii").rstrip("="),
        "A" * 42 + "+",  # Regression: do not leave a terminal '+' exposed.
        "B" * 42 + "/",  # Regression: do not leave a terminal '/' exposed.
    )
    assert all(len(secret) == 43 for secret in secrets)
    for payload in payloads:
        for secret in secrets:
            token = "sntrys_" + payload + "_" + secret
            raw = "before " + token + " after"
            findings = find_secrets(raw)
            assert len(findings) == 1, (payload, secret)
            assert findings[0].kind == "sentry_org_auth_token"
            assert (findings[0].start, findings[0].end) == (7, 7 + len(token))
            assert token not in findings[0].redacted
            assert redact_text(raw) == "before «REDACTED:sentry_org_auth_token» after"
            assert redacted_kinds(redact_text(raw)) == ["sentry_org_auth_token"]



def test_detects_and_redacts_digitalocean_tokens():
    for prefix in ("dop", "doo", "dor"):
        token = prefix + "_v1_" + "a1b2c3d4" * 8
        raw = f"DigitalOcean credential: {token}"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "digitalocean_token"
        assert token not in findings[0].redacted
        assert redact_text(raw) == "DigitalOcean credential: «REDACTED:digitalocean_token»"
        assert redacted_kinds(redact_text(raw)) == ["digitalocean_token"]
    assert label_for_kind("digitalocean_token") == "DigitalOcean API token"


def test_digitalocean_lookalikes_are_not_secrets():
    token = "dop_v1_" + "a1b2c3d4" * 8
    for ordinary in (
        "DigitalOcean supports personal access tokens",
        "dop_v1_" + "a" * 63,
        "doo_v1_" + "b" * 65,
        "dor_v2_" + "c" * 64,
        "not" + token,
        "var_" + token,
        token + "f",
        token + "_suffix",
        "dop_v1_" + "g" * 64,
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_azure_storage_account_key():
    # 64 bytes encoded in base64; synthetic key assembled from harmless pieces.
    account_key = ("Ab3/" * 21) + "Ab" + "=="
    assert len(account_key) == 88
    for prefix in ("AccountKey=", "accountkey = "):
        raw = "DefaultEndpointsProtocol=https;AccountName=sample;" + prefix + account_key + ";EndpointSuffix=core.windows.net"
        findings = find_secrets(raw)
        assert len(findings) == 1
        assert findings[0].kind == "azure_storage_account_key"
        assert account_key not in findings[0].redacted
        redacted = redact_text(raw)
        assert account_key not in redacted
        assert redacted_kinds(redacted) == ["azure_storage_account_key"]
    assert label_for_kind("azure_storage_account_key") == "Azure Storage account key"


def test_azure_storage_key_lookalikes_are_not_secrets():
    for ordinary in (
        "AccountKey=myAccountKey",  # placeholder in documentation
        "AccountKey=" + "A" * 85 + "==",  # shorter than 512 bits
        "AccountKey=" + "A" * 87 + "==",  # longer than 512 bits
        "AccountKey=" + "A" * 86 + "==suffix",  # not an entire value
        "StorageAccountKey=" + "A" * 86 + "==",  # unrelated field
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_and_redacts_sendgrid_api_key():
    # Assemble a synthetic key from fragments to avoid committed credentials.
    key = "SG." + "Ab3_" * 5 + "Q-" + "." + "Cd4-" * 10 + "x_7"
    raw = f"SendGrid credential: {key}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "sendgrid_api_key"
    assert key not in findings[0].redacted
    redacted = redact_text(raw)
    assert redacted == "SendGrid credential: «REDACTED:sendgrid_api_key»"
    assert key not in redacted
    assert redacted_kinds(redacted) == ["sendgrid_api_key"]
    assert label_for_kind("sendgrid_api_key") == "SendGrid API key"


def test_sendgrid_incomplete_or_extended_key_is_not_a_secret():
    assert not has_secret("SendGrid is a service, not a credential")
    assert not has_secret("SG." + "A" * 21 + "." + "B" * 43)
    assert not has_secret("SG." + "A" * 22 + "." + "B" * 42)
    assert not has_secret("SG." + "A" * 22 + "." + "B" * 44)


def test_detects_and_redacts_npm_access_token():
    # Synthetic fragments: no credential-shaped token literal is committed.
    token = "npm_" + "Ab3x" * 9
    raw = f"Use this npm credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "npm_token"
    assert token not in findings[0].redacted
    redacted = redact_text(raw)
    assert redacted == "Use this npm credential: «REDACTED:npm_token»"
    assert token not in redacted
    assert redacted_kinds(redacted) == ["npm_token"]
    assert label_for_kind("npm_token") == "npm access token"


def test_npm_prose_and_wrong_length_tokens_are_not_flagged():
    assert not has_secret("Run npm install before npm test")
    assert not has_secret("npm_" + "A" * 35)
    assert not has_secret("npm_" + "A" * 37)
    assert not has_secret("notnpm_" + "A" * 36)


def test_detects_and_redacts_pypi_api_token():
    token = "pypi-" + "Ab3_" * 22  # Synthetic base64url body, safely above PyPI's minimum length.
    raw = f"Python package upload credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "pypi_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Python package upload credential: «REDACTED:pypi_token»"
    assert redacted_kinds(redact_text(raw)) == ["pypi_token"]
    assert label_for_kind("pypi_token") == "PyPI API token"


def test_pypi_prose_and_short_values_are_not_flagged():
    assert not has_secret("Use twine to upload packages to PyPI")
    assert not has_secret("pypi-" + "A" * 84)
    assert not has_secret("notpypi-" + "A" * 90)


def test_detects_stripe_live_secret_and_restricted_keys_without_leaking():
    for prefix in ("sk_live_", "rk_live_"):
        fake_value = prefix + "A" * 24  # Synthetic fixture, no live credentials.
        findings = find_secrets(f"payment processor key: {fake_value}")
        assert len(findings) == 1
        assert findings[0].kind == "stripe_live_key"
        assert fake_value not in findings[0].redacted
        redacted = redact_text(f"payment processor key: {fake_value}")
        assert fake_value not in redacted
        assert redacted_kinds(redacted) == ["stripe_live_key"]
    assert label_for_kind("stripe_live_key") == "Stripe live secret or restricted key"


def test_stripe_public_and_short_keys_are_not_flagged():
    assert not has_secret("pk_live_" + "A" * 24)  # Publishable, not a secret.
    assert not has_secret("sk_live_" + "A" * 15)  # Too short to be a key.
    assert not has_secret("rk_test_" + "A" * 24)  # Only live keys in this scope.


def test_detects_and_redacts_stripe_webhook_signing_secrets():
    # Fake signing secret assembled from fragments to avoid scanner fixtures.
    secret = "wh" + "sec_" + "Ab3x" * 8
    raw = "Stripe webhook signing value: " + secret
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "stripe_webhook_secret"
    assert secret not in findings[0].redacted
    assert redact_text(raw) == "Stripe webhook signing value: «REDACTED:stripe_webhook_secret»"
    assert redacted_kinds(redact_text(raw)) == ["stripe_webhook_secret"]
    assert label_for_kind("stripe_webhook_secret") == "Stripe webhook signing secret"


def test_stripe_webhook_secret_prefix_and_boundary_lookalikes():
    token = "wh" + "sec_" + "Ab3x" * 8
    for ordinary in (
        "Configure Stripe webhook signing secrets",
        "wh" + "sec_" + "A" * 23,
        "wh" + "sec_" + "A" * 129,
        "prefix_" + token,
        token + "_suffix",
        "pk_live_" + "A" * 24,
    ):
        assert not has_secret(ordinary), ordinary[:80]


def test_detects_and_redacts_slack_incoming_webhook_url():
    # Assemble a synthetic Slack-style webhook without storing a complete URL.
    webhook = (
        "https://" + "hooks.slack.com/services/"
        + "T" + "0" * 8 + "/B" + "1" * 8 + "/" + "Ab3x" * 6
    )
    raw = "Send notifications to " + webhook
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "slack_webhook_url"
    assert webhook not in findings[0].redacted
    assert redact_text(raw) == "Send notifications to «REDACTED:slack_webhook_url»"
    assert redacted_kinds(redact_text(raw)) == ["slack_webhook_url"]
    assert label_for_kind("slack_webhook_url") == "Slack incoming webhook URL"


def test_slack_webhook_lookalikes_do_not_trigger():
    service_path = "/services/T" + "0" * 8 + "/B" + "1" * 8 + "/"
    for ordinary in (
        "https://hooks.slack.com/help",
        "https://example.org" + service_path + "A" * 24,
        "https://hooks.slack.com" + service_path + "A" * 19,
        "https://hooks.slack.com" + "/services/T" + "0" * 7 + "/B" + "1" * 8 + "/" + "A" * 24,
        "https://not-hooks.slack.com" + service_path + "A" * 24,
    ):
        assert not has_secret(ordinary), ordinary


def test_slack_gov_incoming_webhooks_are_redacted_with_public_slack_webhooks():
    # Slack Gov webhook URLs are bearer credentials just like commercial URLs.
    for host in ("hooks.slack.com", "hooks.slack-gov.com"):
        webhook = (
            "https://" + host + "/services/"
            + "T" + "0" * 8 + "/B" + "1" * 8 + "/" + "Ab3x" * 6
        )
        for raw in (webhook, f"Notify via {webhook}?thread_ts=1"):
            findings = find_secrets(raw)
            assert len(findings) == 1
            assert findings[0].kind == "slack_webhook_url"
            assert redact_text(raw) == raw.replace(webhook, "«REDACTED:slack_webhook_url»")
            assert redacted_kinds(redact_text(raw)) == ["slack_webhook_url"]
            assert not has_secret(redact_text(raw))


def test_slack_gov_webhook_host_and_path_lookalikes_do_not_trigger():
    path = "/services/T" + "0" * 8 + "/B" + "1" * 8 + "/" + "A" * 24
    for ordinary in (
        "https://hooks.slack-gov.com/help",
        "https://hooks.slack-gov.com.evil.example" + path,
        "https://not-hooks.slack-gov.com" + path,
        "https://hooks.slack-gov.com/services/T0000000/B11111111/" + "A" * 24,
        "https://hooks.slack-gov.com" + path[:-5],
        "prefix_https://hooks.slack-gov.com" + path,
    ):
        assert not has_secret(ordinary), ordinary


def test_detects_postgres_uri_password():
    uri = _uri("postgre" + "sql", "appuser", "Pg" + "x7QwZ9", "db.example.supabase.co", ":5432/appdb")
    assert any(x.kind == "connection_uri_password" for x in find_secrets(f"DATABASE_URL={uri}"))


def test_detects_neo4j_uri_password():
    uri = _uri("neo4j" + "+s", "neo4j", "Aura" + "Secret42", "abcd1234.databases.neo4j.io")
    assert has_secret(uri)


def test_detects_inline_secret_assignment():
    pwd = "hunter2" + "-demo-only"
    assert any(x.kind == "secret_assignment" for x in find_secrets(f'config: password = "{pwd}"'))


def test_detects_provider_prefixed_secret_assignments():
    # Hexadecimal auth tokens are not reliably detected by the entropy fallback.
    fake_twilio_token = "a1b2c3d4" * 4
    for key, value in [
        ("TWILIO_AUTH_TOKEN", fake_twilio_token),
        ("DB_PASSWORD", "fake-secret-12345"),
        ("OPENAI_API_KEY", "example-placeholder-key-123"),
        ("PAYMENTS_CLIENT_SECRET", "not-a-real-secret-987"),
    ]:
        raw = f"{key}={value}"
        findings = find_secrets(raw)
        assert any(f.kind == "secret_assignment" for f in findings), key
        assert value not in redact_text(raw), key
        assert redact_text(raw) == "«REDACTED:secret_assignment»", key


def test_provider_prefixed_assignment_negatives():
    for ordinary in [
        "GIT_COMMIT_SHA=" + "a1b2c3d4" * 4,
        "FEATURE_FLAG_ENABLED=abcdefgh12345678",
        "SECRET_HINT=not-a-credential",
        "myapisecret=just-a-description",
        "PAYMENTS_CLIENT_SECRET_HINT=use-the-vault",
    ]:
        assert not has_secret(ordinary), ordinary


def test_detects_private_key_block():
    header = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
    assert has_secret(header + "\nMIIEog...")


# --- redaction never leaks the value -----------------------------------------
def test_redaction_hides_value():
    tok = "hf_" + "ABCdef0123456789ABCDEFGHIJ"
    raw = f"token {tok} here"
    red = redact_text(raw)
    assert tok not in red
    assert "REDACTED" in red
    for f in find_secrets(raw):
        assert "0123456789" not in f.redacted


def test_redaction_preview_modes_and_invalid_setting_fail_closed():
    key = "hf_" + "Ab12" * 8  # synthetic; assembled to avoid scanner false alarms
    raw = f"credential {key}"
    expected = {
        "prefix+suffix": f"{key[:4]}…{key[-3:]} ({len(key)} chars)",
        "prefix": f"{key[:4]}… ({len(key)} chars)",
        "none": "***",
        "not-a-valid-mode": "***",
    }
    for mode, preview in expected.items():
        with patch.dict(os.environ, {"CF_REDACTION_PREVIEW": mode}):
            findings = find_secrets(raw)
            assert len(findings) == 1
            assert findings[0].redacted == preview
            assert key not in findings[0].redacted
            # Persistence/read-path redaction is independent of the preview mode.
            assert redact_text(raw) == "credential «REDACTED:huggingface_token»"


def test_redaction_preview_defaults_to_legacy_mode_for_long_tokens():
    key = "hf_" + "Ab12" * 8
    with patch.dict(os.environ, {}, clear=True):
        assert find_secrets(key)[0].redacted == f"{key[:4]}…{key[-3:]} ({len(key)} chars)"


def test_short_secrets_never_expose_prefix_suffix_or_length():
    for length in (8, 9, 19):
        value = "A" * length
        raw = f"password={value}"
        for mode in ("prefix+suffix", "prefix", "none"):
            with patch.dict(os.environ, {"CF_REDACTION_PREVIEW": mode}):
                findings = find_secrets(raw)
                assert len(findings) == 1
                assert findings[0].kind == "secret_assignment"
                assert findings[0].redacted == "***"
                assert redact_text(raw) == "«REDACTED:secret_assignment»"

    # The legacy preview remains available at the documented 20-char boundary.
    with patch.dict(os.environ, {"CF_REDACTION_PREVIEW": "prefix+suffix"}):
        assert find_secrets("password=" + "A" * 20)[0].redacted == "AAAA…AAA (20 chars)"


# --- negatives: should NOT be flagged ----------------------------------------
def test_ignores_plain_prose():
    assert not has_secret("The deploy command changed from make deploy-v1 to make deploy-v2.")


def test_ignores_git_sha():
    # 40-char hex commit sha — lowercase+digit only, must not trip the entropy fallback
    assert not has_secret("fixed in commit c5e8b8dc4c7d4ba81b1d9ad9450b01217a28c093 on dev")


def test_ignores_uuid():
    assert not has_secret("session id 9f8b7c6d-5e4f-3a2b-1c0d-abcdef012345 recorded")


def test_replicate_api_tokens_are_detected_and_redacted():
    token = "r8_" + "aB3x" * 9 + "Q"
    raw = f"Replicate credential: {token}"
    findings = find_secrets(raw)
    assert len(findings) == 1
    assert findings[0].kind == "replicate_api_token"
    assert token not in findings[0].redacted
    assert redact_text(raw) == "Replicate credential: «REDACTED:replicate_api_token»"
    assert redacted_kinds(redact_text(raw)) == ["replicate_api_token"]
    assert label_for_kind("replicate_api_token") == "Replicate API token"


def test_replicate_tokens_require_exact_length_and_boundaries():
    token = "r8_" + "aB3x" * 9 + "Q"
    for ordinary in (
        "r8_ tokens authenticate Replicate API requests",
        "r8_" + "A" * 36,
        "r8_" + "A" * 38,
        "r9_" + "A" * 37,
        "prefix_" + token,
        token + "_suffix",
        "r8_" + "A" * 100_000,
    ):
        assert not has_secret(ordinary), ordinary[:80]


if __name__ == "__main__":  # allow running without pytest
    import sys

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
