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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.api.dependencies import (
    enforce_action_scope,
    enforce_subaccount_action,
    get_current_user,
)
from app.core.config import load_settings
from app.integrations.bigcommerce import auth as bc_auth
from app.integrations.bigcommerce import client as bc_client_module
from app.integrations.bigcommerce import config as bc_config
from app.integrations.bigcommerce import html_templates as bc_html
from app.integrations.bigcommerce import service as bc_service
from app.integrations.bigcommerce.auth import BigCommerceAuthError
from app.integrations.bigcommerce.client import (
    TEST_CONNECTION_TIMEOUT_SECONDS,
    BigCommerceClient,
)
from app.integrations.bigcommerce.exceptions import (
    BigCommerceAPIError,
    BigCommerceAuthError as _BCApiAuthError,
    BigCommerceConnectionError,
    BigCommerceNotFoundError,
    BigCommerceRateLimitError,
    BigCommerceServerError,
)
from app.integrations.bigcommerce.schemas import (
    BigCommerceAvailableStore,
    BigCommerceAvailableStoresResponse,
    BigCommerceCallbackResponse,
    BigCommerceClaimRequest,
    BigCommerceLoadResponse,
    BigCommerceRemoveUserResponse,
    BigCommerceSourceResponse,
    BigCommerceSourceUpdateRequest,
    BigCommerceStatusResponse,
    BigCommerceTestConnectionRequest,
    BigCommerceTestConnectionResponse,
    BigCommerceUninstallResponse,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceResponse,
    FeedSourceType,
    FeedSourceUpdate,
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
                bigcommerce_store_hash=store_hash,
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


def _auth_error_response(
    *,
    accept_header: str | None,
    status_code: int,
    message: str,
    store_hash: str | None = None,
) -> Response:
    """Return either an HTML error page (browser) or a JSON error (API client).

    BigCommerce renders the callback response in an iFrame inside the
    merchant's control panel, so a JSON blob would leak internal
    detail and make the merchant think the whole app is broken. The
    HTML branch surfaces a friendly "Instalare eșuată" page with the
    underlying reason displayed but safely escaped.
    """
    if bc_html.wants_json(accept_header):
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "error": message, "store_hash": store_hash},
        )
    html = bc_html.render_install_error(
        error_message=message, store_hash=store_hash
    )
    return HTMLResponse(content=html, status_code=status_code)


@router.get("/auth/callback")
def bigcommerce_auth_callback(
    request: Request,
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
) -> Response:
    """BigCommerce redirects the merchant here after they install the app.

    Exchanges the short-lived ``code`` for a permanent ``access_token`` and
    persists the full credential bag (token + scope + user info) encrypted at
    rest, keyed by ``store_hash``. When the caller includes a ``subaccount_id``
    query hint (e.g. the merchant was redirected from within an Omarosa
    admin session), we also create/refresh the matching ``feed_sources`` row.

    Content negotiation: the response is an HTML install-success page by
    default (BigCommerce renders this endpoint inside an iFrame in the
    merchant's control panel, so returning raw JSON is terrible UX). API
    clients can opt into the ``BigCommerceCallbackResponse`` JSON shape by
    sending ``Accept: application/json``.
    """
    _enforce_feature_flag()

    accept_header = request.headers.get("accept")

    if not bc_config.oauth_configured():
        return _auth_error_response(
            accept_header=accept_header,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=(
                "BigCommerce OAuth is not configured. "
                "Set BC_CLIENT_ID, BC_CLIENT_SECRET and BC_REDIRECT_URI."
            ),
        )

    try:
        store_hash = bc_auth.extract_store_hash(context)
    except ValueError as exc:
        return _auth_error_response(
            accept_header=accept_header,
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
        )

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
        http_status = exc.http_status or status.HTTP_400_BAD_REQUEST
        if http_status not in {400, 401, 403, 502, 503}:
            http_status = status.HTTP_400_BAD_REQUEST
        return _auth_error_response(
            accept_header=accept_header,
            status_code=http_status,
            message=str(exc),
            store_hash=store_hash,
        )

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
    except Exception:  # noqa: BLE001
        logger.exception("bigcommerce_credentials_store_failed store_hash=%s", store_hash)
        return _auth_error_response(
            accept_header=accept_header,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to persist BigCommerce access token",
            store_hash=store_hash,
        )

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

    if bc_html.wants_json(accept_header):
        return JSONResponse(
            content=BigCommerceCallbackResponse(
                success=True,
                store_hash=store_hash,
                scope=granted_scope,
                account_uuid=returned_uuid or None,
                message="BigCommerce OAuth connected. Access token stored securely.",
            ).model_dump()
        )

    html = bc_html.render_install_success(
        store_hash=store_hash,
        scope=granted_scope or None,
    )
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# 2. load_callback — GET /auth/load
# ---------------------------------------------------------------------------


