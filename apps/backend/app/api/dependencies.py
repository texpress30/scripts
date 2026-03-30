from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.services.auth import AuthError, AuthUser, decode_access_token, is_active_user_id
from app.services.rbac import AuthorizationError, Scope, normalize_role, require_action
from app.services.team_members import team_members_service

SUBACCOUNT_MODULE_KEYS: set[str] = {"dashboard", "campaigns", "rules", "creative", "recommendations", "settings"}
AGENCY_NAVIGATION_KEYS: set[str] = {
    "agency_dashboard",
    "agency_clients",
    "agency_accounts",
    "integrations",
    "agency_audit",
    "creative",
    "settings",
    "settings_profile",
    "settings_company",
    "settings_my_team",
    "settings_tags",
    "settings_audit_logs",
    "settings_ai_agents",
    "settings_media_storage_usage",
    "email_templates",
    "notifications",
}
AGENCY_SETTINGS_PARENT_KEY = "settings"
AGENCY_SETTINGS_CHILD_KEYS: set[str] = {
    "settings_profile",
    "settings_company",
    "settings_my_team",
    "settings_tags",
    "settings_audit_logs",
    "settings_ai_agents",
    "settings_media_storage_usage",
    "email_templates",
    "notifications",
}
NAVIGATION_ACCESS_DENIED_MESSAGE = "Nu ai acces la această secțiune"


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization scheme")

    token = authorization.split(" ", maxsplit=1)[1].strip()
    try:
        user = decode_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if user.is_env_admin:
        return user
    if user.user_id is None:
        return user
    try:
        if not is_active_user_id(int(user.user_id)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid pentru utilizator inexistent sau inactiv")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid") from exc
    return user


def enforce_action_scope(*, user: AuthUser, action: str, scope: Scope) -> None:
    try:
        require_action(user.role, action=action, scope=scope)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def enforce_subaccount_action(*, user: AuthUser, action: str, subaccount_id: int) -> None:
    enforce_action_scope(user=user, action=action, scope="subaccount")

    role = normalize_role(user.role)
    if role in {"super_admin", "agency_owner", "agency_admin"}:
        return
    if role in {"agency_member", "agency_viewer"}:
        requested_subaccount_id = int(subaccount_id)
        if len(user.allowed_subaccount_ids) == 0:
            return
        if requested_subaccount_id not in {int(value) for value in user.allowed_subaccount_ids}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nu ai acces la acest sub-account",
            )
        return
    if role.startswith("subaccount_"):
        requested_subaccount_id = int(subaccount_id)

        if len(user.allowed_subaccount_ids) > 0:
            if requested_subaccount_id not in {int(value) for value in user.allowed_subaccount_ids}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Nu ai acces la acest sub-account",
                )
            return

        legacy_subaccount_id = user.subaccount_id if user.subaccount_id is not None else user.primary_subaccount_id
        if legacy_subaccount_id is not None and int(legacy_subaccount_id) != requested_subaccount_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nu ai acces la acest sub-account",
            )


def enforce_subaccount_module_access(*, user: AuthUser, subaccount_id: int, module_key: str) -> None:
    enforce_subaccount_navigation_access(user=user, subaccount_id=subaccount_id, permission_key=module_key)


def _resolve_agency_access_module_keys(user: AuthUser) -> set[str]:
    try:
        payload = team_members_service.get_agency_my_access(actor_user=user)
    except Exception:  # noqa: BLE001
        payload = team_members_service.get_agency_my_access_fallback(actor_user=user)
    return {
        str(item or "").strip().lower()
        for item in payload.get("module_keys", [])
        if str(item or "").strip() != ""
    }


def enforce_agency_navigation_access(*, user: AuthUser, permission_key: str) -> None:
    requested_key = str(permission_key or "").strip().lower()
    if requested_key not in AGENCY_NAVIGATION_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Modul invalid")

    role = normalize_role(user.role)
    if role in {"super_admin", "agency_owner", "agency_admin"}:
        return
    if role.startswith("subaccount_"):
        return
    if not role.startswith("agency_"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NAVIGATION_ACCESS_DENIED_MESSAGE)

    module_keys = _resolve_agency_access_module_keys(user=user)
    if requested_key not in module_keys:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NAVIGATION_ACCESS_DENIED_MESSAGE)
    if requested_key in AGENCY_SETTINGS_CHILD_KEYS and AGENCY_SETTINGS_PARENT_KEY not in module_keys:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NAVIGATION_ACCESS_DENIED_MESSAGE)


def enforce_subaccount_navigation_access(*, user: AuthUser, subaccount_id: int, permission_key: str) -> None:
    requested_module = str(permission_key or "").strip().lower()
    if requested_module not in SUBACCOUNT_MODULE_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Modul invalid")

    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)

    role = normalize_role(user.role)
    if not role.startswith("subaccount_"):
        return

    try:
        access_context = team_members_service.get_subaccount_my_access(actor_user=user, subaccount_id=int(subaccount_id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    module_keys = {
        str(item or "").strip().lower()
        for item in access_context.get("module_keys", [])
        if str(item or "").strip() != ""
    }

    if requested_module not in module_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NAVIGATION_ACCESS_DENIED_MESSAGE,
        )
