from __future__ import annotations


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {"clients:create", "audit:read", "clients:read"},
    "agency_admin": {"clients:create", "audit:read", "clients:read"},
    "account_manager": {"clients:read"},
    "client_viewer": {"clients:read"},
}


class AuthorizationError(RuntimeError):
    pass


def require_permission(role: str, permission: str) -> None:
    permissions = ROLE_PERMISSIONS.get(role, set())
    if permission not in permissions:
        raise AuthorizationError(f"Role '{role}' does not have permission '{permission}'")
