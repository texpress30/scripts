from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.schemas.client import (
    AttachGoogleAccountRequest,
    AttachPlatformAccountRequest,
    BusinessInputsImportRequest,
    BusinessInputsImportResponse,
    CreateClientRequest,
    DetachGoogleAccountRequest,
    DetachPlatformAccountRequest,
    UpdateClientProfileRequest,
    MediaBuyingConfigUpdateRequest,
    MediaBuyingLeadDailyValueUpsertRequest,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import PlatformAccountAlreadyAttachedError, client_registry_service
from app.services.client_business_inputs_import_service import client_business_inputs_import_service
from app.services.media_buying_store import media_buying_store
from app.services.sync_constants import (
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PLATFORM_PINTEREST_ADS,
    PLATFORM_SNAPCHAT_ADS,
    PLATFORM_TIKTOK_ADS,
)

router = APIRouter(prefix="/clients", tags=["clients"])

_SUPPORTED_PLATFORMS = {
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PLATFORM_TIKTOK_ADS,
    PLATFORM_PINTEREST_ADS,
    PLATFORM_SNAPCHAT_ADS,
    "reddit_ads",
}


def _looks_like_feature_flag_disabled_error(value: object | None) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return "disabled by feature flag" in normalized


def _is_success_run_status(value: object | None) -> bool:
    return str(value or "").strip().lower() in {"done", "success", "completed"}


def _suppress_stale_tiktok_feature_flag_errors(*, items: list[dict[str, object]], sync_enabled: bool) -> None:
    if not sync_enabled:
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        if bool(item.get("has_active_sync")):
            continue
        if _looks_like_feature_flag_disabled_error(item.get("last_error")):
            item["last_error"] = None
            if "last_error_category" in item:
                item["last_error_category"] = None
            if "last_error_details" in item:
                item["last_error_details"] = None


def _suppress_stale_tiktok_recent_errors_after_success(*, items: list[dict[str, object]]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        if bool(item.get("has_active_sync")):
            continue
        if not _is_success_run_status(item.get("last_run_status")):
            continue
        if item.get("last_success_at") is None:
            continue
        if item.get("last_error") is None:
            continue
        item["last_error"] = None
        if "last_error_category" in item:
            item["last_error_category"] = None
        if "last_error_details" in item:
            item["last_error_details"] = None


def _suppress_stale_recent_errors_after_success(*, items: list[dict[str, object]]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        if bool(item.get("has_active_sync")):
            continue
        if not _is_success_run_status(item.get("last_run_status")):
            continue
        if item.get("last_success_at") is None:
            continue
        if item.get("last_error") is None:
            continue
        item["last_error"] = None
        if "last_error_category" in item:
            item["last_error_category"] = None
        if "last_error_details" in item:
            item["last_error_details"] = None


def _normalize_platform_or_422(platform: str) -> str:
    normalized = str(platform or "").strip().lower()
    if normalized not in _SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported platform '{platform}'. Allowed values: {sorted(_SUPPORTED_PLATFORMS)}",
        )
    return normalized


def _is_platform_sync_enabled(platform: str) -> bool:
    normalized = _normalize_platform_or_422(platform)
    settings = load_settings()
    if normalized == PLATFORM_TIKTOK_ADS:
        return bool(settings.ff_tiktok_integration)
    if normalized == PLATFORM_PINTEREST_ADS:
        return bool(settings.ff_pinterest_integration)
    if normalized == PLATFORM_SNAPCHAT_ADS:
        return bool(settings.ff_snapchat_integration)
    return True


def _attach_platform_account(*, client_id: int, platform: str, account_id: str) -> dict[str, str | int | None]:
    normalized_platform = _normalize_platform_or_422(platform)
    normalized_account_id = str(account_id).strip()
    if normalized_account_id == "":
        raise HTTPException(status_code=400, detail="account_id is required")

    try:
        updated = client_registry_service.attach_platform_account_to_client(
            platform=normalized_platform,
            client_id=client_id,
            account_id=normalized_account_id,
        )
    except PlatformAccountAlreadyAttachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Platform account is already attached to another client",
                "platform": exc.platform,
                "account_id": exc.account_id,
                "client_id": exc.existing_client_id,
            },
        ) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="Client or platform account not found")

    return updated


