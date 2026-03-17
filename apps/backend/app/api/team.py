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
    TeamSubaccountOptionItem,
    TeamSubaccountOptionsResponse,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.auth_email_tokens import auth_email_tokens_service
from app.services.client_registry import client_registry_service
from app.services.mailgun_service import MailgunIntegrationError, mailgun_service
from app.services.team_members import team_members_service

router = APIRouter(prefix="/team", tags=["team"])


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
        items, total = team_members_service.list_members(
            search=search,
            user_type=user_type,
            user_role=user_role,
            subaccount=subaccount,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@router.get("/subaccount-options", response_model=TeamSubaccountOptionsResponse)
def list_subaccount_options(user: AuthUser = Depends(get_current_user)) -> TeamSubaccountOptionsResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items: list[TeamSubaccountOptionItem] = []
    for row in client_registry_service.list_clients():
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
        )
    except ValueError as exc:
        if "inexistent" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SubaccountTeamMemberResponse(item=item)
