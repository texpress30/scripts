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
    """List every store hash that currently has a stored BigCommerce token.

    Uses raw SQL against ``integration_secrets`` for a single-round-trip
    scan. Defensively calls ``_ensure_schema()`` first so a fresh
    deployment that hits ``/stores/available`` before any write never
    trips on a "relation does not exist" error.
    """
    try:
        integration_secrets_store._ensure_schema()  # noqa: SLF001
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

    This is the read-side twin of :func:`store_bigcommerce_credentials`. It
    MUST share the same identity keys as the write path (``provider`` +
    ``secret_key`` + ``scope``) so any store the auth callback writes is
    guaranteed to surface here.

    Implementation strategy — deliberately goes through the public
    ``integration_secrets_store`` API rather than raw SQL:

    1. Fetch the set of store hashes that own an ``access_token`` row via
       :func:`_list_connected_stores`. This uses the exact same
       ``WHERE provider=%s AND secret_key=%s`` predicate the write path
       hits at the DB level.
    2. For every hash, load the full credential bag via
       :func:`get_bigcommerce_credentials`, which itself calls
       ``integration_secrets_store.get_secret(...)`` — the exact symmetric
       API of ``upsert_secret`` used on the write side. This also triggers
       ``_ensure_schema`` so a worker that has never touched the table
       still sees a valid schema.
    3. Ask ``get_secret`` for the ``access_token`` row one more time to
       recover its ``updated_at`` timestamp (which the
       ``BigCommerceAvailableStore`` schema surfaces as ``installed_at``).

    This keeps the read path on the same code path as the write — there
    is no separate raw-SQL branch that can silently drift away from the
    encryption / schema bookkeeping done by ``upsert_secret``.
    """
    store_hashes = _list_connected_stores()
    if not store_hashes:
        return []

    results: list[dict[str, Any]] = []
    for store_hash in store_hashes:
        creds = get_bigcommerce_credentials(store_hash)
        if creds is None:
            # Defensive: the access_token row vanished between the scan
            # above and the per-store fetch. Skip rather than leak an
            # inconsistent partial entry.
            continue

        installed_at = None
        try:
            token_row = integration_secrets_store.get_secret(
                provider=PROVIDER,
                secret_key=SECRET_KEY_ACCESS_TOKEN,
                scope=store_hash,
            )
            if token_row is not None:
                installed_at = token_row.updated_at
        except Exception:  # noqa: BLE001
            installed_at = None

        results.append(
            {
                "store_hash": store_hash,
                "installed_at": installed_at,
                "user_email": creds.get(SECRET_KEY_USER_EMAIL) or None,
                "scope": creds.get(SECRET_KEY_SCOPE) or None,
            }
        )
    return results


def get_bigcommerce_status() -> dict[str, Any]:
    """Return integration status (configured + currently connected stores)."""
    configured = bc_config.oauth_configured()
    stores = _list_connected_stores() if configured else []
    return {
        "oauth_configured": configured,
        "connected_stores": stores,
        "token_count": len(stores),
    }
