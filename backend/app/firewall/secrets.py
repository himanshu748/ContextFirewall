"""Secret / sensitivity detection for ContextFirewall.

Pure-Python, no cognee, no network, so it is fast, deterministic, and trivially
unit-testable. The firewall's *secret check* uses this: any candidate memory whose
text contains a credential is BLOCKED before it can reach the trusted context pack,
and the reason it surfaces is always redacted so the secret is never re-leaked into
logs, the UI, or the pack itself.

Detection is two-layer:
  1. High-precision named patterns (HF tokens, OpenAI keys, AWS keys, JWTs,
     private-key blocks, DB connection URIs with inline passwords, `secret=...`
     assignments, ...).
  2. A conservative high-entropy fallback for long mixed-class tokens that don't
     match a named pattern, tuned to avoid flagging git SHAs / UUIDs.
"""
from __future__ import annotations

import base64
import binascii
import math
import os
import re
from dataclasses import dataclass
from typing import List

__all__ = ["SecretFinding", "find_secrets", "redact_text", "has_secret", "redacted_kinds", "label_for_kind"]


@dataclass(frozen=True)
class SecretFinding:
    kind: str          # machine label, e.g. "huggingface_token"
    label: str         # human label, e.g. "Hugging Face token"
    redacted: str      # safe-to-display redacted form of the matched secret
    start: int
    end: int


def _is_discord_bot_token(candidate: str) -> bool:
    """Check that the first segment is a canonical encoded Discord snowflake."""
    encoded_id = candidate.split(".", 1)[0]
    try:
        raw = base64.urlsafe_b64decode(encoded_id + "=" * (-len(encoded_id) % 4))
        decoded_id = raw.decode("ascii")
    except (binascii.Error, ValueError, UnicodeError):
        return False
    return (
        17 <= len(decoded_id) <= 20
        and decoded_id.isascii()
        and decoded_id.isdecimal()
        and base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") == encoded_id
    )


