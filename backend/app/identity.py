"""Per-request identity resolution for ContextFirewall.

An authenticated caller presents ``Authorization: Bearer cf_live_...`` — an API
key minted by the console (Supabase Auth) and tied to that account's private
namespace. We never store the raw key, only its SHA-256, so resolution is:

    bearer key --sha256--> key_hash --(cf_api_keys)--> namespace

An authenticated caller's reads are scoped to just their own ``<namespace>`` —
their console never mixes in the public sample data. Anonymous callers (no
key) get read-only access to the public ``demo`` namespace only.

The key table lives in the same Supabase Postgres the Cognee runtime already
uses, so we resolve keys with asyncpg over the existing ``DB_*`` connection vars
(no extra service-role secret). ``CF_WRITE_TOKEN`` is kept as an optional admin
override that writes to the shared ``public`` namespace.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from fastapi import HTTPException
from dataclasses import dataclass, field
from typing import Optional, Set

DEMO_NAMESPACE = "demo"
PUBLIC_NAMESPACE = "public"
API_KEY_PREFIX = "cf_live_"
logger = logging.getLogger(__name__)
_INVALID_KEY = "Invalid or revoked ContextFirewall API key. Create a new key in Account & keys."
_STORE_UNAVAILABLE = "API key verification is temporarily unavailable. Try again later."


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hex of a raw API key — the only form we ever persist or compare."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def looks_like_api_key(token: Optional[str]) -> bool:
    return bool(token) and token.startswith(API_KEY_PREFIX)


@dataclass
class Identity:
    """Resolved caller. ``namespace`` is the write target; reads use ``read_namespaces``."""

    kind: str  # "apikey" | "admin" | "anon"
    namespace: str = PUBLIC_NAMESPACE
    can_write: bool = False
    allow_demo_write: bool = False
    read_namespaces: Set[str] = field(default_factory=lambda: {DEMO_NAMESPACE})


def _anonymous() -> Identity:
    return Identity(kind="anon", namespace=PUBLIC_NAMESPACE, can_write=False, read_namespaces={DEMO_NAMESPACE})


def llm_checks_allowed(ident: Identity) -> bool:
    """Whether this caller may trigger the LLM-backed checks.

    Those checks run on the deployment's own inference token, so an anonymous
    caller on the public demo gets the deterministic checks only and cannot
    spend the host's credits.
    """
    return ident.kind != "anon"


_pool = None


async def _get_pool():
    """Lazily build an asyncpg pool to the Supabase Postgres (prod only)."""
    global _pool
    if _pool is not None:
        return _pool
    host = os.getenv("DB_HOST")
    if not host:
        return None  # dev profile: no managed Postgres, so no API-key store
    import asyncpg

    _pool = await asyncpg.create_pool(
        host=host,
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USERNAME", ""),
        password=os.getenv("DB_PASSWORD", ""),
        ssl="require",
        min_size=1,
        max_size=4,
    )
    return _pool


async def _namespace_for_key(raw_key: str) -> Optional[str]:
    """Resolve an API key; distinguish unknown/revoked keys from store outages.

    An unavailable key store must not silently substitute public demo memory
    for an authenticated caller's private data.
    """
    try:
        pool = await _get_pool()
        if pool is None:
            logger.error("API key verification unavailable: no key store configured")
            raise HTTPException(status_code=503, detail=_STORE_UNAVAILABLE)
        key_hash = hash_api_key(raw_key)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "select namespace from public.cf_api_keys where key_hash = $1 and revoked_at is null",
                key_hash,
            )
            if row is None:
                return None
            # Best-effort usage stamp; never let it fail the request.
            try:
                await conn.execute(
                    "update public.cf_api_keys set last_used_at = now() where key_hash = $1",
                    key_hash,
                )
            except Exception:  # noqa: BLE001
                pass
        return str(row["namespace"])
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Never log key material, SQL parameters or raw DB exception messages.
        logger.error("API key verification failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_STORE_UNAVAILABLE) from None


async def resolve_identity(authorization: Optional[str], env_write_token: Optional[str] = None) -> Identity:
    """Resolve the caller from the Authorization header.

    A valid API key wins (its private namespace), then the optional admin
    override. Only an absent Authorization header may use anonymous demo-read.
    """
    token = bearer_token(authorization)
    if looks_like_api_key(token):
        ns = await _namespace_for_key(token)  # type: ignore[arg-type]
        if ns:
            return Identity(
                kind="apikey",
                namespace=ns,
                can_write=True,
                allow_demo_write=False,
                read_namespaces={ns},
            )
        raise HTTPException(status_code=401, detail=_INVALID_KEY)
    env_token = env_write_token if env_write_token is not None else os.getenv("CF_WRITE_TOKEN")
    if env_token and token and hmac.compare_digest(token.encode(), env_token.encode()):
        return Identity(
            kind="admin",
            namespace=PUBLIC_NAMESPACE,
            can_write=True,
            allow_demo_write=False,
            read_namespaces={DEMO_NAMESPACE, PUBLIC_NAMESPACE},
        )
    if authorization:
        raise HTTPException(status_code=401, detail=_INVALID_KEY)
    return _anonymous()
