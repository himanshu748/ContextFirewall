"""Pure authentication helpers for ContextFirewall write gating."""
from __future__ import annotations

from typing import Optional


def write_allowed(authorization: Optional[str], env_token: Optional[str]) -> bool:
    if not env_token:
        return True
    return authorization == f"Bearer {env_token}"