@router.get("/auth/load")
def bigcommerce_load_callback(
    request: Request,
    signed_payload_jwt: str = Query(
        ..., min_length=1, description="HS256 signed payload JWT"
    ),
) -> Response:
    """BigCommerce calls this endpoint every time the merchant opens the app.

    The ``signed_payload_jwt`` is verified (HS256 with the app client secret)
    and the ``sub`` claim gives us the store hash + the currently-logged-in
    user + the store owner email.

    Content negotiation: the response is an HTML mini-dashboard by default
    (BigCommerce embeds this endpoint in an iFrame in the merchant's control
    panel, so returning raw JSON leaves the merchant staring at internal
    state). API clients can still opt into the ``BigCommerceLoadResponse``
    JSON shape by sending ``Accept: application/json``.
    """
    _enforce_feature_flag()
    _raise_if_oauth_unconfigured()

    accept_header = request.headers.get("accept")

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

    # Determine whether the store is "connected" — i.e. we actually have
    # credentials in integration_secrets for this store_hash. The happy
    # path is True; if the user uninstalled + reinstalled without us
    # seeing the auth callback it falls back to False and the load page
    # surfaces an "Inactiv" badge instead of "Activ".
    connected = bc_service.get_access_token_for_store(store_hash) is not None

    if bc_html.wants_json(accept_header):
        return JSONResponse(
            content=BigCommerceLoadResponse(
                status="ok",
                store_hash=store_hash,
                user_email=user_email,
                owner_email=owner_email,
            ).model_dump()
        )

    html = bc_html.render_load_page(
        store_hash=store_hash,
        user_email=user_email or None,
        owner_email=owner_email or None,
        connected=connected,
    )
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


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


# ---------------------------------------------------------------------------
# CRUD endpoints — claim, list, read, update, delete BigCommerce sources
# ---------------------------------------------------------------------------


def _source_to_bc_response(source: FeedSourceResponse) -> BigCommerceSourceResponse:
    """Project a generic ``FeedSourceResponse`` row onto the BigCommerce shape."""
    return BigCommerceSourceResponse(
        source_id=source.id,
        subaccount_id=source.subaccount_id,
        source_name=source.name,
        store_hash=source.bigcommerce_store_hash or "",
        catalog_type=source.catalog_type,
        catalog_variant=source.catalog_variant,
        connection_status=source.connection_status,
        has_token=source.has_token,
        token_scopes=source.token_scopes,
        last_connection_check=source.last_connection_check,
        last_error=source.last_error,
        is_active=source.is_active,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _require_bigcommerce_source(
    source_id: str, subaccount_id: int
) -> FeedSourceResponse:
    """Load a BigCommerce source row that MUST belong to ``subaccount_id``.

    Returns 404 — never 403 — for cross-tenant lookups so the API does not
    leak the existence of sources owned by other clients.
    """
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BigCommerce source not found",
        ) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BigCommerce source not found",
        )
    if source.source_type != FeedSourceType.bigcommerce:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BigCommerce source not found",
        )
    return source


