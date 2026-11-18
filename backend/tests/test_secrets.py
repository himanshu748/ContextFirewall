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