@router.get("")
def list_clients(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, str | int | None]]]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")

    records = client_registry_service.list_clients()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.list",
        resource="client",
        details={"count": len(records)},
    )
    return {"items": records}


@router.post("")
def create_client(payload: CreateClientRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str | int | None]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    created = client_registry_service.create_client(name=payload.name, owner_email=user.email)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.create",
        resource=f"client:{created['id']}",
        details={"name": payload.name},
    )
    return created


@router.get("/accounts/summary")
def platform_account_summary(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, str | int | None]]]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items = client_registry_service.platform_account_summary()
    for item in items:
        if isinstance(item, dict):
            item["sync_enabled"] = _is_platform_sync_enabled(str(item.get("platform") or ""))
    return {"items": items}


@router.get("/accounts/google")
def list_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items = client_registry_service.list_platform_accounts(platform=PLATFORM_GOOGLE_ADS)
    return {
        "items": items,
        "count": len(items),
        "last_import_at": client_registry_service.get_last_import_at(platform=PLATFORM_GOOGLE_ADS),
    }


@router.get("/accounts/{platform}")
def list_platform_accounts(platform: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    normalized_platform = _normalize_platform_or_422(platform)
    sync_enabled = _is_platform_sync_enabled(normalized_platform)
    items = client_registry_service.list_platform_accounts_for_mapping(platform=normalized_platform)
    _suppress_stale_recent_errors_after_success(items=items)
    if normalized_platform == PLATFORM_TIKTOK_ADS:
        _suppress_stale_tiktok_feature_flag_errors(items=items, sync_enabled=sync_enabled)
        _suppress_stale_tiktok_recent_errors_after_success(items=items)
    return {
        "platform": normalized_platform,
        "sync_enabled": sync_enabled,
        "items": items,
        "count": len(items),
        "last_import_at": client_registry_service.get_last_import_at(platform=normalized_platform),
    }


@router.post("/{client_id}/attach-account")
def attach_platform_account(
    client_id: int,
    payload: AttachPlatformAccountRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    updated = _attach_platform_account(
        client_id=client_id,
        platform=payload.platform,
        account_id=payload.account_id,
    )

    normalized_platform = _normalize_platform_or_422(payload.platform)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.attach_platform_account",
        resource=f"client:{client_id}",
        details={"platform": normalized_platform, "account_id": payload.account_id},
    )
    return {
        "status": "ok",
        "client_id": client_id,
        "platform": normalized_platform,
        "account_id": payload.account_id,
        "client": updated,
    }


@router.post("/{client_id}/detach-account")
def detach_platform_account(
    client_id: int,
    payload: DetachPlatformAccountRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    normalized_platform = _normalize_platform_or_422(payload.platform)
    deleted = client_registry_service.detach_platform_account_from_client(
        platform=normalized_platform,
        client_id=client_id,
        account_id=payload.account_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Platform account mapping not found")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.detach_platform_account",
        resource=f"client:{client_id}",
        details={"platform": normalized_platform, "account_id": payload.account_id},
    )
    return {"status": "ok", "client_id": client_id, "platform": normalized_platform, "account_id": payload.account_id}


@router.post("/{client_id}/attach-google-account")
def attach_google_account(client_id: int, payload: AttachGoogleAccountRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str | int | None]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    updated = _attach_platform_account(
        client_id=client_id,
        platform=PLATFORM_GOOGLE_ADS,
        account_id=payload.customer_id,
    )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.attach_google_account",
        resource=f"client:{client_id}",
        details={"customer_id": payload.customer_id},
    )
    return updated


@router.delete("/{client_id}/detach-google-account")
def detach_google_account(client_id: int, payload: DetachGoogleAccountRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    deleted = client_registry_service.detach_platform_account_from_client(
        platform=PLATFORM_GOOGLE_ADS,
        client_id=client_id,
        account_id=payload.customer_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Google account mapping not found")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.detach_google_account",
        resource=f"client:{client_id}",
        details={"customer_id": payload.customer_id},
    )
    return {"status": "ok", "client_id": client_id, "customer_id": payload.customer_id}


@router.get("/display/{display_id}")
def get_client_details(display_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    payload = client_registry_service.get_client_details_by_display_id(display_id=display_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return payload


@router.patch("/display/{display_id}")
def update_client_profile(
    display_id: int,
    payload: UpdateClientProfileRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    updated = client_registry_service.update_client_profile_by_display_id(
        display_id=display_id,
        name=payload.name,
        client_logo_url=payload.client_logo_url,
        client_type=payload.client_type,
        account_manager=payload.account_manager,
        currency=payload.currency,
        platform=payload.platform,
        account_id=payload.account_id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@router.post("/{client_id}/business-inputs/import", response_model=BusinessInputsImportResponse)
def import_client_business_inputs(
    client_id: int,
    payload: BusinessInputsImportRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    sanitized_rows: list[dict[str, object]] = []
    for raw in payload.rows:
        row = dict(raw)
        row["client_id"] = client_id
        sanitized_rows.append(row)

    result = client_business_inputs_import_service.import_client_business_inputs(
        sanitized_rows,
        default_client_id=client_id,
        default_period_grain=payload.period_grain,
        default_source=payload.source or "manual",
    )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.business_inputs.import",
        resource=f"client:{client_id}",
        details={
            "processed": int(result.get("processed", 0) or 0),
            "succeeded": int(result.get("succeeded", 0) or 0),
            "failed": int(result.get("failed", 0) or 0),
        },
    )
    return result




def _ensure_client_exists_or_404(*, client_id: int) -> None:
    details = client_registry_service.get_client_details(client_id=int(client_id))
    if details is None:
        raise HTTPException(status_code=404, detail="Client not found")


@router.get("/{client_id}/media-buying/config")
def get_media_buying_config(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    _ensure_client_exists_or_404(client_id=client_id)
    return media_buying_store.get_config(client_id=client_id)


@router.put("/{client_id}/media-buying/config")
def upsert_media_buying_config(
    client_id: int,
    payload: MediaBuyingConfigUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_buying_store.upsert_config(
            client_id=client_id,
            template_type=payload.template_type,
            display_currency=payload.display_currency,
            custom_label_1=payload.custom_label_1,
            custom_label_2=payload.custom_label_2,
            custom_label_3=payload.custom_label_3,
            custom_label_4=payload.custom_label_4,
            custom_label_5=payload.custom_label_5,
            custom_rate_label_1=payload.custom_rate_label_1,
            custom_rate_label_2=payload.custom_rate_label_2,
            custom_cost_label_1=payload.custom_cost_label_1,
            custom_cost_label_2=payload.custom_cost_label_2,
            visible_columns=payload.visible_columns,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{client_id}/media-buying/lead/daily-values")
def list_media_buying_lead_daily_values(
    client_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        items = media_buying_store.list_lead_daily_manual_values(client_id=client_id, date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"items": items, "count": len(items), "date_from": str(date_from), "date_to": str(date_to)}


@router.put("/{client_id}/media-buying/lead/daily-values")
def upsert_media_buying_lead_daily_value(
    client_id: int,
    payload: MediaBuyingLeadDailyValueUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_buying_store.upsert_lead_daily_manual_value(
            client_id=client_id,
            metric_date=payload.date,
            leads=payload.leads,
            phones=payload.phones,
            custom_value_1_count=payload.custom_value_1_count,
            custom_value_2_count=payload.custom_value_2_count,
            custom_value_3_amount_ron=payload.custom_value_3_amount_ron,
            custom_value_4_amount_ron=payload.custom_value_4_amount_ron,
            custom_value_5_amount_ron=payload.custom_value_5_amount_ron,
            sales_count=payload.sales_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc



@router.get("/{client_id}/media-buying/lead/table")
def get_media_buying_lead_table(
    client_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_buying_store.get_lead_table(client_id=client_id, date_from=date_from, date_to=date_to)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

@router.get("/{client_id}/accounts")
def list_client_accounts(
    client_id: int,
    platform: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    normalized_platform = _normalize_platform_or_422(platform) if platform is not None else None
    items = client_registry_service.list_client_accounts(client_id=client_id, platform=normalized_platform)
    return {"items": items, "count": len(items), "platform": normalized_platform}
