"""Credential persistence for the generic-API-key e-commerce platforms.

Stores the API key (and optional secret, depending on the platform) in
the shared ``integration_secrets`` table — Fernet-encrypted at rest via
``integration_secrets_store``. The provider name is the platform key
(``"prestashop"`` / ``"opencart"`` / etc.) so each platform gets its
own namespace and we never leak credentials across platforms.

The scope is the ``feed_sources.id`` UUID, mirroring the Magento
pattern. That keeps the same merchant store hashable independently
across multiple subaccounts and lets us key everything off the
``feed_sources`` row id without inventing a separate identifier.

This module also exposes a deliberately simple ``probe_store_url``
helper used by the test-connection endpoints. The full API validation
(actual REST call against the platform's catalog endpoint) lives in a
follow-up PR — for now we just verify the store URL responds to a
plain ``GET`` so the merchant gets a quick "your URL is reachable"
sanity check before claiming.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.integrations.generic_api_key.config import (
    PlatformDefinition,
    get_platform,
)
from app.services.integration_secrets_store import integration_secrets_store


logger = logging.getLogger(__name__)


SECRET_KEY_API_KEY = "api_key"
SECRET_KEY_API_SECRET = "api_secret"


def _mask(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "*" * len(text)
    return f"****{text[-4:]}"


def store_credentials(
    *,
    platform: str,
    source_id: str,
    api_key: str,
    api_secret: str | None = None,
) -> None:
    """Persist a platform's API key (+ optional secret) encrypted-at-rest.

    Raises ``ValueError`` for missing required fields. The
    :class:`PlatformDefinition` ``has_api_secret`` flag drives whether
    the secret half is required (Shopware, Lightspeed, OpenCart,
    Cart Storefront) or optional / unused (PrestaShop, Volusion).
    """
    definition = get_platform(platform)
    if not source_id:
        raise ValueError("source_id is required")
    if not api_key or not api_key.strip():
        raise ValueError(f"{definition.api_key_label} is required")
    if definition.has_api_secret and (not api_secret or not api_secret.strip()):
        raise ValueError(f"{definition.api_secret_label} is required")

    integration_secrets_store.upsert_secret(
        provider=definition.key,
        secret_key=SECRET_KEY_API_KEY,
        value=api_key.strip(),
        scope=source_id,
    )
    if api_secret and api_secret.strip():
        integration_secrets_store.upsert_secret(
            provider=definition.key,
            secret_key=SECRET_KEY_API_SECRET,
            value=api_secret.strip(),
            scope=source_id,
        )

    logger.info(
        "%s_credentials_stored source_id=%s api_key=%s",
        definition.key,
        source_id,
        _mask(api_key),
    )


def get_credentials(
    *,
    platform: str,
    source_id: str,
) -> dict[str, str] | None:
    """Return the decrypted ``{api_key[, api_secret]}`` bag, or ``None``."""
    definition = get_platform(platform)
    if not source_id:
        return None

    api_key_row = integration_secrets_store.get_secret(
        provider=definition.key,
        secret_key=SECRET_KEY_API_KEY,
        scope=source_id,
    )
    if api_key_row is None or not api_key_row.value.strip():
        return None

    result: dict[str, str] = {"api_key": api_key_row.value.strip()}

    if definition.has_api_secret:
        secret_row = integration_secrets_store.get_secret(
            provider=definition.key,
            secret_key=SECRET_KEY_API_SECRET,
            scope=source_id,
        )
        if secret_row is None or not secret_row.value.strip():
            # Half-configured pair → treat as not provisioned to keep
            # the test-connection / sync flows simple.
            return None
        result["api_secret"] = secret_row.value.strip()

    return result


def delete_credentials(
    *,
    platform: str,
    source_id: str,
) -> None:
    """Remove every credential row for ``platform`` + ``source_id``.

    Idempotent — missing rows are silently ignored. Called both at
    source-delete time (cleanup) and when the agency admin reconnects.
    """
    definition = get_platform(platform)
    if not source_id:
        return
    for key in (SECRET_KEY_API_KEY, SECRET_KEY_API_SECRET):
        integration_secrets_store.delete_secret(
            provider=definition.key,
            secret_key=key,
            scope=source_id,
        )
    logger.info(
        "%s_credentials_deleted source_id=%s",
        definition.key,
        source_id,
    )


def mask_credentials(
    platform: str,
    credentials: dict[str, str] | None,
) -> dict[str, Any]:
    """Return a safe-to-display view of ``credentials``.

    The frontend uses this to show "your API key on file is ****abcd"
    so the merchant can confirm which credential we're holding without
    seeing the raw value. The masked output never contains the full
    plaintext key.
    """
    definition = get_platform(platform)
    creds = credentials or {}
    api_key = (creds.get("api_key") or "").strip()
    api_secret = (creds.get("api_secret") or "").strip()
    return {
        "platform": definition.key,
        "has_credentials": bool(api_key),
        "api_key_masked": _mask(api_key) if api_key else None,
        "api_secret_masked": _mask(api_secret) if api_secret else None,
    }


def probe_store_url(url: str, *, timeout_seconds: float = 8.0) -> dict[str, Any]:
    """Best-effort reachability check on the store URL.

    A real API key probe is platform-specific (PrestaShop has its own
    Webservice handshake, Shopware has OAuth, OpenCart has a session
    login flow…) and lives in the per-platform connector PRs. For the
    stub we just GET the URL and report whether it responds with a
    non-server-error status. This catches typos / DNS errors / dead
    URLs without depending on the API client.

    The response shape is consistent with the existing test-connection
    endpoints (``success`` + ``message``) so the wizard's connection-
    test button doesn't need a special case for stub platforms.
    """
    if not url or not url.strip():
        return {
            "success": False,
            "message": "Store URL is required",
            "details": {},
        }
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return {
            "success": False,
            "message": f"Could not reach store: {exc}",
            "details": {"error_class": type(exc).__name__},
        }

    if response.status_code >= 500:
        return {
            "success": False,
            "message": (
                f"Store URL responded with HTTP {response.status_code} — "
                f"server error. Check the URL or try again later."
            ),
            "details": {"status_code": response.status_code},
        }

    return {
        "success": True,
        "message": (
            "Store URL is reachable. Full API validation coming soon."
        ),
        "details": {"status_code": response.status_code},
    }
