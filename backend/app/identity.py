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
from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)

DEMO_NAMESPACE = "demo"
PUBLIC_NAMESPACE = "public"
API_KEY_PREFIX = "cf_live_"


class IdentityError(Exception):
    """Identity resolution failed in a way the caller must hear about.

    Carries the HTTP ``status_code`` / ``detail`` the REST layer should
    return; over MCP the detail surfaces as the tool error. Raised only
    when a credential was *presented* but could not be honoured — callers
    that send no credential still resolve to anonymous (see
    :func:`resolve_identity`).
    """

    status_code = 500
    detail = "Identity resolution failed."

    def __init__(self, detail: Optional[str] = None) -> None:
        self.detail = detail or type(self).detail
        super().__init__(self.detail)


class InvalidApiKeyError(IdentityError):
    """A ``cf_live_`` key was presented but is unknown or revoked."""

    status_code = 401
    detail = (
        "The API key provided is unknown or has been revoked. "
        "Sign in to the console to mint a new key."
    )


class KeyStoreUnavailableError(IdentityError):
    """The API-key store is configured but unreachable."""

    status_code = 503
    detail = "The API key store is temporarily unavailable; please retry shortly."


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


async def _key_lookup(raw_key: str) -> Tuple[str, Optional[str]]:
    """Look a raw key up in the store.

    Returns ``(status, namespace)`` where ``status`` is one of:

    - ``"ok"`` — key found and not revoked; ``namespace`` is its namespace.
    - ``"unknown"`` — the store answered, but no live key matches (the key
      is unknown or revoked; the query filters revoked rows out).
    - ``"unavailable"`` — a store is configured but the lookup failed
      (connection loss, missing migration, ...). Logged, never silent.
    - ``"not_configured"`` — no key store on this deployment (dev profile
      without ``DB_HOST``), so keys cannot be checked at all.
    """
    try:
        pool = await _get_pool()
    except Exception:  # noqa: BLE001
        logger.exception("API key store unavailable: could not open a connection pool")
        return "unavailable", None
    if pool is None:
        return "not_configured", None
    key_hash = hash_api_key(raw_key)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "select namespace from public.cf_api_keys where key_hash = $1 and revoked_at is null",
                key_hash,
            )
            if row is None:
                return "unknown", None
            # Best-effort usage stamp; never let it fail the request.
            try:
                await conn.execute(
                    "update public.cf_api_keys set last_used_at = now() where key_hash = $1",
                    key_hash,
                )
            except Exception:  # noqa: BLE001
                pass
        return "ok", str(row["namespace"])
    except Exception:  # noqa: BLE001
        logger.exception("API key store unavailable: key lookup failed")
        return "unavailable", None


async def resolve_identity(authorization: Optional[str], env_write_token: Optional[str] = None) -> Identity:
    """Resolve the caller from the Authorization header.

    Order: a valid API key wins (its account namespace); otherwise the optional
    ``CF_WRITE_TOKEN`` admin override; otherwise anonymous demo-read.

    Anonymous is only for callers that present *no* credential. A presented
    ``cf_live_`` key that the store rejects raises :class:`InvalidApiKeyError`
    (401) and a key store that cannot be reached raises
    :class:`KeyStoreUnavailableError` (503) — silently downgrading either to
    anonymous would hand the caller demo data as if it were their own (#45).
    On a deployment with no key store configured at all (dev profile), an
    API-key-shaped token still resolves to anonymous: there is nothing to
    check it against, and anonymous grants no privileges.
    """
    token = bearer_token(authorization)
    if looks_like_api_key(token):
        status, ns = await _key_lookup(token)  # type: ignore[arg-type]
        if status == "ok" and ns:
            return Identity(
                kind="apikey",
                namespace=ns,
                can_write=True,
                allow_demo_write=False,
                read_namespaces={ns},
            )
        if status == "unknown":
            logger.warning(
                "Rejected unknown or revoked API key (sha256 prefix %s)",
                hash_api_key(token)[:8],  # type: ignore[arg-type]
            )
            raise InvalidApiKeyError()
        if status == "unavailable":
            raise KeyStoreUnavailableError()
        return _anonymous()  # no key store configured (dev profile)
    env_token = env_write_token if env_write_token is not None else os.getenv("CF_WRITE_TOKEN")
    if env_token and token and hmac.compare_digest(token.encode(), env_token.encode()):
        return Identity(
            kind="admin",
            namespace=PUBLIC_NAMESPACE,
            can_write=True,
            allow_demo_write=False,
            read_namespaces={DEMO_NAMESPACE, PUBLIC_NAMESPACE},
        )
    return _anonymous()
