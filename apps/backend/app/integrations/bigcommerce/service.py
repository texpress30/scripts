"""BigCommerce credential persistence + feed source wiring.

Credentials live **encrypted at rest** in the shared ``integration_secrets``
table (Fernet, via ``integration_secrets_store``). We use a dedicated
``provider='bigcommerce'`` namespace with four secret keys scoped by the
merchant's ``store_hash`` (e.g. ``"abc123"``):

* ``access_token`` — permanent OAuth 2.0 token (no refresh needed).
* ``scope`` — space-separated scope list granted by the merchant.
* ``user_email`` — email of the user who installed the app.
* ``user_id`` — integer user id from the install payload.

``store_hash`` is used as the ``scope`` (rather than ``feed_sources.id``)
because the three JWT-authenticated callbacks (``load``, ``uninstall``,
``remove_user``) only know the store hash — not the source row id. This
mirrors the Shopify service which scopes its tokens by ``shop_domain``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.bigcommerce import config as bc_config
from app.services.integration_secrets_store import (
    integration_secrets_store,
)


logger = logging.getLogger(__name__)


PROVIDER = "bigcommerce"

SECRET_KEY_ACCESS_TOKEN = "access_token"
SECRET_KEY_SCOPE = "scope"
SECRET_KEY_USER_EMAIL = "user_email"
SECRET_KEY_USER_ID = "user_id"

BIGCOMMERCE_SECRET_KEYS: tuple[str, ...] = (
    SECRET_KEY_ACCESS_TOKEN,
    SECRET_KEY_SCOPE,
    SECRET_KEY_USER_EMAIL,
    SECRET_KEY_USER_ID,
)


def _mask_token(token: str | None) -> str:
    if not token:
        return ""
    value = str(token)
    if len(value) <= 8:
        return "***"
    return f"{value[:6]}***"


def store_bigcommerce_credentials(
    *,
    store_hash: str,
    access_token: str,
    scope: str,
    user_info: dict[str, Any] | None = None,
) -> None:
    """Persist the BigCommerce access token + metadata encrypted-at-rest.

    ``store_hash`` is the ``integration_secrets.scope`` column — multiple
    merchants connecting independently never collide.

    ``user_info`` is the ``user`` dict from the OAuth response (e.g.
    ``{"id": 9876543, "email": "user@example.com"}``). It's stored so the
    ``remove_user`` callback has something to compare against in a future
    multi-user flow.
    """
    clean_hash = bc_config.validate_store_hash(store_hash)
    if not access_token:
        raise ValueError("access_token is required to store BigCommerce credentials")

    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN,
        value=str(access_token),
        scope=clean_hash,
    )
    if scope:
        integration_secrets_store.upsert_secret(
            provider=PROVIDER,
            secret_key=SECRET_KEY_SCOPE,
            value=str(scope),
            scope=clean_hash,
        )
    if isinstance(user_info, dict):
        email = str(user_info.get("email") or "").strip()
        user_id = user_info.get("id")
        if email:
            integration_secrets_store.upsert_secret(
                provider=PROVIDER,
                secret_key=SECRET_KEY_USER_EMAIL,
                value=email,
                scope=clean_hash,
            )
        if user_id is not None:
            integration_secrets_store.upsert_secret(
                provider=PROVIDER,
                secret_key=SECRET_KEY_USER_ID,
                value=str(user_id),
                scope=clean_hash,
            )

    logger.info(
        "bigcommerce_credentials_stored store_hash=%s token=%s scope=%s",
        clean_hash,
        _mask_token(access_token),
        scope or "-",
    )


def get_bigcommerce_credentials(store_hash: str) -> dict[str, str] | None:
    """Return the decrypted credential bag for ``store_hash`` (or ``None``).

    The returned dict always contains ``access_token`` when present; the
    other keys (``scope``, ``user_email``, ``user_id``) are only populated
    when the merchant granted / supplied them.
    """
    try:
        clean_hash = bc_config.validate_store_hash(store_hash)
    except ValueError:
        return None

    token_row = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN,
        scope=clean_hash,
    )
    if token_row is None or not token_row.value.strip():
        return None

    result: dict[str, str] = {"access_token": token_row.value.strip()}
    for key in (SECRET_KEY_SCOPE, SECRET_KEY_USER_EMAIL, SECRET_KEY_USER_ID):
        row = integration_secrets_store.get_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=clean_hash,
        )
        if row is not None and row.value.strip():
            result[key] = row.value.strip()
    return result


def delete_bigcommerce_credentials(store_hash: str) -> None:
    """Remove every BigCommerce credential row keyed on ``store_hash``.

    Idempotent: missing rows are silently ignored by ``delete_secret``.
    Called by the ``uninstall`` callback handler after verifying the
    signed payload JWT.
    """
    try:
        clean_hash = bc_config.validate_store_hash(store_hash)
    except ValueError:
        return
    for key in BIGCOMMERCE_SECRET_KEYS:
        integration_secrets_store.delete_secret(
            provider=PROVIDER,
            secret_key=key,
            scope=clean_hash,
        )
    logger.info("bigcommerce_credentials_deleted store_hash=%s", clean_hash)


def get_access_token_for_store(store_hash: str) -> str | None:
    """Return just the decrypted access token for ``store_hash`` (or ``None``)."""
    creds = get_bigcommerce_credentials(store_hash)
    if creds is None:
        return None
    return creds.get("access_token")


def _list_connected_stores() -> list[str]:
    """List every store hash that currently has a stored BigCommerce token."""
    try:
        with integration_secrets_store._connect() as conn:  # noqa: SLF001
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scope
                    FROM integration_secrets
                    WHERE provider = %s AND secret_key = %s
                    ORDER BY scope ASC
                    """,
                    (PROVIDER, SECRET_KEY_ACCESS_TOKEN),
                )
                rows = cur.fetchall() or []
        return [str(row[0]) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("bigcommerce_list_connected_stores_failed error=%s", exc)
        return []


def list_installed_stores_with_metadata() -> list[dict[str, Any]]:
    """Return ``[{store_hash, installed_at, ...}, ...]`` for every installed store.

    Joins all per-store secret rows so the caller (the
    ``stores/available`` endpoint) can render an "available stores" list
    without N+1 round-trips. The ``installed_at`` timestamp is the
    ``updated_at`` of the access_token row.
    """
    try:
        with integration_secrets_store._connect() as conn:  # noqa: SLF001
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scope, secret_key, encrypted_value, updated_at
                    FROM integration_secrets
                    WHERE provider = %s
                    ORDER BY scope ASC
                    """,
                    (PROVIDER,),
                )
                rows = cur.fetchall() or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "bigcommerce_list_installed_stores_failed error=%s", exc
        )
        return []

    stores: dict[str, dict[str, Any]] = {}
    for row in rows:
        scope = str(row[0])
        secret_key = str(row[1])
        encrypted_value = str(row[2])
        updated_at = row[3]

        bucket = stores.setdefault(
            scope,
            {
                "store_hash": scope,
                "installed_at": None,
                "user_email": None,
                "scope": None,
                "_has_token": False,
            },
        )

        try:
            decrypted = integration_secrets_store.decrypt_secret(encrypted_value)
        except Exception:  # noqa: BLE001
            decrypted = ""

        if secret_key == SECRET_KEY_ACCESS_TOKEN:
            bucket["_has_token"] = True
            bucket["installed_at"] = updated_at
        elif secret_key == SECRET_KEY_USER_EMAIL:
            bucket["user_email"] = decrypted or None
        elif secret_key == SECRET_KEY_SCOPE:
            bucket["scope"] = decrypted or None

    return [b for b in stores.values() if b.pop("_has_token", False)]


def get_bigcommerce_status() -> dict[str, Any]:
    """Return integration status (configured + currently connected stores)."""
    configured = bc_config.oauth_configured()
    stores = _list_connected_stores() if configured else []
    return {
        "oauth_configured": configured,
        "connected_stores": stores,
        "token_count": len(stores),
    }