@router.get(
    "/stores/available",
    response_model=BigCommerceAvailableStoresResponse,
)
def list_available_bigcommerce_stores(
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceAvailableStoresResponse:
    """Return BigCommerce stores that have installed the app but not yet been claimed.

    The set is ``{installed credentials in integration_secrets}`` minus
    ``{stores already linked to a feed_sources row}``. The endpoint is
    agency-scoped because the unclaimed pool is global — any agency admin
    can pick any unclaimed store and bind it to one of their subaccounts.
    """
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    installed = bc_service.list_installed_stores_with_metadata()
    claimed = _source_repo.list_claimed_bigcommerce_store_hashes()
    unclaimed = [
        BigCommerceAvailableStore(
            store_hash=str(entry.get("store_hash") or ""),
            installed_at=entry.get("installed_at"),
            user_email=entry.get("user_email"),
            scope=entry.get("scope"),
        )
        for entry in installed
        if str(entry.get("store_hash") or "") not in claimed
    ]
    unclaimed.sort(key=lambda item: item.store_hash)
    return BigCommerceAvailableStoresResponse(
        stores=unclaimed, total=len(unclaimed)
    )


@router.post(
    "/sources/claim",
    response_model=BigCommerceSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def claim_bigcommerce_source(
    payload: BigCommerceClaimRequest,
    subaccount_id: int = Query(
        ..., description="Subaccount that should own this BigCommerce source"
    ),
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceSourceResponse:
    """Bind an installed BigCommerce store to a subaccount.

    Pre-conditions checked here:

    1. ``store_hash`` has credentials in ``integration_secrets`` (i.e. the
       merchant has installed the app and the OAuth callback fired) — 404
       otherwise so we don't leak the unclaimed pool.
    2. ``store_hash`` is not already claimed by another row — 409 otherwise.

    On success the new ``feed_sources`` row starts in
    ``connection_status='pending'``; the caller should follow up with
    ``test-connection`` to flip it to ``connected``.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    try:
        clean_hash = bc_config.validate_store_hash(payload.store_hash)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if bc_service.get_access_token_for_store(clean_hash) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No installed BigCommerce store with this store_hash. "
                "Make sure the merchant has installed the app first."
            ),
        )

    try:
        created = _source_repo.create(
            FeedSourceCreate(
                subaccount_id=subaccount_id,
                source_type=FeedSourceType.bigcommerce,
                name=payload.source_name,
                config=FeedSourceConfig(store_url=f"stores/{clean_hash}"),
                catalog_type=payload.catalog_type,
                catalog_variant=payload.catalog_variant,
                bigcommerce_store_hash=clean_hash,
            )
        )
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This BigCommerce store is already claimed (by this subaccount "
                "or another). Detach the existing source first."
            ),
        ) from exc

    # Mirror the OAuth scope onto the row so the UI knows the granted scope
    # without re-reading the secrets store.
    creds = bc_service.get_bigcommerce_credentials(clean_hash) or {}
    granted_scope = creds.get("scope")
    try:
        refreshed = _source_repo.mark_oauth_connected(
            created.id, scopes=granted_scope or None
        )
    except FeedSourceNotFoundError:
        refreshed = created

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="bigcommerce.source.claimed",
        resource=f"feed_source:{refreshed.id}",
        details={
            "subaccount_id": subaccount_id,
            "store_hash": clean_hash,
            "scope": granted_scope,
        },
    )
    return _source_to_bc_response(refreshed)


@router.get("/sources", response_model=list[BigCommerceSourceResponse])
def list_bigcommerce_sources(
    subaccount_id: int = Query(..., description="Subaccount to scope the listing"),
    user: AuthUser = Depends(get_current_user),
) -> list[BigCommerceSourceResponse]:
    """List every BigCommerce source belonging to the requested subaccount."""
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    sources = _source_repo.get_bigcommerce_sources_by_subaccount(subaccount_id)
    return [_source_to_bc_response(src) for src in sources]


@router.get(
    "/sources/{source_id}", response_model=BigCommerceSourceResponse
)
def get_bigcommerce_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    source = _require_bigcommerce_source(source_id, subaccount_id)
    return _source_to_bc_response(source)


@router.put(
    "/sources/{source_id}", response_model=BigCommerceSourceResponse
)
def update_bigcommerce_source(
    source_id: str,
    payload: BigCommerceSourceUpdateRequest,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceSourceResponse:
    """Patch the cosmetic fields of a BigCommerce source.

    The ``store_hash`` itself is immutable post-claim — there's no use case
    for "point this row at a different merchant store" and silently
    swapping it would orphan any synced products.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    _require_bigcommerce_source(source_id, subaccount_id)

    has_any_update = any(
        value is not None
        for value in (
            payload.source_name,
            payload.catalog_type,
            payload.catalog_variant,
            payload.is_active,
        )
    )
    if not has_any_update:
        return _source_to_bc_response(_require_bigcommerce_source(source_id, subaccount_id))

    update_payload = FeedSourceUpdate(
        name=payload.source_name,
        catalog_type=payload.catalog_type,
        catalog_variant=payload.catalog_variant,
        is_active=payload.is_active,
    )
    try:
        updated = _source_repo.update(source_id, update_payload)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BigCommerce source not found",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="bigcommerce.source.updated",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "fields": {
                k: v
                for k, v in payload.model_dump(exclude_none=True).items()
            },
        },
    )
    return _source_to_bc_response(updated)


@router.delete("/sources/{source_id}")
def delete_bigcommerce_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Delete the ``feed_sources`` row but **leave the credentials in place**.

    This is the platform-side equivalent of "stop syncing this store" — the
    BigCommerce app is still installed on the merchant's side, the encrypted
    OAuth token still lives in ``integration_secrets``, and the store will
    show up again in ``stores/available`` so it can be re-claimed by the
    same or another subaccount.

    Actual app uninstallation only happens when the merchant clicks "Remove"
    in their BigCommerce control panel — that triggers the
    ``/auth/uninstall`` callback which wipes the credentials.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    source = _require_bigcommerce_source(source_id, subaccount_id)

    try:
        _source_repo.delete(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BigCommerce source not found",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="bigcommerce.source.deleted",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "store_hash": source.bigcommerce_store_hash,
        },
    )
    return {"status": "ok", "id": source_id}


