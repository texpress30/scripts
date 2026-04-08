"""Magento 2 credential persistence (OAuth 1.0a four-legged tokens).

Credentials live **encrypted at rest** in the shared ``integration_secrets``
table (Fernet, via ``integration_secrets_store``). We use a dedicated
``provider='magento'`` namespace, with one row per secret key
(``consumer_key``, ``consumer_secret``, ``access_token``,
``access_token_secret``) scoped by the ``feed_sources`` row id.

This module is intentionally thin: it provides typed helpers that the
feed-sources router (future task) will call at create / read / delete time.
The Pydantic schemas in ``schemas.py`` own input validation + response
masking, and the DB migration in
``db/migrations/0055_feed_sources_magento_oauth.sql`` owns the new
non-sensitive columns on ``feed_sources`` itself.
"""

from __future__ import annotations

import logging

from app.services.integration_secrets_store import integration_secrets_store


logger = logging.getLogger(__name__)


PROVIDER = "magento"

SECRET_KEY_CONSUMER_KEY = "consumer_key"
SECRET_KEY_CONSUMER_SECRET = "consumer_secret"
SECRET_KEY_ACCESS_TOKEN = "access_token"
SECRET_KEY_ACCESS_TOKEN_SECRET = "access_token_secret"

MAGENTO_SECRET_KEYS: tuple[str, ...] = (
    SECRET_KEY_CONSUMER_KEY,
    SECRET_KEY_CONSUMER_SECRET,
    SECRET_KEY_ACCESS_TOKEN,
    SECRET_KEY_ACCESS_TOKEN_SECRET,
)


def _mask(value: str | None) -> str:
    if not value:
        return ""
    v = str(value)
    if len(v) <= 8:
        return "*" * len(v)
    return f"****{v[-4:]}"


def store_magento_credentials(
    *,
    source_id: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> None:
    """Persist the four OAuth 1.0a credentials encrypted-at-rest.

    ``source_id`` is the ``feed_sources.id`` UUID — used as the scope so
    multiple Magento sources (even for the same subaccount) never collide.
    All four keys are written atomically in a best-effort sequence; on any
    error we log and re-raise so the caller can rollback the feed_sources
    row.
    """
    if not source_id:
        raise ValueError("source_id is required to store Magento credentials")
    if not (consumer_key and consumer_secret and access_token and access_token_secret):
        raise ValueError("All four Magento OAuth 1.0a credentials are required")

    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_CONSUMER_KEY,
        value=consumer_key,
        scope=source_id,
    )
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_CONSUMER_SECRET,
        value=consumer_secret,
        scope=source_id,
    )
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN,
        value=access_token,
        scope=source_id,
    )
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN_SECRET,
        value=access_token_secret,
        scope=source_id,
    )
    logger.info(
        "magento_credentials_stored source_id=%s consumer_key=%s access_token=%s",
        source_id,
        _mask(consumer_key),
        _mask(access_token),
    )


def get_magento_credentials(source_id: str) -> dict[str, str] | None:
    """Return the four decrypted OAuth 1.0a credentials for ``source_id``.

    Returns ``None`` if any of the four keys is missing (partial state is
    treated as "not provisioned" — the caller should surface a reconnect
    prompt in that case).
    """
    if not source_id:
        return None

    creds: dict[str, str] = {}
    for key in MAGENTO_SECRET_KEYS:
        row = integration_secrets_store.get_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=source_id,
        )
        if row is None or not row.value.strip():
            return None
        creds[key] = row.value.strip()
    return creds


def delete_magento_credentials(source_id: str) -> None:
    """Remove every Magento credential row keyed on ``source_id``.

    Idempotent: missing rows are silently ignored by ``delete_secret``.
    Used both when a source is deleted and when the user triggers a
    reconnect flow.
    """
    if not source_id:
        return
    for key in MAGENTO_SECRET_KEYS:
        integration_secrets_store.delete_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=source_id,
        )
    logger.info("magento_credentials_deleted source_id=%s", source_id)


def mask_magento_credentials(credentials: dict[str, str] | None) -> dict[str, str]:
    """Return a fully-masked copy of ``credentials`` for API responses.

    Any missing key maps to an empty string. Safe to call on ``None``.
    """
    creds = credentials or {}
    return {
        "consumer_key": _mask(creds.get(SECRET_KEY_CONSUMER_KEY)),
        "consumer_secret": _mask(creds.get(SECRET_KEY_CONSUMER_SECRET)),
        "access_token": _mask(creds.get(SECRET_KEY_ACCESS_TOKEN)),
        "access_token_secret": _mask(creds.get(SECRET_KEY_ACCESS_TOKEN_SECRET)),
    }
