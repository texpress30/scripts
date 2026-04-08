"""BigCommerce Feed Integration configuration (Public App - OAuth 2.0).

BigCommerce apps are installed by the merchant from the App Marketplace (or
from ``My Draft Apps`` while under development). The ``auth_callback`` URL
registered on the Developer Portal receives a short-lived ``code`` plus the
merchant ``context`` (``stores/{store_hash}``) and exchanges it for a
permanent ``access_token`` via ``POST https://login.bigcommerce.com/oauth2/token``.

All four callback endpoints (``auth_callback``, ``load_callback``,
``uninstall_callback``, ``remove_user_callback``) are verified with a
``signed_payload_jwt`` signed with ``HS256`` using the app's client secret —
we verify it with stdlib ``hmac`` + ``hashlib`` (no PyJWT dependency).
"""

from __future__ import annotations

import os
import re


# --- Public endpoints (no env override — BigCommerce-controlled) ------------

BC_LOGIN_URL: str = "https://login.bigcommerce.com"
BC_API_URL: str = "https://api.bigcommerce.com"
BC_TOKEN_URL: str = f"{BC_LOGIN_URL}/oauth2/token"
BC_API_VERSION: str = "v3"

# Default scope list. Read-only is sufficient for product feed ingest; the
# merchant can always grant additional scopes by reinstalling the app.
_DEFAULT_SCOPES = " ".join(
    [
        "store_v2_products_read_only",
        "store_v2_content_read_only",
        "store_v2_information_read_only",
    ]
)

# --- Env-backed configuration ------------------------------------------------

BC_CLIENT_ID: str = os.environ.get("BC_CLIENT_ID", "")
BC_CLIENT_SECRET: str = os.environ.get("BC_CLIENT_SECRET", "")
BC_CLIENT_UUID: str = os.environ.get("BC_CLIENT_UUID", "")
BC_REDIRECT_URI: str = os.environ.get(
    "BC_REDIRECT_URI",
    "https://admin.omarosa.ro/agency/integrations/bigcommerce/callback",
)
BC_SCOPES: str = os.environ.get("BC_SCOPES", _DEFAULT_SCOPES)


_STORE_HASH_RE = re.compile(r"^[a-z0-9]+$")


def oauth_configured() -> bool:
    """Return ``True`` when all three critical BigCommerce credentials exist."""
    return bool(
        BC_CLIENT_ID.strip()
        and BC_CLIENT_SECRET.strip()
        and BC_REDIRECT_URI.strip()
    )


def require_oauth_configured() -> None:
    """Raise ``RuntimeError`` when critical env vars are missing.

    Called from the router at request time (and optionally from startup wiring)
    so misconfigured deployments fail loudly instead of silently 500-ing on
    the first install attempt.
    """
    missing: list[str] = []
    if not BC_CLIENT_ID.strip():
        missing.append("BC_CLIENT_ID")
    if not BC_CLIENT_SECRET.strip():
        missing.append("BC_CLIENT_SECRET")
    if not BC_REDIRECT_URI.strip():
        missing.append("BC_REDIRECT_URI")
    if missing:
        raise RuntimeError(
            "BigCommerce OAuth is not configured. Missing env vars: "
            + ", ".join(missing)
        )


def validate_store_hash(store_hash: str) -> str:
    """Return a cleaned lowercase store hash or raise ``ValueError``."""
    cleaned = (store_hash or "").strip().lower()
    if not cleaned:
        raise ValueError("BigCommerce store hash is required")
    if not _STORE_HASH_RE.match(cleaned):
        raise ValueError(
            f"Invalid BigCommerce store hash (expected [a-z0-9]+): {store_hash!r}"
        )
    return cleaned


def get_bigcommerce_store_api_base_url(store_hash: str) -> str:
    """Return the versioned BigCommerce Store API base URL for ``store_hash``.

    Example: ``https://api.bigcommerce.com/stores/abc123/v3``.
    """
    cleaned = validate_store_hash(store_hash)
    return f"{BC_API_URL}/stores/{cleaned}/{BC_API_VERSION}"
