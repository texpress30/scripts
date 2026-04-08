"""FastAPI router for the BigCommerce Feed Integration (OAuth 2.0 Public App).

BigCommerce public-app flow (see https://developer.bigcommerce.com/docs/integrations/apps/guide):

1. Merchant installs the app from the marketplace / Draft Apps.
2. BigCommerce calls ``auth_callback`` with ``code``, ``scope``, ``context``,
   ``account_uuid`` — we exchange the code for a permanent ``access_token``
   and persist it encrypted-at-rest keyed by the store hash.
3. Each subsequent app launch calls ``load_callback`` with a
   ``signed_payload_jwt`` — we verify it and return session info.
4. When the merchant removes the app, BigCommerce calls ``uninstall_callback``
   (also with a signed JWT) — we delete the stored credentials and mark every
   ``feed_sources`` row bound to that store hash as disconnected.
5. For multi-user stores, a user revocation triggers ``remove_user_callback``
   — we log it (no per-user state today, but the hook is wired in for the
   future multi-user feature).

All four endpoints mirror the Shopify OAuth + webhook pattern:

* No ``Depends(get_current_user)`` — BigCommerce calls these endpoints
  directly, and we authenticate via the signed JWT (``load``/``uninstall``/
  ``remove_user``) or via the HTTPS + short-lived ``code`` + server-side
  token exchange (``auth_callback``).
* A global feature flag guards every endpoint so we can dark-launch the
  integration without exposing public routes.
* Audit log entries are best-effort — failures never block BigCommerce's
  callback response (same policy as the Shopify webhook handlers).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import load_settings
from app.integrations.bigcommerce import auth as bc_auth
from app.integrations.bigcommerce import config as bc_config
from app.integrations.bigcommerce import service as bc_service
from app.integrations.bigcommerce.auth import BigCommerceAuthError
from app.integrations.bigcommerce.schemas import (
    BigCommerceCallbackResponse,
    BigCommerceLoadResponse,
    BigCommerceRemoveUserResponse,
    BigCommerceStatusResponse,
    BigCommerceUninstallResponse,
)
from app.services.audit import audit_log_service
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceType,
)
from app.services.feed_management.repository import FeedSourceRepository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/bigcommerce", tags=["bigcommerce", "integrations"])

_source_repo = FeedSourceRepository()


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


def _raise_if_oauth_unconfigured() -> None:
    if not bc_config.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "BigCommerce OAuth is not configured. "
                "Set BC_CLIENT_ID, BC_CLIENT_SECRET and BC_REDIRECT_URI."
            ),
        )


def _bigcommerce_error_to_http(exc: BigCommerceAuthError) -> HTTPException:
    code = exc.http_status or status.HTTP_400_BAD_REQUEST
    if code not in {400, 401, 403, 502}:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


def _ensure_feed_source(
    *,
    store_hash: str,
    subaccount_id: int | None,
    scope: str,
) -> str | None:
    """Create or refresh a ``feed_sources`` row for the given store hash.

    Returns the source id on success, or ``None`` when we don't have enough
    information to attach a source row (e.g. the callback arrived without a
    ``subaccount_id`` hint). The token itself is always stored regardless —
    this helper only manages the feed_sources metadata row.
    """
    if not subaccount_id:
        logger.info(
            "bigcommerce_feed_source_skip_no_subaccount store_hash=%s", store_hash
        )
        return None

    existing = _source_repo.get_by_bigcommerce_store_hash(store_hash)
    matching = [src for src in existing if src.subaccount_id == subaccount_id]
    if matching:
        source = matching[0]
        try:
            _source_repo.mark_oauth_connected(source.id, scopes=scope or None)
        except FeedSourceNotFoundError:
            return None
        logger.info(
            "bigcommerce_feed_source_refreshed source_id=%s store_hash=%s",
            source.id,
            store_hash,
        )
        return source.id

    try:
        created = _source_repo.create(
            FeedSourceCreate(
                subaccount_id=subaccount_id,
                source_type=FeedSourceType.bigcommerce,
                name=f"BigCommerce store {store_hash}",
                config=FeedSourceConfig(store_url=f"stores/{store_hash}"),
                shop_domain=store_hash,
            )
        )
    except FeedSourceAlreadyExistsError:
        logger.warning(
            "bigcommerce_feed_source_duplicate store_hash=%s subaccount_id=%s",
            store_hash,
            subaccount_id,
        )
        return None

    try:
        _source_repo.mark_oauth_connected(created.id, scopes=scope or None)
    except FeedSourceNotFoundError:
        return created.id

    logger.info(
        "bigcommerce_feed_source_created source_id=%s store_hash=%s subaccount_id=%s",
        created.id,
        store_hash,
        subaccount_id,
    )
    return created.id


# ---------------------------------------------------------------------------
# 1. auth_callback — GET /auth/callback
# ---------------------------------------------------------------------------


@router.get("/auth/callback", response_model=BigCommerceCallbackResponse)
def bigcommerce_auth_callback(
    code: str = Query(..., min_length=1, description="Short-lived authorization code"),
    scope: str = Query("", description="Space-separated scope list granted by the merchant"),
    context: str = Query(..., min_length=1, description="stores/{store_hash}"),
    account_uuid: str | None = Query(
        default=None, description="Account UUID returned by BigCommerce"
    ),
    subaccount_id: int | None = Query(
        default=None,
        description="Optional Omarosa subaccount to attach this store to",
    ),
) -> BigCommerceCallbackResponse:
    """BigCommerce redirects the merchant here after they install the app.

    Exchanges the short-lived ``code`` for a permanent ``access_token`` and
    persists the full credential bag (token + scope + user info) encrypted at
    rest, keyed by ``store_hash``. When the caller includes a ``subaccount_id``
    query hint (e.g. the merchant was redirected from within an Omarosa
    admin session), we also create/refresh the matching ``feed_sources`` row.
    """
    _enforce_feature_flag()
    _raise_if_oauth_unconfigured()

    try:
        store_hash = bc_auth.extract_store_hash(context)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        payload = bc_auth.exchange_code_for_token(
            code=code,
            scope=scope,
            context=context,
        )
    except BigCommerceAuthError as exc:
        logger.warning(
            "bigcommerce_auth_callback_exchange_failed store_hash=%s status=%s err=%s",
            store_hash,
            exc.http_status,
            exc,
        )
        raise _bigcommerce_error_to_http(exc) from exc

    access_token = str(payload.get("access_token") or "").strip()
    granted_scope = str(payload.get("scope") or scope or "").strip()
    user_info = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    returned_uuid = str(payload.get("account_uuid") or account_uuid or "").strip()

    try:
        bc_service.store_bigcommerce_credentials(
            store_hash=store_hash,
            access_token=access_token,
            scope=granted_scope,
            user_info=user_info,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("bigcommerce_credentials_store_failed store_hash=%s", store_hash)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist BigCommerce access token",
        ) from exc

    source_id = _ensure_feed_source(
        store_hash=store_hash,
        subaccount_id=subaccount_id,
        scope=granted_scope,
    )

    try:
        audit_log_service.log(
            actor_email=str((user_info or {}).get("email") or "bigcommerce-install"),
            actor_role="system",
            action="bigcommerce.auth.callback",
            resource="integration:bigcommerce",
            details={
                "store_hash": store_hash,
                "scope": granted_scope,
                "account_uuid": returned_uuid,
                "feed_source_id": source_id,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_auth_callback_audit_log_failed store_hash=%s", store_hash
        )

    logger.info(
        "bigcommerce_auth_callback_ok store_hash=%s scope=%s source_id=%s",
        store_hash,
        granted_scope,
        source_id,
    )

    return BigCommerceCallbackResponse(
        success=True,
        store_hash=store_hash,
        scope=granted_scope,
        account_uuid=returned_uuid or None,
        message="BigCommerce OAuth connected. Access token stored securely.",
    )


# ---------------------------------------------------------------------------
# 2. load_callback — GET /auth/load
# ---------------------------------------------------------------------------


@router.get("/auth/load", response_model=BigCommerceLoadResponse)
def bigcommerce_load_callback(
    signed_payload_jwt: str = Query(
        ..., min_length=1, description="HS256 signed payload JWT"
    ),
) -> BigCommerceLoadResponse:
    """BigCommerce calls this endpoint every time the merchant opens the app.

    The ``signed_payload_jwt`` is verified (HS256 with the app client secret)
    and the ``sub`` claim gives us the store hash. In a full-featured app we'd
    mint a short-lived session cookie and redirect the iFrame to the frontend
    app shell; for this slice we just return the decoded session info so the
    router can be unit-tested end-to-end.
    """
    _enforce_feature_flag()
    _raise_if_oauth_unconfigured()

    try:
        claims = bc_auth.verify_signed_payload_jwt(
            signed_payload_jwt,
            bc_config.BC_CLIENT_SECRET,
            client_id=bc_config.BC_CLIENT_ID,
        )
    except BigCommerceAuthError as exc:
        logger.warning("bigcommerce_load_jwt_invalid err=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    sub = str(claims.get("sub") or "")
    try:
        store_hash = bc_auth.extract_store_hash(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    user = claims.get("user") if isinstance(claims.get("user"), dict) else {}
    owner = claims.get("owner") if isinstance(claims.get("owner"), dict) else {}
    user_email = str((user or {}).get("email") or "")
    owner_email = str((owner or {}).get("email") or "")

    try:
        audit_log_service.log(
            actor_email=user_email or "bigcommerce-load",
            actor_role="system",
            action="bigcommerce.load",
            resource="integration:bigcommerce",
            details={
                "store_hash": store_hash,
                "user_email": user_email,
                "owner_email": owner_email,
                "url": claims.get("url"),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_load_callback_audit_log_failed store_hash=%s", store_hash
        )

    logger.info(
        "bigcommerce_load_callback_ok store_hash=%s user=%s",
        store_hash,
        user_email or "-",
    )

    return BigCommerceLoadResponse(
        status="ok",
        store_hash=store_hash,
        user_email=user_email,
        owner_email=owner_email,
    )


# ---------------------------------------------------------------------------
# 3. uninstall_callback — GET /auth/uninstall
# ---------------------------------------------------------------------------


@router.get("/auth/uninstall", response_model=BigCommerceUninstallResponse)
def bigcommerce_uninstall_callback(
    signed_payload_jwt: str = Query(
        ..., min_length=1, description="HS256 signed payload JWT"
    ),
) -> BigCommerceUninstallResponse:
    """BigCommerce calls this endpoint when the merchant removes the app.

    Verifies the JWT, extracts the store hash, marks every ``feed_sources``
    row bound to the store as ``disconnected`` and wipes the encrypted
    credentials. Always returns 200 on a valid JWT — internal cleanup errors
    are logged but never surfaced (BigCommerce will retry on non-2xx).
    """
    _enforce_feature_flag()
    _raise_if_oauth_unconfigured()

    try:
        claims = bc_auth.verify_signed_payload_jwt(
            signed_payload_jwt,
            bc_config.BC_CLIENT_SECRET,
            client_id=bc_config.BC_CLIENT_ID,
        )
    except BigCommerceAuthError as exc:
        logger.warning("bigcommerce_uninstall_jwt_invalid err=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    sub = str(claims.get("sub") or "")
    try:
        store_hash = bc_auth.extract_store_hash(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    sources_disconnected = 0
    try:
        sources_disconnected = _source_repo.mark_disconnected_by_bigcommerce_store_hash(
            store_hash,
            reason="App uninstalled by merchant",
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_uninstall_mark_disconnected_failed store_hash=%s",
            store_hash,
        )

    try:
        bc_service.delete_bigcommerce_credentials(store_hash)
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_uninstall_delete_token_failed store_hash=%s", store_hash
        )

    try:
        audit_log_service.log(
            actor_email="bigcommerce-uninstall",
            actor_role="system",
            action="bigcommerce.uninstall",
            resource="integration:bigcommerce",
            details={
                "store_hash": store_hash,
                "sources_disconnected": sources_disconnected,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_uninstall_audit_log_failed store_hash=%s", store_hash
        )

    logger.info(
        "bigcommerce_uninstall_callback_ok store_hash=%s sources_disconnected=%d",
        store_hash,
        sources_disconnected,
    )

    return BigCommerceUninstallResponse(
        status="ok",
        store_hash=store_hash,
        sources_disconnected=sources_disconnected,
    )


# ---------------------------------------------------------------------------
# 4. remove_user_callback — GET /auth/remove-user
# ---------------------------------------------------------------------------


@router.get("/auth/remove-user", response_model=BigCommerceRemoveUserResponse)
def bigcommerce_remove_user_callback(
    signed_payload_jwt: str = Query(
        ..., min_length=1, description="HS256 signed payload JWT"
    ),
) -> BigCommerceRemoveUserResponse:
    """BigCommerce calls this endpoint when a multi-user store revokes a user.

    For the current single-user model this is effectively a logging hook —
    we verify the JWT, extract the user info and write an audit log entry.
    When multi-user support lands, this handler will wipe the per-user
    session row for ``user_email`` in the store identified by ``store_hash``.
    """
    _enforce_feature_flag()
    _raise_if_oauth_unconfigured()

    try:
        claims = bc_auth.verify_signed_payload_jwt(
            signed_payload_jwt,
            bc_config.BC_CLIENT_SECRET,
            client_id=bc_config.BC_CLIENT_ID,
        )
    except BigCommerceAuthError as exc:
        logger.warning("bigcommerce_remove_user_jwt_invalid err=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    sub = str(claims.get("sub") or "")
    try:
        store_hash = bc_auth.extract_store_hash(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    user = claims.get("user") if isinstance(claims.get("user"), dict) else {}
    user_email = str((user or {}).get("email") or "")

    try:
        audit_log_service.log(
            actor_email=user_email or "bigcommerce-remove-user",
            actor_role="system",
            action="bigcommerce.remove_user",
            resource="integration:bigcommerce",
            details={
                "store_hash": store_hash,
                "user_email": user_email,
                "user_id": (user or {}).get("id"),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "bigcommerce_remove_user_audit_log_failed store_hash=%s", store_hash
        )

    logger.info(
        "bigcommerce_remove_user_callback_ok store_hash=%s user=%s",
        store_hash,
        user_email or "-",
    )

    return BigCommerceRemoveUserResponse(
        status="ok",
        store_hash=store_hash,
        user_email=user_email,
    )


# ---------------------------------------------------------------------------
# Status endpoint (for internal tooling / smoke tests)
# ---------------------------------------------------------------------------


@router.get("/status", response_model=BigCommerceStatusResponse)
def bigcommerce_status() -> BigCommerceStatusResponse:
    """Report whether the integration is configured and which stores are connected."""
    _enforce_feature_flag()
    payload = bc_service.get_bigcommerce_status()
    return BigCommerceStatusResponse(
        oauth_configured=bool(payload["oauth_configured"]),
        connected_stores=list(payload["connected_stores"]),
        token_count=int(payload["token_count"]),
    )
