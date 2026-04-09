"""File source credential persistence (HTTP Basic Auth for URL fetch).

Many third-party product feeds live behind HTTP Basic Auth — the client
enters a username + password pair in their feed provider's admin and
gives us the URL + credentials. We store the credentials **encrypted at
rest** in the shared ``integration_secrets`` table (Fernet, via
``integration_secrets_store``), keyed on the ``feed_sources.id`` UUID so
multiple file sources (even for the same subaccount) never collide.

This mirrors the ``app/integrations/magento/service.py`` layout — same
pattern, same primitive. The two secret keys are:

* ``auth_username`` — plaintext-returnable, shown masked in API responses
* ``auth_password`` — never round-trips back to the frontend; only the
  connector layer reads it to stitch the Basic Auth header.

Google Sheets sources intentionally never call these helpers — their
access model is "public URL" or "share with service account", not
HTTP Basic Auth.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.integration_secrets_store import integration_secrets_store


logger = logging.getLogger(__name__)


PROVIDER = "file_source"

SECRET_KEY_USERNAME = "auth_username"
SECRET_KEY_PASSWORD = "auth_password"

FILE_SOURCE_SECRET_KEYS: tuple[str, ...] = (
    SECRET_KEY_USERNAME,
    SECRET_KEY_PASSWORD,
)


def _mask(value: str | None) -> str:
    """Return a password-safe masked form of ``value`` for API responses."""
    if not value:
        return ""
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return "****"


def store_file_source_credentials(
    *,
    source_id: str,
    username: str,
    password: str,
) -> None:
    """Persist HTTP Basic Auth credentials encrypted-at-rest.

    ``source_id`` is the ``feed_sources.id`` UUID — used as the secret
    store scope so multiple file sources can coexist without colliding.
    Both ``username`` and ``password`` are required and non-empty;
    passing empty strings raises ``ValueError`` so the caller can
    surface a 400 instead of silently storing a partial pair.
    """
    if not source_id:
        raise ValueError("source_id is required to store file source credentials")
    if not username:
        raise ValueError("username is required to store file source credentials")
    if not password:
        raise ValueError("password is required to store file source credentials")

    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_USERNAME,
        value=username,
        scope=source_id,
    )
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_PASSWORD,
        value=password,
        scope=source_id,
    )
    logger.info(
        "file_source_credentials_stored source_id=%s username=%s",
        source_id,
        username,
    )


def get_file_source_credentials(source_id: str) -> dict[str, str] | None:
    """Return the decrypted ``{username, password}`` bag for ``source_id``.

    Returns ``None`` when either secret is missing so the caller treats
    partial state as "not provisioned" — we never hand back a
    username-only pair that would confuse the connector's ``auth=`` tuple.
    """
    if not source_id:
        return None

    username_row = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_USERNAME,
        scope=source_id,
    )
    password_row = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_PASSWORD,
        scope=source_id,
    )
    if username_row is None or password_row is None:
        return None

    username = username_row.value.strip()
    password = password_row.value.strip()
    if not username or not password:
        return None
    return {"username": username, "password": password}


def delete_file_source_credentials(source_id: str) -> None:
    """Remove every file-source credential row keyed on ``source_id``.

    Idempotent: missing rows are silently ignored by
    ``IntegrationSecretsStore.delete_secret``. Called both by the
    update endpoint (when the agency admin clears the auth panel) and
    by the delete endpoint (cleanup on source deletion).
    """
    if not source_id:
        return
    for key in FILE_SOURCE_SECRET_KEYS:
        integration_secrets_store.delete_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=source_id,
        )
    logger.info("file_source_credentials_deleted source_id=%s", source_id)


def mask_file_source_credentials(
    credentials: dict[str, str] | None,
) -> dict[str, Any]:
    """Return a safe-to-display view of ``credentials``.

    Used by the API response serialiser to tell the frontend "this
    source has auth enabled; here is the username you can edit; the
    password stays server-side". A ``None`` input maps to a no-auth
    descriptor (``has_auth=False``) so callers don't need to branch.
    """
    creds = credentials or {}
    username = (creds.get("username") or "").strip()
    password = (creds.get("password") or "").strip()
    has_auth = bool(username and password)
    return {
        "has_auth": has_auth,
        "username": username or None,
        "password_masked": _mask(password) if password else None,
    }
