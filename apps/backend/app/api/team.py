from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.team import (
    CreateTeamMemberRequest,
    TeamMemberListResponse,
    TeamMemberResponse,
    TeamSubaccountOptionItem,
    TeamSubaccountOptionsResponse,
)
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
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


@router.get("/subaccount-options", response_model=TeamSubaccountOptionsResponse)
def list_subaccount_options(user: AuthUser = Depends(get_current_user)) -> TeamSubaccountOptionsResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items: list[TeamSubaccountOptionItem] = []
    for row in client_registry_service.list_clients():
        client_id = row.get("id")
        name = str(row.get("name") or "").strip()
        if client_id is None or name == "":
            continue
        display_id = row.get("display_id")
        label = f"#{display_id} — {name}" if display_id is not None else name
        items.append(TeamSubaccountOptionItem(id=int(client_id), name=name, label=label))
    return TeamSubaccountOptionsResponse(items=items)
