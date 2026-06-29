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

import math
import re
from dataclasses import dataclass
from typing import List

__all__ = ["SecretFinding", "find_secrets", "redact_text", "has_secret"]


@dataclass(frozen=True)
class SecretFinding:
    kind: str          # machine label, e.g. "huggingface_token"
    label: str         # human label, e.g. "Hugging Face token"
    redacted: str      # safe-to-display redacted form of the matched secret
    start: int
    end: int


# (kind, human label, regex). The optional last capture group, when present,
# isolates the secret value to redact (vs. the whole match).
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("huggingface_token", "Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{16,}\b")),
    ("openai_key", "OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b")),
    ("anthropic_key", "Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("aws_access_key", "AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", "Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("github_token", "GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", "Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
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
            r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b"
            r"\s*[:=]\s*[\"']?([^\s\"',;]{8,})"
        ),
    ),
]

# Long mixed-class token for the entropy fallback.
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/_\-]{32,}")


def _redact(secret: str) -> str:
    """Redact a secret to a safe, non-recoverable preview."""
    secret = secret.strip()
    if len(secret) <= 8:
        return (secret[:1] + "***") if secret else "***"
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
            value = m.group(m.lastindex) if m.lastindex else m.group(0)
            findings.append(SecretFinding(kind, label, _redact(value), m.start(), m.end()))
            spans.append((m.start(), m.end()))

    # Entropy fallback: only long, mixed-class, high-entropy tokens not already
    # covered. Requires upper+lower+digit to avoid git SHAs (hex) and UUIDs.
    for m in _TOKEN_RE.finditer(text):
        if _overlaps(m.start(), m.end(), spans):
            continue
        tok = m.group(0)
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
