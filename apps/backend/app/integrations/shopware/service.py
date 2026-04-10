"""Credential persistence for the Shopware integration.

Stores Store Key and API Access Key encrypted at rest in the
``integration_secrets`` table.  Uses ``provider='shopware'`` so
credentials live in their own namespace.  Bridge Endpoint is
non-sensitive and stored in the ``feed_sources.config`` JSONB column.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.integration_secrets_store import integration_secrets_store


logger = logging.getLogger(__name__)

PROVIDER = "shopware"
SECRET_KEY_STORE_KEY = "api_key"
SECRET_KEY_API_ACCESS_KEY = "api_secret"


def _mask(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "*" * len(text)
    return f"****{text[-4:]}"


def store_credentials(
    *,
    source_id: str,
    store_key: str,
    api_access_key: str,
) -> None:
    """Persist Store Key and API Access Key encrypted at rest."""
    if not source_id:
        raise ValueError("source_id is required")
    if not store_key or not store_key.strip():
        raise ValueError("Store Key is required")
    if not api_access_key or not api_access_key.strip():
        raise ValueError("API Access Key is required")

    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_STORE_KEY,
        value=store_key.strip(),
        scope=source_id,
    )
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_API_ACCESS_KEY,
        value=api_access_key.strip(),
        scope=source_id,
    )
    logger.info(
        "shopware_credentials_stored source_id=%s store_key=%s",
        source_id,
        _mask(store_key),
    )


def get_credentials(*, source_id: str) -> dict[str, str] | None:
    """Return the decrypted ``{store_key, api_access_key}`` bag, or ``None``."""
    if not source_id:
        return None

    sk_row = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_STORE_KEY,
        scope=source_id,
    )
    if sk_row is None or not sk_row.value.strip():
        return None

    ak_row = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_API_ACCESS_KEY,
        scope=source_id,
    )
    if ak_row is None or not ak_row.value.strip():
        return None

    return {
        "store_key": sk_row.value.strip(),
        "api_access_key": ak_row.value.strip(),
    }


def delete_credentials(*, source_id: str) -> None:
    """Remove every credential row for this Shopware source."""
    if not source_id:
        return
    for key in (SECRET_KEY_STORE_KEY, SECRET_KEY_API_ACCESS_KEY):
        integration_secrets_store.delete_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=source_id,
        )
    logger.info("shopware_credentials_deleted source_id=%s", source_id)


def mask_credentials(credentials: dict[str, str] | None) -> dict[str, Any]:
    """Return a safe-to-display view of credentials."""
    creds = credentials or {}
    store_key = (creds.get("store_key") or "").strip()
    api_access_key = (creds.get("api_access_key") or "").strip()
    return {
        "has_credentials": bool(store_key),
        "store_key_masked": _mask(store_key) if store_key else None,
        "api_access_key_masked": _mask(api_access_key) if api_access_key else None,
    }
