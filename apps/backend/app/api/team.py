from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, enforce_subaccount_action, get_current_user
from app.core.config import load_settings
from app.schemas.team import (
    CreateSubaccountTeamMemberRequest,
    CreateTeamMemberRequest,
    SubaccountTeamMemberListResponse,
    SubaccountTeamMemberResponse,
    TeamMemberInviteResponse,
    TeamMemberListResponse,
    TeamMemberResponse,
    TeamModuleCatalogResponse,
    TeamGrantableModulesResponse,
    TeamSubaccountMyAccessResponse,
    TeamSubaccountOptionItem,
    TeamSubaccountOptionsResponse,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.auth_email_tokens import auth_email_tokens_service
from app.services.client_registry import client_registry_service
from app.services.mailgun_service import MailgunIntegrationError, mailgun_service
from app.services.team_members import team_members_service

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

router = APIRouter(prefix="/team", tags=["team"])


def _is_db_unavailable_error(error: Exception) -> bool:
    if psycopg is not None and isinstance(error, psycopg.OperationalError):
        return True
    name = error.__class__.__name__.lower()
    text = str(error).lower()
    return "operationalerror" in name or "connection refused" in text or "connection failed" in text


def _normalize_module_keys(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        key = str(item or "").strip().lower()
        if key and key not in out:
            out.append(key)
    return out


def _normalize_member_item(raw: dict[str, object]) -> dict[str, object] | None:
    try:
        member_id = int(raw.get("id"))
    except Exception:  # noqa: BLE001
        return None

    membership_id_raw = raw.get("membership_id")
    user_id_raw = raw.get("user_id")

    membership_id: int | None
    user_id: int | None
    try:
        membership_id = int(membership_id_raw) if membership_id_raw is not None else None
    except Exception:  # noqa: BLE001
        membership_id = None
    try:
        user_id = int(user_id_raw) if user_id_raw is not None else None
    except Exception:  # noqa: BLE001
        user_id = None

    return {
        "id": member_id,
        "membership_id": membership_id,
        "user_id": user_id,
        "first_name": str(raw.get("first_name") or ""),
        "last_name": str(raw.get("last_name") or ""),
        "email": str(raw.get("email") or ""),
        "phone": str(raw.get("phone") or ""),
        "extension": str(raw.get("extension") or ""),
        "user_type": str(raw.get("user_type") or "agency"),
        "user_role": str(raw.get("user_role") or "member"),
        "location": str(raw.get("location") or "România"),
        "subaccount": str(raw.get("subaccount") or "Toate"),
        "module_keys": _normalize_module_keys(raw.get("module_keys")),
    }


def _normalize_module_catalog(items: list[dict[str, object]], *, requested_scope: str) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for idx, item in enumerate(items, start=1):
        key = str(item.get("key") or "").strip().lower()
        if key == "" or key in seen:
            continue
        seen.add(key)
        label = str(item.get("label") or "").strip() or key.replace("_", " ").title()
        try:
            order = int(item.get("order"))
        except Exception:  # noqa: BLE001
            order = idx
        scope = str(item.get("scope") or requested_scope).strip().lower() or requested_scope
        normalized.append({"key": key, "label": label, "order": order, "scope": scope})
    normalized.sort(key=lambda row: (int(row["order"]), str(row["label"]).lower()))
    return normalized


@router.get("/members", response_model=TeamMemberListResponse)
def list_team_members(
    search: str = Query(default=""),
    user_type: str = Query(default=""),
    user_role: str = Query(default=""),
    subaccount: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> TeamMemberListResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    try:
        raw_items, total = team_members_service.list_members(
            search=search,
            user_type=user_type,
            user_role=user_role,
            subaccount=subaccount,
            page=page,
            page_size=page_size,
        )
        items = [item for raw in raw_items if isinstance(raw, dict) for item in [_normalize_member_item(raw)] if item is not None]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if _is_db_unavailable_error(exc):
            return TeamMemberListResponse(items=[], total=0, page=page, page_size=page_size)
        raise
    return TeamMemberListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/members", response_model=TeamMemberResponse)
def create_team_member(payload: CreateTeamMemberRequest, user: AuthUser = Depends(get_current_user)) -> TeamMemberResponse:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    try:
        item = team_members_service.create_member(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            extension=payload.extension,
            user_type=payload.user_type,
            user_role=payload.user_role,
            location=payload.location,
            subaccount=payload.subaccount,
            password=payload.password,
            module_keys=payload.module_keys,
            actor_user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Nu am putut adăuga utilizatorul: {exc}") from exc

    return TeamMemberResponse(item=item)


@router.post("/members/{membership_id}/invite", response_model=TeamMemberInviteResponse)
def invite_team_member(membership_id: int, user: AuthUser = Depends(get_current_user)) -> TeamMemberInviteResponse:
    membership = team_members_service.get_membership_with_user(membership_id=membership_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership inexistent")

    scope_type = str(membership.get("scope_type") or "")
    subaccount_id = membership.get("subaccount_id")

    if scope_type == "agency":
        enforce_action_scope(user=user, action="team:invite", scope="agency")
    elif scope_type == "subaccount":
        if subaccount_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership inconsistent")
        enforce_subaccount_action(user=user, action="team:invite", subaccount_id=int(subaccount_id))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership inconsistent")

    email = str(membership.get("email") or "").strip().lower()
    if email == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utilizatorul nu are email valid")

    if not bool(membership.get("is_active", False)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utilizatorul este inactiv")

    try:
        mailgun_service.assert_available()
    except MailgunIntegrationError as exc:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "mailgun_unavailable", "status_code": exc.status_code},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan") from exc

    settings = load_settings()
    frontend_base_url = str(settings.frontend_base_url or "").strip()
    if frontend_base_url == "":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")

    invite_ttl_minutes = max(1, int(getattr(settings, "auth_reset_token_ttl_minutes", 60)))
    raw_token, _ = auth_email_tokens_service.create_user_invite_token_for_existing_user(
        user_id=int(membership["user_id"]),
        email=email,
        expires_in_minutes=invite_ttl_minutes,
    )

    invite_link = f"{frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
    subject = "Invitație în platformă"
    text = (
        "Ai fost invitat în platformă.\n\n"
        f"Setează parola contului tău folosind acest link (expiră în {invite_ttl_minutes} minute):\n"
        f"{invite_link}\n\n"
        "Dacă nu te așteptai la acest email, îl poți ignora."
    )

    try:
        mailgun_service.send_email(to_email=email, subject=subject, text=text)
    except (MailgunIntegrationError, ValueError):
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "mail_send_failed"},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="team.invite.sent",
        resource=f"team:membership:{membership_id}",
        details={"membership_id": membership_id, "scope_type": scope_type},
    )
    return TeamMemberInviteResponse(message="Invitația a fost trimisă")


@router.get("/module-catalog", response_model=TeamModuleCatalogResponse)
def get_team_module_catalog(
    scope: str = Query(default="subaccount"),
    user: AuthUser = Depends(get_current_user),
) -> TeamModuleCatalogResponse:
    try:
        raw_items = team_members_service.list_module_catalog(scope=scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if _is_db_unavailable_error(exc):
            return TeamModuleCatalogResponse(items=[])
        raise
    items = _normalize_module_catalog([item for item in raw_items if isinstance(item, dict)], requested_scope=scope)
    return TeamModuleCatalogResponse(items=items)


@router.get("/subaccount-options", response_model=TeamSubaccountOptionsResponse)
def list_subaccount_options(user: AuthUser = Depends(get_current_user)) -> TeamSubaccountOptionsResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items: list[TeamSubaccountOptionItem] = []
    try:
        rows = client_registry_service.list_clients()
    except Exception as exc:  # noqa: BLE001
        if _is_db_unavailable_error(exc):
            return TeamSubaccountOptionsResponse(items=[])
        raise

    for row in rows:
        try:
            client_id = int(row.get("id"))
        except Exception:  # noqa: BLE001
            continue

        name = str(row.get("name") or "").strip() or f"Sub-account {client_id}"

        display_id_raw = str(row.get("display_id") or "").strip()
        if display_id_raw == "":
            label = name
        else:
            label = f"#{display_id_raw} — {name}"

        if name == "":
            continue
        items.append(TeamSubaccountOptionItem(id=client_id, name=name, label=label))
    return TeamSubaccountOptionsResponse(items=items)


@router.get("/subaccounts/{subaccount_id}/grantable-modules", response_model=TeamGrantableModulesResponse)
def get_subaccount_grantable_modules(
    subaccount_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamGrantableModulesResponse:
    enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=subaccount_id)

    raw_items = team_members_service.list_module_catalog(scope="subaccount")
    catalog = _normalize_module_catalog([item for item in raw_items if isinstance(item, dict)], requested_scope="subaccount")
    grantable_keys = team_members_service.get_grantable_module_keys_for_actor(actor_user=user, subaccount_id=subaccount_id)

    items = [
        {
            "key": str(item.get("key") or ""),
            "label": str(item.get("label") or ""),
            "order": int(item.get("order") or 0),
            "grantable": str(item.get("key") or "") in grantable_keys,
        }
        for item in catalog
    ]
    return TeamGrantableModulesResponse(items=items)


@router.get("/subaccounts/{subaccount_id}/my-access", response_model=TeamSubaccountMyAccessResponse)
def get_subaccount_my_access(
    subaccount_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamSubaccountMyAccessResponse:
    enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=subaccount_id)
    try:
        payload = team_members_service.get_subaccount_my_access(actor_user=user, subaccount_id=subaccount_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TeamSubaccountMyAccessResponse(
        subaccount_id=int(payload.get("subaccount_id") or subaccount_id),
        role=str(payload.get("role") or user.role),
        module_keys=_normalize_module_keys(payload.get("module_keys")),
        source_scope=str(payload.get("source_scope") or "subaccount"),
        access_scope=str(payload.get("access_scope") or (user.access_scope or "subaccount")),
        unrestricted_modules=bool(payload.get("unrestricted_modules")),
    )


@router.get("/subaccounts/{subaccount_id}/members", response_model=SubaccountTeamMemberListResponse)
def list_subaccount_team_members(
    subaccount_id: int,
    search: str = Query(default=""),
    user_role: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> SubaccountTeamMemberListResponse:
    enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=subaccount_id)
    try:
        items, total = team_members_service.list_subaccount_members(
            subaccount_id=subaccount_id,
            search=search,
            user_role=user_role,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        if "inexistent" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SubaccountTeamMemberListResponse(items=items, total=total, page=page, page_size=page_size, subaccount_id=subaccount_id)


@router.post("/subaccounts/{subaccount_id}/members", response_model=SubaccountTeamMemberResponse)
def create_subaccount_team_member(
    subaccount_id: int,
    payload: CreateSubaccountTeamMemberRequest,
    user: AuthUser = Depends(get_current_user),
) -> SubaccountTeamMemberResponse:
    enforce_subaccount_action(user=user, action="team:subaccount:create", subaccount_id=subaccount_id)
    try:
        item = team_members_service.create_subaccount_member(
            subaccount_id=subaccount_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            extension=payload.extension,
            user_role=payload.user_role,
            password=payload.password,
            module_keys=payload.module_keys,
            actor_user=user,
        )
    except ValueError as exc:
        if "inexistent" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SubaccountTeamMemberResponse(item=item)
