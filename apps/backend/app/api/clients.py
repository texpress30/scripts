from datetime import date
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, enforce_subaccount_action, get_current_user
from app.core.config import load_settings
from app.schemas.client import (
    AttachGoogleAccountRequest,
    AttachPlatformAccountRequest,
    BusinessInputsImportRequest,
    BusinessInputsImportResponse,
    ClientDataConfigResponse,
    CustomValueLabelsUpdateRequest,
    CustomValueLabelsResponse,
    ClientDataDailyInputUpsertRequest,
    ClientDataDailyInputPatchRequest,
    ClientDataDailyInputDeleteResponse,
    ClientDataDailyInputWriteResponse,
    ClientDataDailyCustomValueUpsertRequest,
    ClientDataDailyCustomValueWriteResponse,
    ClientDataCustomFieldCreateRequest,
    ClientDataCustomFieldUpdateRequest,
    ClientDataCustomFieldWriteResponse,
    ClientDataCustomFieldListResponse,
    ClientDataSaleEntryCreateRequest,
    ClientDataSaleEntryUpdateRequest,
    ClientDataSaleEntryWriteResponse,
    ClientDataTableResponse,
    CreateClientRequest,
    DetachGoogleAccountRequest,
    DetachPlatformAccountRequest,
    UpdateClientProfileRequest,
    SubaccountBusinessProfilePayload,
    SubaccountBusinessProfileResponse,
    MediaBuyingConfigUpdateRequest,
    MediaBuyingLeadDailyValueUpsertRequest,
    MediaTrackerWorksheetManualValuesUpsertRequest,
    MediaTrackerWorksheetEurRonRateUpsertRequest,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services import client_data_store
from app.services.client_registry import PlatformAccountAlreadyAttachedError, client_registry_service
from app.services.client_business_inputs_import_service import client_business_inputs_import_service
from app.services.client_data_csv_import_service import import_csv_rows, parse_csv_for_preview
from app.services.media_buying_store import media_buying_store
from app.services.storage_media_access import StorageMediaAccessError, storage_media_access_service
from app.services.media_tracker_worksheet import media_tracker_worksheet_service
from app.services.sync_constants import (
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PLATFORM_PINTEREST_ADS,
    PLATFORM_SNAPCHAT_ADS,
    PLATFORM_TIKTOK_ADS,
)
from app.services.subaccount_business_profile_store import subaccount_business_profile_store

router = APIRouter(prefix="/clients", tags=["clients"])

_SUPPORTED_PLATFORMS = {
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PLATFORM_TIKTOK_ADS,
    PLATFORM_PINTEREST_ADS,
    PLATFORM_SNAPCHAT_ADS,
    "reddit_ads",
}
_LEGACY_MANUAL_EDIT_MOVED_DETAIL = "Manual editing moved to the Data page for this client."


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
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")

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
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")

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
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
    items = client_registry_service.platform_account_summary()
    for item in items:
        if isinstance(item, dict):
            item["sync_enabled"] = _is_platform_sync_enabled(str(item.get("platform") or ""))
    return {"items": items}


@router.get("/accounts/google")
def list_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
    items = client_registry_service.list_platform_accounts(platform=PLATFORM_GOOGLE_ADS)
    return {
        "items": items,
        "count": len(items),
        "last_import_at": client_registry_service.get_last_import_at(platform=PLATFORM_GOOGLE_ADS),
    }


@router.get("/accounts/{platform}")
def list_platform_accounts(platform: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
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
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
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


def _resolve_client_from_subaccount_identifier_or_404(*, identifier: int) -> tuple[int, int, str]:
    direct_details = client_registry_service.get_client_details(client_id=int(identifier))
    if direct_details is not None:
        client_payload = direct_details.get("client", {}) if isinstance(direct_details, dict) else {}
        client_id = int(client_payload.get("id") or 0)
        display_id = int(client_payload.get("display_id") or 0)
        client_name = str(client_payload.get("name") or "").strip()
        if client_id > 0:
            return client_id, display_id, client_name

    details = client_registry_service.get_client_details_by_display_id(display_id=int(identifier))
    if details is None:
        raise HTTPException(status_code=404, detail="Client not found")
    client_payload = details.get("client", {}) if isinstance(details, dict) else {}
    client_id = int(client_payload.get("id") or 0)
    display_id = int(client_payload.get("display_id") or 0)
    client_name = str(client_payload.get("name") or "").strip()
    if client_id <= 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_id, display_id, client_name


def _resolve_logo_preview_url(*, client_id: int, profile: dict[str, object]) -> str:
    logo_media_id = str(profile.get("logo_media_id") or "").strip()
    legacy_logo_url = str(profile.get("logo_url") or "").strip()
    if logo_media_id == "":
        return legacy_logo_url
    try:
        access_payload = storage_media_access_service.build_access_url(
            client_id=int(client_id),
            media_id=logo_media_id,
            disposition="inline",
        )
        return str(access_payload.get("url") or "").strip() or legacy_logo_url
    except StorageMediaAccessError:
        return legacy_logo_url
    except RuntimeError:
        return legacy_logo_url
    except Exception:
        return legacy_logo_url


def _build_subaccount_business_profile_response(*, identifier: int, profile: dict[str, object]) -> SubaccountBusinessProfileResponse:
    client_id, display_id, client_name = _resolve_client_from_subaccount_identifier_or_404(identifier=identifier)
    logo_media_id = str(profile.get("logo_media_id") or "").strip() or None
    return SubaccountBusinessProfileResponse(
        client_id=client_id,
        display_id=display_id,
        client_name=client_name,
        general=dict(profile.get("general") or {}),
        business=dict(profile.get("business") or {}),
        address=dict(profile.get("address") or {}),
        representative=dict(profile.get("representative") or {}),
        logo_url=_resolve_logo_preview_url(client_id=client_id, profile=profile),
        logo_media_id=logo_media_id,
    )


@router.get("/{subaccount_id}/business-profile", response_model=SubaccountBusinessProfileResponse)
def get_subaccount_business_profile_by_subaccount_id(subaccount_id: int, user: AuthUser = Depends(get_current_user)) -> SubaccountBusinessProfileResponse:
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    client_id, _, _ = _resolve_client_from_subaccount_identifier_or_404(identifier=subaccount_id)
    profile = subaccount_business_profile_store.get_profile(client_id=client_id)
    return _build_subaccount_business_profile_response(identifier=subaccount_id, profile=profile)


@router.put("/{subaccount_id}/business-profile", response_model=SubaccountBusinessProfileResponse)
def upsert_subaccount_business_profile_by_subaccount_id(
    subaccount_id: int,
    payload: SubaccountBusinessProfilePayload,
    user: AuthUser = Depends(get_current_user),
) -> SubaccountBusinessProfileResponse:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    client_id, _, _ = _resolve_client_from_subaccount_identifier_or_404(identifier=subaccount_id)
    profile = subaccount_business_profile_store.upsert_profile(
        client_id=client_id,
        payload={
            "general": payload.general,
            "business": payload.business,
            "address": payload.address,
            "representative": payload.representative,
            "logo_url": payload.logo_url,
            "logo_media_id": payload.logo_media_id,
        },
    )
    return _build_subaccount_business_profile_response(identifier=subaccount_id, profile=profile)


@router.get("/display/{display_id}/business-profile", response_model=SubaccountBusinessProfileResponse)
def get_subaccount_business_profile(display_id: int, user: AuthUser = Depends(get_current_user)) -> SubaccountBusinessProfileResponse:
    return get_subaccount_business_profile_by_subaccount_id(subaccount_id=display_id, user=user)


@router.put("/display/{display_id}/business-profile", response_model=SubaccountBusinessProfileResponse)
def upsert_subaccount_business_profile(
    display_id: int,
    payload: SubaccountBusinessProfilePayload,
    user: AuthUser = Depends(get_current_user),
) -> SubaccountBusinessProfileResponse:
    return upsert_subaccount_business_profile_by_subaccount_id(subaccount_id=display_id, payload=payload, user=user)


@router.post("/{client_id}/business-inputs/import", response_model=BusinessInputsImportResponse)
def import_client_business_inputs(
    client_id: int,
    payload: BusinessInputsImportRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")

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


def _decimal_to_string(value: object) -> str:
    return str(value)


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _fallback_field_label(*, label: object, custom_field_id: object) -> str:
    normalized_label = str(label or "").strip()
    if normalized_label:
        return normalized_label
    return f"Custom Field {int(custom_field_id)}"


def _validate_canonical_source_or_422(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if not normalized:
        return "unknown"
    if not client_data_store.is_supported_source(normalized):
        supported = [str(item.get("key")) for item in client_data_store.list_supported_sources() if str(item.get("key") or "").strip()]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported source '{source}'. Allowed values: {supported}",
        )
    return normalized


_CANONICAL_DAILY_INPUT_DISALLOWED_FIELDS = {
    "notes",
    "sale_entries",
    "sale_brand",
    "sale_model",
    "sale_price_amount",
    "sale_actual_price_amount",
    "sale_notes",
    "sale_sort_order",
    "custom_value_5_amount",
}


def _reject_legacy_daily_input_fields_or_422(payload: ClientDataDailyInputUpsertRequest) -> None:
    blocked = sorted(_CANONICAL_DAILY_INPUT_DISALLOWED_FIELDS.intersection(payload.model_fields_set))
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Canonical daily-input save accepts only metric_date, source, leads, phones, "
                "custom_value_1_count, custom_value_2_count, custom_value_3_amount, custom_value_4_amount, sales_count and dynamic_custom_values. "
                f"Unsupported fields: {blocked}"
            ),
        )


def _map_daily_input_write_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "client_id": int(row["client_id"]),
        "metric_date": str(row["metric_date"]),
        "source": str(row["source"]),
        "leads": int(row["leads"]),
        "phones": int(row["phones"]),
        "custom_value_1_count": int(row["custom_value_1_count"]),
        "custom_value_2_count": int(row["custom_value_2_count"]),
        "custom_value_3_amount": _decimal_to_string(row["custom_value_3_amount"]),
        "custom_value_4_amount": _decimal_to_string(row["custom_value_4_amount"]),
        "custom_value_5_amount": _decimal_to_string(row["custom_value_5_amount"]),
        "sales_count": int(row["sales_count"]),
        "notes": row.get("notes"),
    }


