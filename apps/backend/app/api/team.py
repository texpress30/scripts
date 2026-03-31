import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)

from app.api.dependencies import (
    enforce_action_scope,
    enforce_agency_navigation_access,
    enforce_subaccount_action,
    enforce_subaccount_navigation_access,
    get_current_user,
)
from app.core.config import load_settings
from app.schemas.team import (
    CreateSubaccountTeamMemberRequest,
    CreateTeamMemberRequest,
    SubaccountTeamMemberListResponse,
    SubaccountTeamMemberResponse,
    TeamMemberInviteResponse,
    TeamMemberListResponse,
    TeamMemberResponse,
    TeamMembershipStatusResponse,
    TeamMembershipRemoveResponse,
    TeamUserDeleteResponse,
    TeamModuleCatalogResponse,
    TeamGrantableModulesResponse,
    TeamSubaccountMyAccessResponse,
    TeamAgencyMyAccessResponse,
    TeamSubaccountOptionItem,
    TeamSubaccountOptionsResponse,
    TeamMembershipDetailResponse,
    UpdateTeamMembershipRequest,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.auth_email_tokens import auth_email_tokens_service
from app.services.client_registry import client_registry_service
from app.services.mailgun_service import MailgunIntegrationError, mailgun_service
from app.services.email_notifications import email_notifications_service
from app.services.email_templates import email_templates_service
from app.services.team_members import team_members_service

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

router = APIRouter(prefix="/team", tags=["team"])


def _enforce_membership_edit_actor_role(user: AuthUser) -> None:
    role = str(user.role or "").strip().lower()
    if role in {"super_admin", "agency_owner", "agency_admin", "subaccount_admin"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nu ai permisiunea să editezi acest membership")


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

    allowed_subaccount_ids: list[int] = []
    raw_allowed_ids = raw.get("allowed_subaccount_ids")
    if isinstance(raw_allowed_ids, list):
        for item in raw_allowed_ids:
            try:
                value = int(item)
            except Exception:  # noqa: BLE001
                continue
            if value not in allowed_subaccount_ids:
                allowed_subaccount_ids.append(value)

    allowed_subaccounts: list[dict[str, object]] = []
    raw_allowed = raw.get("allowed_subaccounts")
    if isinstance(raw_allowed, list):
        for item in raw_allowed:
            if not isinstance(item, dict):
                continue
            try:
                subaccount_id = int(item.get("id"))
            except Exception:  # noqa: BLE001
                continue
            name = str(item.get("name") or "")
            if not any(int(existing.get("id", -1)) == subaccount_id for existing in allowed_subaccounts):
                allowed_subaccounts.append({"id": subaccount_id, "name": name, "label": name or str(subaccount_id)})

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
        "allowed_subaccount_ids": allowed_subaccount_ids,
        "allowed_subaccounts": allowed_subaccounts,
        "has_restricted_subaccount_access": bool(raw.get("has_restricted_subaccount_access", False)),
        "membership_status": str(raw.get("membership_status") or "active").strip().lower() or "active",
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
        group_key = str(item.get("group_key") or "").strip().lower()
        group_label = str(item.get("group_label") or "").strip() or group_key.replace("_", " ").title()
        parent_key_raw = str(item.get("parent_key") or "").strip().lower()
        parent_key = parent_key_raw or None
        is_container = bool(item.get("is_container", False))
        normalized.append(
            {
                "key": key,
                "label": label,
                "order": order,
                "scope": scope,
                "group_key": group_key,
                "group_label": group_label,
                "parent_key": parent_key,
                "is_container": is_container,
            }
        )
    normalized.sort(key=lambda row: (int(row["order"]), str(row["label"]).lower(), str(row["key"])))
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
    enforce_agency_navigation_access(user=user, permission_key="settings_my_team")
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
        logger.exception("team.list_members error")
        if _is_db_unavailable_error(exc):
            return TeamMemberListResponse(items=[], total=0, page=page, page_size=page_size)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nu am putut încărca lista de utilizatori: {exc}",
        ) from exc
    return TeamMemberListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/members", response_model=TeamMemberResponse)
def create_team_member(payload: CreateTeamMemberRequest, user: AuthUser = Depends(get_current_user)) -> TeamMemberResponse:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_my_team")

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
            allowed_subaccount_ids=payload.allowed_subaccount_ids,
            actor_user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Nu am putut adăuga utilizatorul: {exc}") from exc

    return TeamMemberResponse(item=item)




@router.get("/members/{membership_id}", response_model=TeamMembershipDetailResponse)
def get_team_membership_detail(
    membership_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamMembershipDetailResponse:
    _enforce_membership_edit_actor_role(user)
    try:
        item = team_members_service.get_membership_detail(membership_id=membership_id, actor_user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership inexistent")

    return TeamMembershipDetailResponse(item=item)


@router.patch("/members/{membership_id}", response_model=TeamMembershipDetailResponse)
def patch_team_membership(
    membership_id: int,
    payload: UpdateTeamMembershipRequest,
    user: AuthUser = Depends(get_current_user),
) -> TeamMembershipDetailResponse:
    _enforce_membership_edit_actor_role(user)
    if payload.user_role is None and payload.module_keys is None and payload.allowed_subaccount_ids is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nu există câmpuri de actualizat")

    try:
        item = team_members_service.update_membership(
            membership_id=membership_id,
            actor_user=user,
            user_role=payload.user_role,
            module_keys=payload.module_keys,
            allowed_subaccount_ids=payload.allowed_subaccount_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TeamMembershipDetailResponse(item=item)


@router.post("/members/{membership_id}/deactivate", response_model=TeamMembershipStatusResponse)
def deactivate_team_membership(
    membership_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamMembershipStatusResponse:
    _enforce_membership_edit_actor_role(user)
    try:
        payload = team_members_service.deactivate_membership(membership_id=membership_id, actor_user=user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TeamMembershipStatusResponse(
        membership_id=int(payload.get("membership_id") or membership_id),
        status=str(payload.get("status") or "inactive"),
        message=str(payload.get("message") or "Membership dezactivat"),
    )


@router.post("/members/{membership_id}/reactivate", response_model=TeamMembershipStatusResponse)
def reactivate_team_membership(
    membership_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamMembershipStatusResponse:
    _enforce_membership_edit_actor_role(user)
    try:
        payload = team_members_service.reactivate_membership(membership_id=membership_id, actor_user=user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TeamMembershipStatusResponse(
        membership_id=int(payload.get("membership_id") or membership_id),
        status=str(payload.get("status") or "active"),
        message=str(payload.get("message") or "Membership reactivat"),
    )


@router.post("/members/{membership_id}/remove", response_model=TeamMembershipRemoveResponse)
def remove_team_membership(
    membership_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamMembershipRemoveResponse:
    _enforce_membership_edit_actor_role(user)
    try:
        payload = team_members_service.remove_membership(membership_id=membership_id, actor_user=user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TeamMembershipRemoveResponse(
        membership_id=int(payload.get("membership_id") or membership_id),
        removed=bool(payload.get("removed", True)),
        message=str(payload.get("message") or "Membership eliminat"),
    )


@router.post("/users/{user_id}/delete", response_model=TeamUserDeleteResponse)
def delete_team_user_hard(
    user_id: int,
    user: AuthUser = Depends(get_current_user),
) -> TeamUserDeleteResponse:
    _enforce_membership_edit_actor_role(user)
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_my_team")
    try:
        payload = team_members_service.delete_user_hard(user_id=user_id, actor_user=user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TeamUserDeleteResponse(
        user_id=int(payload.get("user_id") or user_id),
        deleted=bool(payload.get("deleted", True)),
        deleted_memberships_count=int(payload.get("deleted_memberships_count") or 0),
        message=str(payload.get("message") or "Utilizator șters complet din sistem"),
    )

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

    runtime_notification = email_notifications_service.resolve_runtime_notification(notification_key="team_invite_user")
    if runtime_notification is None:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "notification_missing", "notification_key": "team_invite_user"},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")
    if not runtime_notification.enabled:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.blocked",
            resource=f"team:membership:{membership_id}",
            details={"reason": "notification_disabled", "notification_key": runtime_notification.key},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Notificarea de invitație este dezactivată")

    settings = load_settings()
    frontend_base_url = str(settings.frontend_base_url or "").strip()
    if frontend_base_url == "":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")

    should_send_reset_link = bool(membership.get("must_reset_password", True))
    logger.info(
        "team.invite membership_id=%s email=%s must_reset_password=%s template=%s",
        membership_id, email, should_send_reset_link,
        "team_invite_user" if should_send_reset_link else "team_account_ready",
    )
    if should_send_reset_link:
        invite_ttl_minutes = max(1, int(getattr(settings, "auth_reset_token_ttl_minutes", 60)))
        raw_token, _ = auth_email_tokens_service.create_user_invite_token_for_existing_user(
            user_id=int(membership["user_id"]),
            email=email,
            expires_in_minutes=invite_ttl_minutes,
        )
        template_key = "team_invite_user"
        template_variables = {
            "invite_link": f"{frontend_base_url.rstrip('/')}/reset-password?token={raw_token}",
            "expires_minutes": str(invite_ttl_minutes),
            "user_email": email,
        }
    else:
        template_key = "team_account_ready"
        template_variables = {
            "login_link": f"{frontend_base_url.rstrip('/')}/login",
            "user_email": email,
        }

    rendered_template = email_templates_service.render_effective_template(
        template_key=template_key,
        variables=template_variables,
    )
    if rendered_template is None:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "template_missing", "template_key": template_key},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")
    if not rendered_template.enabled:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "template_disabled", "template_key": template_key},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invitația nu este disponibilă momentan")

    try:
        mailgun_service.send_email(
            to_email=email,
            subject=rendered_template.subject,
            text=rendered_template.text_body,
            html=rendered_template.html_body,
        )
    except (MailgunIntegrationError, ValueError) as exc:
        logger.exception("team.invite.send_failed membership_id=%s email=%s template=%s", membership_id, email, template_key)
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="team.invite.failed",
            resource=f"team:membership:{membership_id}",
            details={"reason": "mail_send_failed", "error": str(exc)[:300]},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Invitația nu a putut fi trimisă: {str(exc)[:200]}") from exc

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
    enforce_subaccount_navigation_access(user=user, subaccount_id=subaccount_id, permission_key="settings")

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


@router.get("/agency/my-access", response_model=TeamAgencyMyAccessResponse)
def get_agency_my_access(
    user: AuthUser = Depends(get_current_user),
) -> TeamAgencyMyAccessResponse:
    try:
        payload = team_members_service.get_agency_my_access(actor_user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if _is_db_unavailable_error(exc):
            payload = team_members_service.get_agency_my_access_fallback(actor_user=user)
        else:
            raise

    return TeamAgencyMyAccessResponse(
        role=str(payload.get("role") or user.role),
        module_keys=_normalize_module_keys(payload.get("module_keys")),
        source_scope=str(payload.get("source_scope") or "agency"),
        access_scope=str(payload.get("access_scope") or (user.access_scope or "agency")),
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
    enforce_subaccount_navigation_access(user=user, subaccount_id=subaccount_id, permission_key="settings")
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
    enforce_subaccount_navigation_access(user=user, subaccount_id=subaccount_id, permission_key="settings")
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