# (kind, human label, regex). The optional last capture group, when present,
# isolates the secret value to redact (vs. the whole match).
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("huggingface_token", "Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{16,}\b")),
    ("openai_key", "OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b")),
    ("anthropic_key", "Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    # LangSmith personal and service keys have distinct documented prefixes.
    # Match the full opaque body with boundaries; this is not a key validator.
    ("langsmith_key", "LangSmith API key", re.compile(
        r"(?<![A-Za-z0-9_-])lsv2_(?:pt|sk)_[A-Za-z0-9_-]{24,256}(?![A-Za-z0-9_-])"
    )),
    # Groq API keys have their own prefix; a bare key should not depend on
    # being labelled GROQ_API_KEY or passing the entropy fallback.
    ("groq_api_key", "Groq API key", re.compile(
        r"(?<![A-Za-z0-9_])gsk_[A-Za-z0-9]{30,}(?![A-Za-z0-9_])"
    )),
    # xAI documents its xai- prefix but not a fixed key length; require
    # identifier boundaries and a bounded opaque payload.
    ("xai_api_key", "xAI API key", re.compile(
        r"(?<![A-Za-z0-9_-])xai-[A-Za-z0-9_-]{24,128}(?![A-Za-z0-9_-])"
    )),
    # Resend documents the re_ key prefix. Use a conservative payload length
    # because it does not document a fixed full-key length.
    ("resend_api_key", "Resend API key", re.compile(
        r"(?<![A-Za-z0-9_-])re_[A-Za-z0-9_-]{24,128}(?![A-Za-z0-9_-])"
    )),
    # Databricks documents dapi-prefixed PATs with a 32-digit hexadecimal body.
    ("databricks_pat", "Databricks personal access token", re.compile(
        r"(?<![A-Za-z0-9_-])dapi[0-9a-fA-F]{32}(?![A-Za-z0-9_-])"
    )),
    ("aws_access_key", "AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", "Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    # Includes classic/OAuth/App credentials and fine-grained personal access tokens.
    ("github_token", "GitHub token", re.compile(
        r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})(?![A-Za-z0-9_])"
    )),
    ("gitlab_token", "GitLab access token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    # Legacy GitLab CI job tokens use glcbt- without dots. JWT-format job
    # tokens are handled by the JWT rule below; do not mask just their prefix.
    ("gitlab_ci_job_token", "GitLab CI/CD job token", re.compile(
        r"(?<![A-Za-z0-9_-])glcbt-[A-Za-z0-9_-]{20,128}(?![A-Za-z0-9_.-])"
    )),
    # GitLab runner authentication tokens use glrt- (or glrtr- via legacy registration).
    # Devise.friendly_token produces URL-safe Base64: both "_" and "-" are valid.
    ("gitlab_runner_token", "GitLab runner authentication token", re.compile(
        r"(?<![A-Za-z0-9_-])glrtr?-[A-Za-z0-9_-]{20,128}(?![A-Za-z0-9_-])"
    )),
    # GitLab deploy tokens have a distinct prefix from access/runner/job tokens.
    # This conservative length bound is a detector, not a complete validator.
    ("gitlab_deploy_token", "GitLab deploy token", re.compile(
        r"(?<![A-Za-z0-9_-])gldt-[A-Za-z0-9_-]{16,128}(?![A-Za-z0-9_-])"
    )),
    # Supabase's server-only API keys start with sb_secret_; sb_publishable_
    # is intentionally excluded. The body length is a conservative heuristic.
    ("supabase_secret_key", "Supabase secret API key", re.compile(
        r"(?<![A-Za-z0-9_-])sb_secret_[A-Za-z0-9_-]{24,128}(?![A-Za-z0-9_-])"
    )),

    # Telegram bot IDs can require up to 52 bits (16 decimal digits).
    # Keep the /bot API path prefix outside the redacted credential.
    ("telegram_bot_token", "Telegram bot token", re.compile(
        r"(?:(?<![A-Za-z0-9_])|(?<=/bot))[0-9]{8,16}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"
    )),
    # Shopify Admin API online and offline access tokens use the shpat_ prefix.
    # Exclude adjacent identifier characters to avoid redacting partial values.
    ("shopify_access_token", "Shopify Admin API access token", re.compile(
        r"(?<![A-Za-z0-9_])shpat_[A-Za-z0-9]{32}(?![A-Za-z0-9_])"
    )),
    # The legacy three-segment bot format starts with a base64url snowflake.
    # Validate the decoded ID to avoid redacting unrelated dotted identifiers.
    ("discord_bot_token", "Discord bot token", re.compile(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,38}(?![A-Za-z0-9_-])"
    )),
    # Incoming webhook URLs authenticate by webhook id and secret URL token;
    # leaking the URL permits posting messages without a separate bot key.
    ("discord_webhook_url", "Discord incoming webhook URL", re.compile(
        r"(?i)(?<![A-Za-z0-9._-])https://(?:discord\.com|discordapp\.com)/api(?:/v\d+)?/webhooks/"
        r"\d{17,20}/[A-Za-z0-9_-]{50,128}(?![A-Za-z0-9_-])"
    )),
    # Sentry org auth tokens contain a standard-Base64 payload (which may end
    # in = or ==) and an unpadded standard-Base64 secret, delimited by _.
    # Both segments can contain + and /; the boundary must consume them too.
    ("sentry_org_auth_token", "Sentry organization auth token", re.compile(
        r"(?<![A-Za-z0-9_])sntrys_[A-Za-z0-9+/]{10,}={0,2}_[A-Za-z0-9+/]{10,}(?![A-Za-z0-9+/=_-])"
    )),

    # DigitalOcean personal, OAuth and refresh tokens share a 64-char hex body.
    ("digitalocean_token", "DigitalOcean API token", re.compile(
        r"(?<![A-Za-z0-9_])(?:dop|doo|dor)_v1_[0-9a-f]{64}(?![A-Za-z0-9_])"
    )),
    # Replicate documents a fixed 40-character token: r8_ plus 37 opaque characters.
    ("replicate_api_token", "Replicate API token", re.compile(
        r"(?<![A-Za-z0-9_-])r8_[A-Za-z0-9_-]{37}(?![A-Za-z0-9_-])"
    )),
    # Cloudflare's newer API key, user-token, and account-token formats use
    # 40 alphanumeric characters followed by an eight-character hex checksum.
    ("cloudflare_api_credential", "Cloudflare API credential", re.compile(
        r"(?<![A-Za-z0-9_-])(?:cfk|cfut|cfat)_[A-Za-z0-9]{40}[0-9a-fA-F]{8}(?![A-Za-z0-9_-])"
    )),
    # 1Password service-account tokens are long, base64-encoded credentials;
    # the ops_eyJ prefix and 250-char minimum avoid broad false positives.
    ("onepassword_service_account_token", "1Password service account token", re.compile(
        r"(?<![A-Za-z0-9_])ops_eyJ[A-Za-z0-9+/]{250,}={0,3}(?![A-Za-z0-9_+/=])"
    )),
    # Grafana service-account credentials carry 32 alphanumerics and 8 hex checksum digits.
    ("grafana_service_account_token", "Grafana service account token", re.compile(
        r"(?<![A-Za-z0-9_-])glsa_[A-Za-z0-9]{32}_[0-9a-fA-F]{8}(?![A-Za-z0-9_-])"
    )),
    # Vault 1.10+ service, batch and recovery tokens use typed prefixes and
    # at least 24 random characters; legacy one-letter prefixes are ambiguous.
    ("hashicorp_vault_token", "HashiCorp Vault token", re.compile(
        r"(?<![A-Za-z0-9._-])hv[sbr]\.[A-Za-z0-9_-]{24,128}(?![A-Za-z0-9_-])"
    )),
    # Tailscale documents these five typed key prefixes. Match the modern
    # two-component key format to avoid mistaking prose for a credential.
    ("tailscale_token", "Tailscale API, auth, or integration key", re.compile(
        r"(?<![A-Za-z0-9_-])tskey-(?:api|auth|client|scim|webhook)-"
        r"[A-Za-z0-9]{8,32}-[A-Za-z0-9]{12,128}(?![A-Za-z0-9_-])"
    )),

    # Azure Storage account keys are 512-bit values (86 base64 chars plus ==).
    # Require the connection-string field name to avoid flagging unrelated data.
    ("azure_storage_account_key", "Azure Storage account key", re.compile(
        r"(?i)(?<![A-Za-z0-9_])AccountKey\s*=\s*([A-Za-z0-9+/]{86}==)(?![A-Za-z0-9+/=])"
    )),
    # NVIDIA NGC API keys have a distinct nvapi- prefix. Bound the opaque
    # payload to prevent matching prose identifiers or oversized partial keys.
    ("nvidia_ngc_api_key", "NVIDIA NGC API key", re.compile(
        r"(?<![A-Za-z0-9_-])nvapi-[A-Za-z0-9_-]{24,256}(?![A-Za-z0-9_-])"
    )),
    # SendGrid API keys contain two base64url segments of fixed lengths.
    ("sendgrid_api_key", "SendGrid API key", re.compile(r"(?<![A-Za-z0-9_-])SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")),
    ("npm_token", "npm access token", re.compile(r"(?<![A-Za-z0-9_])npm_[A-Za-z0-9]{36}(?![A-Za-z0-9])")),
    # Notion's current API tokens use ntn_ (legacy secret_ tokens still work).
    ("notion_token", "Notion integration token", re.compile(
        r"(?<![A-Za-z0-9_-])ntn_[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    )),
    # Docker Hub's personal and organization credentials have distinct prefixes.
    ("docker_hub_token", "Docker Hub access token", re.compile(
        r"(?<![A-Za-z0-9_-])dckr_(?:pat|oat)_[A-Za-z0-9_-]{20,128}(?![A-Za-z0-9_-])"
    )),
    # Linear prefixes distinguish personal API keys and OAuth access tokens.
    # Treat the opaque payload conservatively; this is not a token validator.
    ("linear_token", "Linear API or OAuth token", re.compile(
        r"(?<![A-Za-z0-9_-])lin_(?:api|oauth)_[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    )),
    # PyPI's secret-reporting API documents at least 85 base64url characters after pypi-.
    ("pypi_token", "PyPI API token", re.compile(r"(?<![A-Za-z0-9_-])pypi-[A-Za-z0-9_-]{85,}(?![A-Za-z0-9_-])")),
    # Vercel's 2026 token formats have distinct typed prefixes. The bounded
    # opaque-body heuristic is not a validator for every possible key length.
    ("vercel_credential", "Vercel API credential", re.compile(
        r"(?<![A-Za-z0-9_-])vc[piark]_[A-Za-z0-9]{40,80}(?![A-Za-z0-9_-])"
    )),
    # Public pk_live_ keys are intentionally excluded; only live secret or
    # restricted keys should block a memory.
    ("stripe_live_key", "Stripe live secret or restricted key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    # Webhook signing secrets authenticate inbound Stripe events and are
    # sensitive even in test mode; unlike pk_ keys they are not publishable.
    ("stripe_webhook_secret", "Stripe webhook signing secret", re.compile(
        r"(?<![A-Za-z0-9_-])whsec_[A-Za-z0-9]{24,128}(?![A-Za-z0-9_-])"
    )),
    ("slack_token", "Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    # Slack app-level tokens, including their rotating xoxe.xapp- form.
    ("slack_app_level_token", "Slack app-level token", re.compile(
        r"(?<![A-Za-z0-9_-])(?:xoxe\.)?xapp-[A-Za-z0-9-]{20,256}(?![A-Za-z0-9_-])"
    )),
    # Incoming webhook URLs are bearer credentials: their final path segment
    # permits posting to a channel without a separate API token.
    ("slack_webhook_url", "Slack incoming webhook URL", re.compile(
        r"(?i)(?<![A-Za-z0-9._-])https://hooks\.(?:slack|slack-gov)\.com/services/"
        r"[TE][A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{20,}(?![A-Za-z0-9])"
    )),
    ("jwt", "JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")),
    (
        "private_key_block",
        "private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ),
    (
        "connection_uri_password",
        "database connection URI with inline password",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|neo4j(?:\+s|\+ssc)?|bolt(?:\+s)?)"
            r"://[^\s:@/]+:([^\s:@/]{3,})@",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        "inline secret assignment",
        re.compile(
            # Allow provider prefixes such as TWILIO_AUTH_TOKEN and DB_PASSWORD;
            # the sensitive suffix must still be a whole identifier component.
            r"(?i)(?<![A-Za-z0-9_])(?:[A-Za-z][A-Za-z0-9]*[_-])*"
            r"(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b"
            r"\s*[:=]\s*[\"']?([^\s\"',;]{8,})"
        ),
    ),
]

# Long mixed-class token for the entropy fallback.
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/_\-]{32,}")
# Publishable Supabase keys are intended for client-side use, not secrets.
# Restrict the exemption to the documented 22-random + '_' + 8-checksum
# shape. Other high-entropy text (including malformed or extended keys)
# still goes through the normal fallback detector.
_PUBLIC_SUPABASE_KEY_RE = re.compile(r"sb_publishable_[A-Za-z0-9_-]{22}_[A-Za-z0-9_-]{8}")


def _redact(secret: str) -> str:
    """Build a display-only preview; never expose fragments of short secrets.

    Invalid preview settings fail closed to a fully masked value. The mode only
    controls audit-reason previews, not the typed markers used by ``redact_text``.
    """
    secret = secret.strip()
    mode = os.getenv("CF_REDACTION_PREVIEW", "prefix+suffix").strip().lower()
    if len(secret) < 20 or mode not in ("prefix", "prefix+suffix"):
        return "***"
    if mode == "prefix":
        return f"{secret[:4]}… ({len(secret)} chars)"
    return f"{secret[:4]}…{secret[-3:]} ({len(secret)} chars)"


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(s < end and start < e for s, e in spans)


def find_secrets(text: str, *, entropy_threshold: float = 4.2) -> List[SecretFinding]:
    """Return all secret findings in ``text`` (possibly empty)."""
    if not text:
        return []

    findings: list[SecretFinding] = []
    spans: list[tuple[int, int]] = []

    for kind, label, pat in _PATTERNS:
        for m in pat.finditer(text):
            if kind == "discord_bot_token" and not _is_discord_bot_token(m.group(0)):
                continue
            if kind == "telegram_bot_token" and int(m.group(0).split(":", 1)[0]) >= (1 << 52):
                continue
            value = m.group(m.lastindex) if m.lastindex else m.group(0)
            findings.append(SecretFinding(kind, label, _redact(value), m.start(), m.end()))
            spans.append((m.start(), m.end()))

    # Entropy fallback: only long, mixed-class, high-entropy tokens not already
    # covered. Requires upper+lower+digit to avoid git SHAs (hex) and UUIDs.
    for m in _TOKEN_RE.finditer(text):
        if _overlaps(m.start(), m.end(), spans):
            continue
        tok = m.group(0)
        if _PUBLIC_SUPABASE_KEY_RE.fullmatch(tok):
            continue
        has_upper = any(c.isupper() for c in tok)
        has_lower = any(c.islower() for c in tok)
        has_digit = any(c.isdigit() for c in tok)
        if has_upper and has_lower and has_digit and _shannon_entropy(tok) >= entropy_threshold:
            findings.append(
                SecretFinding("high_entropy_token", "high-entropy token", _redact(tok), m.start(), m.end())
            )
            spans.append((m.start(), m.end()))

    findings.sort(key=lambda f: (f.start, f.end))
    return findings


def redact_text(text: str) -> str:
    """Return ``text`` with every detected secret replaced by a typed marker."""
    findings = find_secrets(text or "")
    if not findings:
        return text or ""
    out: list[str] = []
    last = 0
    for f in findings:
        if f.start < last:  # skip overlaps already consumed
            continue
        out.append(text[last:f.start])
        out.append(f"«REDACTED:{f.kind}»")
        last = f.end
    out.append(text[last:])
    return "".join(out)


def has_secret(text: str) -> bool:
    return bool(find_secrets(text or ""))


_KIND_LABEL = {kind: label for kind, label, _ in _PATTERNS}
_KIND_LABEL["high_entropy_token"] = "high-entropy token"
_MARKER_RE = re.compile(r"«REDACTED:([A-Za-z0-9_]+)»")


def redacted_kinds(text: str) -> List[str]:
    """Secret kinds already redacted in ``text`` (markers written at ingest time)."""
    return _MARKER_RE.findall(text or "")


def label_for_kind(kind: str) -> str:
    """Human label for a secret kind (e.g. aws_access_key -> AWS access key id)."""
    return _KIND_LABEL.get(kind, kind.replace("_", " "))