def _map_sale_entry_write_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "daily_input_id": int(row["daily_input_id"]),
        "brand": row.get("brand"),
        "model": row.get("model"),
        "sale_price_amount": _decimal_to_string(row["sale_price_amount"]),
        "actual_price_amount": _decimal_to_string(row["actual_price_amount"]),
        "notes": row.get("notes"),
        "sort_order": int(row["sort_order"]),
        "gross_profit_amount": _decimal_to_string(row["gross_profit_amount"]),
    }


def _map_custom_field_write_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "client_id": int(row["client_id"]),
        "field_key": str(row["field_key"]),
        "label": str(row["label"]),
        "value_kind": str(row["value_kind"]),
        "sort_order": int(row["sort_order"]),
        "is_active": bool(row["is_active"]),
        "archived_at": row.get("archived_at"),
    }


def _map_daily_custom_value_write_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "daily_input_id": int(row["daily_input_id"]),
        "metric_date": str(row["metric_date"]),
        "source": str(row["source"]),
        "custom_field_id": int(row["custom_field_id"]),
        "field_key": str(row["field_key"]),
        "label": str(row["label"]),
        "value_kind": str(row["value_kind"]),
        "sort_order": int(row["sort_order"]),
        "is_active": bool(row["is_active"]),
        "numeric_value": _decimal_to_string(row["numeric_value"]),
    }


