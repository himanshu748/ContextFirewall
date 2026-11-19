"""Deployment options kept separate from Cognee initialization for easy testing."""
from __future__ import annotations

import os
from typing import Optional


def cors_allowed_origins(value: Optional[str] = None) -> list[str]:
    """Return explicit origins, preserving the public demo's wildcard default.

    An explicitly empty setting allows no cross-origin requests; a missing
    setting retains the original public-demo behavior.
    """
    raw = os.environ.get("CF_CORS_ORIGINS", "*") if value is None else value
    return list(dict.fromkeys(origin.strip() for origin in raw.split(",") if origin.strip()))


def api_key_db_ssl_mode(value: Optional[str] = None) -> str:
    """Choose a PostgreSQL SSL mode for asyncpg's API-key lookup connection."""
    raw = os.environ.get("CF_DB_SSLMODE", "require") if value is None else value
    mode = raw.strip().lower()
    if mode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ValueError("Invalid CF_DB_SSLMODE; expected a PostgreSQL SSL mode")
    return mode
