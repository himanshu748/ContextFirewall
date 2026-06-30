"""Pure authentication helpers for ContextFirewall write gating."""
from __future__ import annotations

import re
from typing import Optional

# Namespaces are caller-supplied tenant labels; keep them to a safe, bounded
# slug so a header value can't carry injection payloads or unbounded length.
RESERVED_NAMESPACE = "demo"
_NAMESPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def write_allowed(authorization: Optional[str], env_token: Optional[str]) -> bool:
    if not env_token:
        return True
    return authorization == f"Bearer {env_token}"


def sanitize_namespace(value: Optional[str]) -> Optional[str]:
    """Normalize a caller-supplied namespace, or None if it is empty/invalid."""
    if not value:
        return None
    candidate = value.strip().lower()
    return candidate if _NAMESPACE_RE.match(candidate) else None