def _build_client_data_derived_fields(*, media_buying_config: dict[str, object]) -> list[dict[str, str]]:
    return [
        {"key": "custom_value_5_amount", "label": str(media_buying_config.get("custom_label_5") or "Custom Value 5"), "value_kind": "amount"},
        {"key": "revenue_amount", "label": "Venit", "value_kind": "amount"},
        {"key": "cogs_amount", "label": "COGS", "value_kind": "amount"},
        {"key": "gross_profit_amount", "label": "Profit Brut", "value_kind": "amount"},
    ]


@router.get("/{client_id}/data/config", response_model=ClientDataConfigResponse)
def get_client_data_config(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    client_details = client_registry_service.get_client_details(client_id=int(client_id)) or {}
    client_payload = client_details.get("client") if isinstance(client_details, dict) else {}
    client_currency = str((client_payload or {}).get("currency") or "").strip().upper() or None
    media_buying_config = media_buying_store.get_config(client_id=client_id)
    display_currency = client_currency or (str(media_buying_config.get("display_currency") or "").strip().upper() or None)
    fixed_fields = [
        {"key": "leads", "label": "Lead-uri", "editable": True, "read_only": False},
        {"key": "phones", "label": "Telefoane", "editable": True, "read_only": False},
        {"key": "custom_value_1_count", "label": str(media_buying_config.get("custom_label_1") or "Custom Value 1"), "editable": True, "read_only": False},
        {"key": "custom_value_2_count", "label": str(media_buying_config.get("custom_label_2") or "Custom Value 2"), "editable": True, "read_only": False},
        {"key": "custom_value_3_amount", "label": str(media_buying_config.get("custom_label_3") or "Custom Value 3"), "editable": True, "read_only": False},
        {"key": "custom_value_4_amount", "label": str(media_buying_config.get("custom_label_4") or "Custom Value 4"), "editable": True, "read_only": False},
        {"key": "sales_count", "label": "Vânzări", "editable": True, "read_only": False},
    ]
    derived_fields = _build_client_data_derived_fields(media_buying_config=media_buying_config)

    custom_fields = client_data_store.list_custom_fields(client_id=client_id, include_inactive=True)
    mapped_custom_fields: list[dict[str, object]] = []
    for field in custom_fields:
        mapped_custom_fields.append(
            {
                "id": int(field["id"]),
                "field_key": str(field["field_key"]),
                "label": _fallback_field_label(label=field.get("label"), custom_field_id=field["id"]),
                "value_kind": str(field["value_kind"]),
                "sort_order": int(field["sort_order"]),
                "is_active": bool(field["is_active"]),
            }
        )
    dynamic_custom_fields = [item for item in mapped_custom_fields if bool(item.get("is_active"))]
    custom_value_labels = _build_custom_value_labels_response(media_buying_config)
    return {
        "client_id": client_id,
        "currency_code": display_currency,
        "display_currency": display_currency,
        "fixed_fields": fixed_fields,
        "sources": client_data_store.list_supported_sources(),
        "dynamic_custom_fields": dynamic_custom_fields,
        "custom_fields": mapped_custom_fields,
        "derived_fields": derived_fields,
        "custom_value_labels": custom_value_labels,
    }


@router.get("/{client_id}/data/custom-value-labels", response_model=CustomValueLabelsResponse)
def get_custom_value_labels(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    config = media_buying_store.get_config(client_id=client_id)
    return _build_custom_value_labels_response(config)


@router.patch("/{client_id}/data/custom-value-labels", response_model=CustomValueLabelsResponse)
def update_custom_value_labels(
    client_id: int,
    payload: CustomValueLabelsUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    label_1 = payload.custom_label_1
    label_2 = payload.custom_label_2
    cost_label_1 = f"Cost {label_1}" if label_1 and label_1 != "Custom Value 1" else None
    cost_label_2 = f"Cost {label_2}" if label_2 and label_2 != "Custom Value 2" else None
    updated = media_buying_store.upsert_config(
        client_id=client_id,
        custom_label_1=payload.custom_label_1,
        custom_label_2=payload.custom_label_2,
        custom_label_3=payload.custom_label_3,
        custom_label_4=payload.custom_label_4,
        custom_label_5=payload.custom_label_5,
        custom_rate_label_1=payload.custom_rate_label_1,
        custom_rate_label_2=payload.custom_rate_label_2,
        custom_cost_label_1=cost_label_1,
        custom_cost_label_2=cost_label_2,
    )
    return _build_custom_value_labels_response(updated)


def _build_custom_value_labels_response(config: dict) -> dict[str, object]:
    label_1 = str(config.get("custom_label_1") or "Custom Value 1")
    label_2 = str(config.get("custom_label_2") or "Custom Value 2")
    return {
        "custom_label_1": label_1,
        "custom_label_2": label_2,
        "custom_label_3": str(config.get("custom_label_3") or "Custom Value 3"),
        "custom_label_4": str(config.get("custom_label_4") or "Custom Value 4"),
        "custom_label_5": str(config.get("custom_label_5") or "Custom Value 5"),
        "custom_rate_label_1": str(config.get("custom_rate_label_1") or "Custom Value Rate 1"),
        "custom_rate_label_2": str(config.get("custom_rate_label_2") or "Custom Value Rate 2"),
        "custom_cost_label_1": str(config.get("custom_cost_label_1") or f"Cost {label_1}"),
        "custom_cost_label_2": str(config.get("custom_cost_label_2") or f"Cost {label_2}"),
    }


@router.get("/{client_id}/data/table", response_model=ClientDataTableResponse)
def get_client_data_table(
    client_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        daily_inputs = client_data_store.list_daily_inputs(client_id=client_id, date_from=date_from, date_to=date_to)
        daily_custom_values = client_data_store.list_daily_custom_values(client_id=client_id, date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    custom_values_by_daily_input_id: dict[int, list[dict[str, object]]] = {}
    for row in daily_custom_values:
        daily_input_id = int(row["daily_input_id"])
        custom_values_by_daily_input_id.setdefault(daily_input_id, []).append(
            {
                "custom_field_id": int(row["custom_field_id"]),
                "field_key": str(row["field_key"]),
                "label": _fallback_field_label(label=row.get("label"), custom_field_id=row["custom_field_id"]),
                "value_kind": str(row["value_kind"]),
                "sort_order": int(row["sort_order"]),
                "is_active": bool(row["is_active"]),
                "numeric_value": _decimal_to_string(row["numeric_value"]),
            }
        )

    rows: list[dict[str, object]] = []
    sale_entries_by_daily_input_id = client_data_store.list_sale_entries_for_daily_input_ids(
        daily_input_ids=[int(item["id"]) for item in daily_inputs]
    )
    for daily_input in daily_inputs:
        daily_input_id = int(daily_input["id"])
        sale_entries = sale_entries_by_daily_input_id.get(daily_input_id, [])

        custom_value_3_amount = _to_decimal(daily_input["custom_value_3_amount"])
        custom_value_4_amount = _to_decimal(daily_input["custom_value_4_amount"])
        custom_value_5_amount = custom_value_4_amount - custom_value_3_amount

        source_key = str(daily_input.get("source") or "").strip().lower() or "unknown"
        source_label = client_data_store.get_source_label(source_key) or "Unknown"
        rows.append(
            {
                "daily_input_id": daily_input_id,
                "metric_date": str(daily_input["metric_date"]),
                "source": source_key,
                "source_label": source_label,
                "leads": int(daily_input["leads"]),
                "phones": int(daily_input["phones"]),
                "custom_value_1_count": int(daily_input["custom_value_1_count"]),
                "custom_value_2_count": int(daily_input["custom_value_2_count"]),
                "custom_value_3_amount": _decimal_to_string(custom_value_3_amount),
                "custom_value_4_amount": _decimal_to_string(custom_value_4_amount),
                "custom_value_5_amount": _decimal_to_string(custom_value_5_amount),
                "notes": daily_input.get("notes"),
                "sales_count": int(daily_input["sales_count"]),
                "revenue_amount": _decimal_to_string(client_data_store.compute_revenue(sale_entries)),
                "cogs_amount": _decimal_to_string(client_data_store.compute_cogs(sale_entries)),
                "gross_profit_amount": _decimal_to_string(client_data_store.compute_gross_profit(sale_entries)),
                "sale_entries": [_map_sale_entry_write_payload(entry) for entry in sale_entries],
                "dynamic_custom_values": sorted(
                    custom_values_by_daily_input_id.get(daily_input_id, []),
                    key=lambda item: (int(item["sort_order"]), int(item["custom_field_id"])),
                ),
                "custom_values": sorted(
                    custom_values_by_daily_input_id.get(daily_input_id, []),
                    key=lambda item: (int(item["sort_order"]), int(item["custom_field_id"])),
                ),
            }
        )

    return {
        "client_id": int(client_id),
        "date_from": str(date_from),
        "date_to": str(date_to),
        "count": len(rows),
        "rows": rows,
    }


@router.put("/{client_id}/data/daily-input", response_model=ClientDataDailyInputWriteResponse)
def upsert_client_data_daily_input(
    client_id: int,
    payload: ClientDataDailyInputUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    _reject_legacy_daily_input_fields_or_422(payload)
    source_key = _validate_canonical_source_or_422(payload.source)

    numeric_updates: dict[str, object] = {}
    for key in (
        "leads",
        "phones",
        "custom_value_1_count",
        "custom_value_2_count",
        "custom_value_3_amount",
        "custom_value_4_amount",
        "sales_count",
    ):
        value = getattr(payload, key)
        if value is not None:
            numeric_updates[key] = value

    dynamic_values_provided = "dynamic_custom_values" in payload.model_fields_set and payload.dynamic_custom_values is not None
    dynamic_values_payload: list[dict[str, object]] = []
    if dynamic_values_provided:
        dynamic_values_payload = [
            {"custom_field_id": int(item.custom_field_id), "numeric_value": item.numeric_value}
            for item in payload.dynamic_custom_values or []
        ]
    if not numeric_updates and not dynamic_values_provided:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one canonical field is required: numeric daily values and/or dynamic_custom_values",
        )

    try:
        latest_row = client_data_store.get_or_create_daily_input(
            client_id=client_id,
            metric_date=payload.metric_date,
            source=source_key,
        )
        if numeric_updates:
            latest_row = client_data_store.upsert_daily_input(
                client_id=client_id,
                metric_date=payload.metric_date,
                source=source_key,
                recompute_custom_value_5=True,
                **numeric_updates,
            )
        if dynamic_values_provided:
            client_data_store.replace_daily_custom_values_for_daily_input(
                client_id=client_id,
                daily_input_id=int(latest_row["id"]),
                dynamic_custom_values=dynamic_values_payload,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if latest_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to write daily input")
    return _map_daily_input_write_payload(latest_row)


@router.post("/{client_id}/data/daily-inputs", response_model=ClientDataDailyInputWriteResponse)
def create_client_data_daily_input(
    client_id: int,
    payload: ClientDataDailyInputUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    _reject_legacy_daily_input_fields_or_422(payload)
    source_key = _validate_canonical_source_or_422(payload.source)

    try:
        created = client_data_store.create_daily_input(
            client_id=client_id,
            metric_date=payload.metric_date,
            source=source_key,
            leads=int(payload.leads or 0),
            phones=int(payload.phones or 0),
            custom_value_1_count=int(payload.custom_value_1_count or 0),
            custom_value_2_count=int(payload.custom_value_2_count or 0),
            custom_value_3_amount=payload.custom_value_3_amount or 0,
            custom_value_4_amount=payload.custom_value_4_amount or 0,
            sales_count=int(payload.sales_count or 0),
        )
        if "dynamic_custom_values" in payload.model_fields_set and payload.dynamic_custom_values is not None:
            dynamic_values_payload = [
                {"custom_field_id": int(item.custom_field_id), "numeric_value": item.numeric_value}
                for item in payload.dynamic_custom_values or []
            ]
            client_data_store.replace_daily_custom_values_for_daily_input(
                client_id=client_id,
                daily_input_id=int(created["id"]),
                dynamic_custom_values=dynamic_values_payload,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_daily_input_write_payload(created)


@router.patch("/{client_id}/data/daily-inputs/{daily_input_id}", response_model=ClientDataDailyInputWriteResponse)
def patch_client_data_daily_input(
    client_id: int,
    daily_input_id: int,
    payload: ClientDataDailyInputPatchRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    allowed_fields = {
        "leads",
        "phones",
        "custom_value_1_count",
        "custom_value_2_count",
        "custom_value_3_amount",
        "custom_value_4_amount",
        "sales_count",
    }
    provided_fields = set(payload.model_fields_set).intersection(allowed_fields)
    dynamic_values_provided = "dynamic_custom_values" in payload.model_fields_set and payload.dynamic_custom_values is not None
    if not provided_fields and not dynamic_values_provided:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one canonical field is required")

    try:
        client_data_store.validate_daily_input_belongs_to_client(daily_input_id=daily_input_id, client_id=client_id)
        kwargs = {field: getattr(payload, field) for field in provided_fields}
        updated = None
        if kwargs:
            updated = client_data_store.update_daily_input_by_id(daily_input_id=daily_input_id, **kwargs)
        else:
            updated = client_data_store.validate_daily_input_belongs_to_client(daily_input_id=daily_input_id, client_id=client_id)

        if dynamic_values_provided:
            dynamic_values_payload = [
                {"custom_field_id": int(item.custom_field_id), "numeric_value": item.numeric_value}
                for item in payload.dynamic_custom_values or []
            ]
            client_data_store.replace_daily_custom_values_for_daily_input(
                client_id=client_id,
                daily_input_id=daily_input_id,
                dynamic_custom_values=dynamic_values_payload,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_daily_input_write_payload(updated)


@router.delete("/{client_id}/data/daily-inputs/{daily_input_id}", response_model=ClientDataDailyInputDeleteResponse)
def delete_client_data_daily_input(
    client_id: int,
    daily_input_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_daily_input_belongs_to_client(daily_input_id=daily_input_id, client_id=client_id)
        deleted = client_data_store.delete_daily_input_with_dependencies(daily_input_id=daily_input_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_daily_input_write_payload(deleted)


@router.post("/{client_id}/data/sale-entries", response_model=ClientDataSaleEntryWriteResponse)
def create_client_data_sale_entry(
    client_id: int,
    payload: ClientDataSaleEntryCreateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_daily_input_belongs_to_client(daily_input_id=payload.daily_input_id, client_id=client_id)
        created = client_data_store.create_sale_entry(
            daily_input_id=payload.daily_input_id,
            sale_price_amount=payload.sale_price_amount,
            actual_price_amount=payload.actual_price_amount,
            brand=payload.brand,
            model=payload.model,
            notes=payload.notes,
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_sale_entry_write_payload(created)


@router.patch("/{client_id}/data/sale-entries/{sale_entry_id}", response_model=ClientDataSaleEntryWriteResponse)
def update_client_data_sale_entry(
    client_id: int,
    sale_entry_id: int,
    payload: ClientDataSaleEntryUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    allowed_fields = {"sale_price_amount", "actual_price_amount", "brand", "model", "notes", "sort_order"}
    provided_fields = set(payload.model_fields_set).intersection(allowed_fields)
    if not provided_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one sale entry field is required for update",
        )

    kwargs = {field: getattr(payload, field) for field in provided_fields}
    try:
        client_data_store.validate_sale_entry_belongs_to_client(sale_entry_id=sale_entry_id, client_id=client_id)
        updated = client_data_store.update_sale_entry(sale_entry_id=sale_entry_id, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_sale_entry_write_payload(updated)


@router.delete("/{client_id}/data/sale-entries/{sale_entry_id}", response_model=ClientDataSaleEntryWriteResponse)
def delete_client_data_sale_entry(
    client_id: int,
    sale_entry_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_sale_entry_belongs_to_client(sale_entry_id=sale_entry_id, client_id=client_id)
        deleted = client_data_store.delete_sale_entry(sale_entry_id=sale_entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_sale_entry_write_payload(deleted)


@router.post("/{client_id}/data/custom-fields", response_model=ClientDataCustomFieldWriteResponse)
def create_client_data_custom_field(
    client_id: int,
    payload: ClientDataCustomFieldCreateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        created = client_data_store.create_custom_field(
            client_id=client_id,
            label=payload.label,
            value_kind=payload.value_kind,
            field_key=payload.field_key,
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_custom_field_write_payload(created)


@router.get("/{client_id}/data/custom-fields", response_model=ClientDataCustomFieldListResponse)
def list_client_data_custom_fields(
    client_id: int,
    include_inactive: bool = Query(False),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    items = client_data_store.list_custom_fields(client_id=client_id, include_inactive=include_inactive)
    return {"items": [_map_custom_field_write_payload(item) for item in items]}


@router.patch("/{client_id}/data/custom-fields/{custom_field_id}", response_model=ClientDataCustomFieldWriteResponse)
def update_client_data_custom_field(
    client_id: int,
    custom_field_id: int,
    payload: ClientDataCustomFieldUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    allowed_fields = {"label", "value_kind", "sort_order"}
    provided_fields = set(payload.model_fields_set).intersection(allowed_fields)
    if not provided_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one custom field value is required for update",
        )

    kwargs = {field: getattr(payload, field) for field in provided_fields}
    try:
        client_data_store.validate_custom_field_belongs_to_client(custom_field_id=custom_field_id, client_id=client_id)
        updated = client_data_store.update_custom_field(custom_field_id=custom_field_id, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_custom_field_write_payload(updated)


@router.delete("/{client_id}/data/custom-fields/{custom_field_id}", response_model=ClientDataCustomFieldWriteResponse)
def archive_client_data_custom_field(
    client_id: int,
    custom_field_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_custom_field_belongs_to_client(custom_field_id=custom_field_id, client_id=client_id)
        archived = client_data_store.archive_custom_field(custom_field_id=custom_field_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_custom_field_write_payload(archived)


@router.post("/{client_id}/data/custom-fields/{custom_field_id}/archive", response_model=ClientDataCustomFieldWriteResponse)
def archive_client_data_custom_field_post(
    client_id: int,
    custom_field_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    return archive_client_data_custom_field(client_id=client_id, custom_field_id=custom_field_id, user=user)


@router.put(
    "/{client_id}/data/daily-inputs/{daily_input_id}/custom-values/{custom_field_id}",
    response_model=ClientDataDailyCustomValueWriteResponse,
)
def upsert_client_data_daily_custom_value(
    client_id: int,
    daily_input_id: int,
    custom_field_id: int,
    payload: ClientDataDailyCustomValueUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_daily_input_belongs_to_client(daily_input_id=daily_input_id, client_id=client_id)
        custom_field = client_data_store.validate_custom_field_belongs_to_client(custom_field_id=custom_field_id, client_id=client_id)
        if not bool(custom_field.get("is_active")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot write daily custom value for archived custom field",
            )
        upserted = client_data_store.upsert_daily_custom_value(
            daily_input_id=daily_input_id,
            custom_field_id=custom_field_id,
            numeric_value=payload.numeric_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_daily_custom_value_write_payload(upserted)


@router.delete(
    "/{client_id}/data/daily-inputs/{daily_input_id}/custom-values/{custom_field_id}",
    response_model=ClientDataDailyCustomValueWriteResponse,
)
def delete_client_data_daily_custom_value(
    client_id: int,
    daily_input_id: int,
    custom_field_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    try:
        client_data_store.validate_daily_input_belongs_to_client(daily_input_id=daily_input_id, client_id=client_id)
        client_data_store.validate_custom_field_belongs_to_client(custom_field_id=custom_field_id, client_id=client_id)
        deleted = client_data_store.delete_daily_custom_value(daily_input_id=daily_input_id, custom_field_id=custom_field_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _map_daily_custom_value_write_payload(deleted)


@router.get("/{client_id}/media-buying/config")
def get_media_buying_config(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    return media_buying_store.get_config(client_id=client_id)


@router.put("/{client_id}/media-buying/config")
def upsert_media_buying_config(
    client_id: int,
    payload: MediaBuyingConfigUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_LEGACY_MANUAL_EDIT_MOVED_DETAIL)


@router.get("/{client_id}/media-buying/lead/daily-values")
def list_media_buying_lead_daily_values(
    client_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
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
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_LEGACY_MANUAL_EDIT_MOVED_DETAIL)



@router.get("/{client_id}/media-buying/lead/table")
def get_media_buying_lead_table(
    client_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_days: bool = Query(default=True),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_buying_store.get_lead_table(client_id=client_id, date_from=date_from, date_to=date_to, include_days=bool(include_days))
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

@router.get("/{client_id}/media-buying/lead/month-days")
def get_media_buying_lead_month_days(
    client_id: int,
    month_start: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_buying_store.get_lead_month_days(client_id=client_id, month_start=month_start)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{client_id}/media-tracker/worksheet-foundation")
def get_media_tracker_weekly_worksheet_foundation(
    client_id: int,
    granularity: str = Query(...),
    anchor_date: date = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity=str(granularity).strip().lower(),
            anchor_date=anchor_date,
            client_id=client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{client_id}/media-tracker/overview-charts")
def get_media_tracker_overview_charts(
    client_id: int,
    granularity: str = Query(...),
    anchor_date: date = Query(...),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_tracker_worksheet_service.build_overview_charts_payload(
            granularity=str(granularity).strip().lower(),
            anchor_date=anchor_date,
            client_id=client_id,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/{client_id}/media-tracker/worksheet/manual-values")
def upsert_media_tracker_weekly_manual_values(
    client_id: int,
    payload: MediaTrackerWorksheetManualValuesUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_LEGACY_MANUAL_EDIT_MOVED_DETAIL)


@router.put("/{client_id}/media-tracker/worksheet/eur-ron-rate")
def upsert_media_tracker_scope_eur_ron_rate(
    client_id: int,
    payload: MediaTrackerWorksheetEurRonRateUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)
    try:
        return media_tracker_worksheet_service.upsert_scope_eur_ron_rate(
            client_id=client_id,
            granularity=str(payload.granularity).strip().lower(),
            anchor_date=payload.anchor_date,
            value=payload.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{client_id}/accounts")
def list_client_accounts(
    client_id: int,
    platform: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")
    normalized_platform = _normalize_platform_or_422(platform) if platform is not None else None
    items = client_registry_service.list_client_accounts(client_id=client_id, platform=normalized_platform)
    return {"items": items, "count": len(items), "platform": normalized_platform}


@router.post("/{client_id}/data/import-preview")
async def import_preview_client_data(
    client_id: int,
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    """Parse and validate a CSV file for data import preview. Does not write to DB."""
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    if file.content_type and file.content_type not in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
        "text/plain",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tip de fișier neacceptat: {file.content_type}. Încărcați un fișier CSV.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișierul este gol.")

    try:
        result = parse_csv_for_preview(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        print(f"[IMPORT-PREVIEW] Unexpected error for sub_id={client_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eroare internă la parsarea CSV-ului: {exc}",
        ) from exc

    print(
        f"[IMPORT-PREVIEW] sub_id={client_id}, rows={result['total']}, "
        f"valid={result['valid']}, errors={result['errors']}"
    )

    return result


@router.post("/{client_id}/data/import-confirm")
def confirm_import_client_data(
    client_id: int,
    payload: dict,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    """Import confirmed CSV rows into the database with transactional upsert."""
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_clients")
    _ensure_client_exists_or_404(client_id=client_id)

    rows = payload.get("rows")
    if not rows or not isinstance(rows, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lipsesc rândurile de importat.")

    try:
        result = import_csv_rows(client_id=client_id, rows=rows)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    print(
        f"[IMPORT-CONFIRM] sub_id={client_id}, inserted={result['inserted']}, "
        f"updated={result['updated']}, errors={len(result['errors'])}"
    )

    return result
