from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.services.auth import AuthError, AuthUser, decode_access_token
from app.services.rbac import AuthorizationError, Scope, require_action


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
