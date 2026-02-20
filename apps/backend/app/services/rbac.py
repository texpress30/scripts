from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Scope = Literal["agency", "subaccount"]


@dataclass(frozen=True)
class ActionPolicy:
    permission: str
    scope: Scope



ROLE_SCOPES: dict[str, set[Scope]] = {
    "super_admin": {"agency", "subaccount"},
    "agency_owner": {"agency", "subaccount"},
    "agency_admin": {"agency", "subaccount"},
    "account_manager": {"subaccount"},
    "client_viewer": {"subaccount"},
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {
        "clients:create",
        "clients:read",
        "audit:read",
        "integrations:status",
        "integrations:sync",
        "integrations:tiktok:status",
        "integrations:tiktok:sync",
        "integrations:pinterest:status",
        "integrations:pinterest:sync",
        "integrations:snapchat:status",
        "integrations:snapchat:sync",
        "rules:read",
        "rules:write",
        "insights:read",
        "insights:generate",
        "exports:read",
        "exports:run",
        "recommendations:read",
        "recommendations:review",
        "creative:read",
        "creative:write",
    },
    "agency_owner": {
        "clients:create",
        "clients:read",
        "audit:read",
        "integrations:status",
        "integrations:sync",
        "integrations:tiktok:status",
        "integrations:tiktok:sync",
        "integrations:pinterest:status",
        "integrations:pinterest:sync",
        "integrations:snapchat:status",
        "integrations:snapchat:sync",
        "rules:read",
        "rules:write",
        "insights:read",
        "insights:generate",
        "exports:read",
        "exports:run",
        "recommendations:read",
        "recommendations:review",
        "creative:read",
        "creative:write",
    },
    "agency_admin": {
        "clients:create",
        "clients:read",
        "audit:read",
        "integrations:status",
        "integrations:sync",
        "integrations:tiktok:status",
        "integrations:tiktok:sync",
        "integrations:pinterest:status",
        "integrations:pinterest:sync",
        "integrations:snapchat:status",
        "integrations:snapchat:sync",
        "rules:read",
        "rules:write",
        "insights:read",
        "insights:generate",
        "exports:read",
        "exports:run",
        "recommendations:read",
        "recommendations:review",
        "creative:read",
        "creative:write",
    },
    "account_manager": {
        "clients:read",
        "rules:read",
        "insights:read",
        "recommendations:read",
        "creative:read",
    },
    "client_viewer": {
        "clients:read",
        "rules:read",
        "insights:read",
        "recommendations:read",
        "creative:read",
    },
}


ACTION_POLICIES: dict[str, ActionPolicy] = {
    # agency scope
    "clients:list": ActionPolicy(permission="clients:read", scope="agency"),
    "clients:create": ActionPolicy(permission="clients:create", scope="agency"),
    "audit:list": ActionPolicy(permission="audit:read", scope="agency"),
    "integrations:status": ActionPolicy(permission="integrations:status", scope="agency"),
    "integrations:tiktok:status": ActionPolicy(permission="integrations:tiktok:status", scope="agency"),
    "integrations:pinterest:status": ActionPolicy(permission="integrations:pinterest:status", scope="agency"),
    "integrations:snapchat:status": ActionPolicy(permission="integrations:snapchat:status", scope="agency"),
    "exports:list": ActionPolicy(permission="exports:read", scope="agency"),
    # sub-account scope
    "dashboard:view": ActionPolicy(permission="clients:read", scope="subaccount"),
    "integrations:sync": ActionPolicy(permission="integrations:sync", scope="subaccount"),
    "integrations:tiktok:sync": ActionPolicy(permission="integrations:tiktok:sync", scope="subaccount"),
    "integrations:pinterest:sync": ActionPolicy(permission="integrations:pinterest:sync", scope="subaccount"),
    "integrations:snapchat:sync": ActionPolicy(permission="integrations:snapchat:sync", scope="subaccount"),
    "rules:list": ActionPolicy(permission="rules:read", scope="subaccount"),
    "rules:create": ActionPolicy(permission="rules:write", scope="subaccount"),
    "rules:evaluate": ActionPolicy(permission="rules:write", scope="subaccount"),
    "insights:get": ActionPolicy(permission="insights:read", scope="subaccount"),
    "insights:generate": ActionPolicy(permission="insights:generate", scope="subaccount"),
    "exports:run": ActionPolicy(permission="exports:run", scope="subaccount"),
    "recommendations:list": ActionPolicy(permission="recommendations:read", scope="subaccount"),
    "recommendations:review": ActionPolicy(permission="recommendations:review", scope="subaccount"),
    "creative:list": ActionPolicy(permission="creative:read", scope="subaccount"),
    "creative:write": ActionPolicy(permission="creative:write", scope="subaccount"),
}


class AuthorizationError(RuntimeError):
    pass


def require_permission(role: str, permission: str) -> None:
    permissions = ROLE_PERMISSIONS.get(role, set())
    if permission not in permissions:
        raise AuthorizationError(f"Role '{role}' does not have permission '{permission}'")


def require_action(role: str, action: str, scope: Scope) -> None:
    policy = ACTION_POLICIES.get(action)
    if policy is None:
        raise AuthorizationError(f"Unknown action '{action}'")
    if policy.scope != scope:
        raise AuthorizationError(
            f"Action '{action}' is not allowed in scope '{scope}' (expected '{policy.scope}')"
        )

    role_scopes = ROLE_SCOPES.get(role, set())
    if scope not in role_scopes:
        raise AuthorizationError(f"Role '{role}' is not allowed in scope '{scope}'")

    require_permission(role, policy.permission)