# ---------------------------------------------------------------------------
# Test connection — pre-claim (by store_hash) + post-claim (by source_id)
# ---------------------------------------------------------------------------


async def _probe_store_info(client: BigCommerceClient) -> BigCommerceTestConnectionResponse:
    """Hit BigCommerce ``/v2/store`` and map the result to the normalised probe.

    Every BigCommerce exception is caught and folded into a
    ``success=False`` payload so callers always get a predictable shape.
    """
    try:
        data = await client.get("store", api_version="v2")
    except _BCApiAuthError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"Invalid credentials: {exc.message}"
        )
    except BigCommerceNotFoundError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"Endpoint not found: {exc.message}"
        )
    except BigCommerceRateLimitError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"Rate limit hit: {exc.message}"
        )
    except BigCommerceConnectionError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"Connection failed: {exc.message}"
        )
    except BigCommerceServerError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"BigCommerce server error: {exc.message}"
        )
    except BigCommerceAPIError as exc:
        return BigCommerceTestConnectionResponse(
            success=False, error=f"BigCommerce API error: {exc.message}"
        )

    if not isinstance(data, dict):
        return BigCommerceTestConnectionResponse(
            success=False,
            error="BigCommerce returned an unexpected /v2/store payload",
        )

    return BigCommerceTestConnectionResponse(
        success=True,
        store_name=str(data.get("name") or "") or None,
        domain=str(data.get("domain") or "") or None,
        secure_url=str(data.get("secure_url") or "") or None,
        currency=str(data.get("currency") or "") or None,
    )


@router.post(
    "/sources/{source_id}/test-connection",
    response_model=BigCommerceTestConnectionResponse,
)
async def test_bigcommerce_source_connection(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceTestConnectionResponse:
    """Probe a saved BigCommerce source using the stored encrypted credentials.

    On success/failure the outcome is recorded via
    ``FeedSourceRepository.record_connection_check`` so the source list UI
    can show a fresh badge without an extra round-trip.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    _require_bigcommerce_source(source_id, subaccount_id)

    try:
        client = bc_client_module.create_bc_client_from_source(
            source_id,
            timeout_seconds=TEST_CONNECTION_TIMEOUT_SECONDS,
        )
    except _BCApiAuthError:
        result = BigCommerceTestConnectionResponse(
            success=False,
            error="No credentials stored — reconnect required",
        )
    except ValueError as exc:
        result = BigCommerceTestConnectionResponse(success=False, error=str(exc))
    else:
        result = await _probe_store_info(client)

    try:
        if result.success:
            _source_repo.record_connection_check(source_id, success=True)
        else:
            _source_repo.record_connection_check(
                source_id, success=False, error=result.error
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "bigcommerce_probe_persist_failed source_id=%s", source_id, exc_info=True
        )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="bigcommerce.source.test_connection",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "success": result.success},
    )
    return result


@router.post(
    "/test-connection", response_model=BigCommerceTestConnectionResponse
)
async def test_bigcommerce_connection_pre_claim(
    payload: BigCommerceTestConnectionRequest,
    user: AuthUser = Depends(get_current_user),
) -> BigCommerceTestConnectionResponse:
    """Probe a not-yet-claimed BigCommerce store using the installed credentials.

    Used by the wizard "test before claim" button — the merchant can verify
    the install was wired correctly before binding the store to a
    subaccount. Resolves credentials by ``store_hash`` from the secrets
    store; the request body never carries an access token (BigCommerce
    is OAuth-only, there's no manual token entry path).
    """
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="data:write", scope="agency")

    try:
        clean_hash = bc_config.validate_store_hash(payload.store_hash)
    except ValueError as exc:
        return BigCommerceTestConnectionResponse(success=False, error=str(exc))

    try:
        client = bc_client_module.create_bc_client_from_store_hash(
            clean_hash,
            timeout_seconds=TEST_CONNECTION_TIMEOUT_SECONDS,
        )
    except _BCApiAuthError as exc:
        result = BigCommerceTestConnectionResponse(
            success=False,
            error=exc.message
            or "No BigCommerce credentials stored for this store_hash",
        )
    except ValueError as exc:
        result = BigCommerceTestConnectionResponse(success=False, error=str(exc))
    else:
        result = await _probe_store_info(client)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="bigcommerce.test_connection.pre_claim",
        resource="integration:bigcommerce",
        details={"store_hash": clean_hash, "success": result.success},
    )
    return result
