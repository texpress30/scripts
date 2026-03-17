from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.services.auth import AuthError, AuthUser, decode_access_token
from app.services.rbac import AuthorizationError, Scope, normalize_role, require_action


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization scheme")

    token = authorization.split(" ", maxsplit=1)[1].strip()
    try:
        return decode_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def enforce_action_scope(*, user: AuthUser, action: str, scope: Scope) -> None:
    try:
        require_action(user.role, action=action, scope=scope)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def enforce_subaccount_action(*, user: AuthUser, action: str, subaccount_id: int) -> None:
    enforce_action_scope(user=user, action=action, scope="subaccount")

    role = normalize_role(user.role)
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
