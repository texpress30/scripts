from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

_logger = logging.getLogger(__name__)


Scope = Literal["agency", "subaccount"]


@dataclass(frozen=True)
class ActionPolicy:
    permission: str
    scopes: tuple[Scope, ...]


CANONICAL_ROLES: set[str] = {
    "agency_owner",
    "agency_admin",
    "agency_member",
    "agency_viewer",
    "subaccount_admin",
    "subaccount_user",
    "subaccount_viewer",
}

SPECIAL_ROLES: set[str] = {"super_admin"}

LEGACY_ROLE_ALIASES: dict[str, str] = {
    "account_manager": "subaccount_user",
    "client_viewer": "subaccount_viewer",
}


def normalize_role(role: str) -> str:
    candidate = role.strip().lower()
    if candidate in CANONICAL_ROLES or candidate in SPECIAL_ROLES:
        return candidate
    return LEGACY_ROLE_ALIASES.get(candidate, candidate)


def is_supported_role(role: str) -> bool:
    normalized = normalize_role(role)
    return normalized in ROLE_PERMISSIONS


ROLE_SCOPES: dict[str, set[Scope]] = {
    "super_admin": {"agency", "subaccount"},
    "agency_owner": {"agency", "subaccount"},
    "agency_admin": {"agency", "subaccount"},
    "agency_member": {"agency", "subaccount"},
    "agency_viewer": {"agency", "subaccount"},
    "subaccount_admin": {"subaccount"},
    "subaccount_user": {"subaccount"},
    "subaccount_viewer": {"subaccount"},
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {
        "clients:create",
        "clients:read",
        "data:write",
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
        "data:write",
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
    # Canonical agency roles
    "agency_admin": {
        "clients:create",
        "clients:read",
        "data:write",
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
    "agency_member": {
        "clients:read",
        "data:write",
        "integrations:status",
        "integrations:tiktok:status",
        "integrations:pinterest:status",
        "integrations:snapchat:status",
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
    "agency_viewer": {
        "clients:read",
        "integrations:status",
        "integrations:tiktok:status",
        "integrations:pinterest:status",
        "integrations:snapchat:status",
        "rules:read",
        "insights:read",
        "exports:read",
        "recommendations:read",
        "creative:read",
    },
    # Canonical subaccount roles
    "subaccount_admin": {
        "clients:read",
        "data:write",
        "integrations:sync",
        "integrations:tiktok:sync",
        "integrations:pinterest:sync",
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
    "subaccount_user": {
        "clients:read",
        "data:write",
        "rules:read",
        "rules:write",
        "insights:read",
        "insights:generate",
        "exports:read",
        "exports:run",
        "recommendations:read",
        "creative:read",
        "creative:write",
    },
    "subaccount_viewer": {
        "clients:read",
        "rules:read",
        "insights:read",
        "exports:read",
        "recommendations:read",
        "creative:read",
    },
}


ACTION_POLICIES: dict[str, ActionPolicy] = {
    # agency scope
    "clients:list": ActionPolicy(permission="clients:read", scopes=("agency", "subaccount")),
    "clients:create": ActionPolicy(permission="clients:create", scopes=("agency", "subaccount")),
    "audit:list": ActionPolicy(permission="audit:read", scopes=("agency",)),
    "integrations:status": ActionPolicy(permission="integrations:status", scopes=("agency",)),
    "integrations:tiktok:status": ActionPolicy(permission="integrations:tiktok:status", scopes=("agency",)),
    "integrations:pinterest:status": ActionPolicy(permission="integrations:pinterest:status", scopes=("agency",)),
    "integrations:snapchat:status": ActionPolicy(permission="integrations:snapchat:status", scopes=("agency",)),
    "integrations:mailgun:config": ActionPolicy(permission="clients:create", scopes=("agency",)),
    "integrations:mailgun:test": ActionPolicy(permission="clients:create", scopes=("agency",)),
    "exports:list": ActionPolicy(permission="exports:read", scopes=("agency",)),
    # sub-account scope – data write (daily inputs, sale entries, custom fields, media tracker, imports)
    "data:write": ActionPolicy(permission="data:write", scopes=("agency", "subaccount")),
    "dashboard:view": ActionPolicy(permission="clients:read", scopes=("agency", "subaccount")),
    "integrations:sync": ActionPolicy(permission="integrations:sync", scopes=("agency", "subaccount")),
    "integrations:tiktok:sync": ActionPolicy(permission="integrations:tiktok:sync", scopes=("subaccount",)),
    "integrations:pinterest:sync": ActionPolicy(permission="integrations:pinterest:sync", scopes=("subaccount",)),
    "integrations:snapchat:sync": ActionPolicy(permission="integrations:snapchat:sync", scopes=("subaccount",)),
    "rules:list": ActionPolicy(permission="rules:read", scopes=("subaccount",)),
    "rules:create": ActionPolicy(permission="rules:write", scopes=("subaccount",)),
    "rules:evaluate": ActionPolicy(permission="rules:write", scopes=("subaccount",)),
    "insights:get": ActionPolicy(permission="insights:read", scopes=("subaccount",)),
    "insights:generate": ActionPolicy(permission="insights:generate", scopes=("subaccount",)),
    "exports:run": ActionPolicy(permission="exports:run", scopes=("subaccount",)),
    "recommendations:list": ActionPolicy(permission="recommendations:read", scopes=("subaccount",)),
    "recommendations:review": ActionPolicy(permission="recommendations:review", scopes=("subaccount",)),
    "creative:list": ActionPolicy(permission="creative:read", scopes=("subaccount",)),
    "creative:write": ActionPolicy(permission="creative:write", scopes=("subaccount",)),
    "team:subaccount:list": ActionPolicy(permission="clients:read", scopes=("subaccount",)),
    "team:subaccount:create": ActionPolicy(permission="rules:write", scopes=("subaccount",)),
    "team:invite": ActionPolicy(permission="rules:write", scopes=("agency", "subaccount")),
}


class AuthorizationError(RuntimeError):
    pass


def require_permission(role: str, permission: str) -> None:
    normalized_role = normalize_role(role)
    permissions = ROLE_PERMISSIONS.get(normalized_role, set())
    if permission not in permissions:
        raise AuthorizationError(f"Role '{normalized_role}' does not have permission '{permission}'")


def require_action(role: str, action: str, scope: Scope) -> None:
    normalized_role = normalize_role(role)
    policy = ACTION_POLICIES.get(action)
    if policy is None:
        raise AuthorizationError(f"Unknown action '{action}'")
    if scope not in policy.scopes:
        expected = ", ".join(policy.scopes)
        raise AuthorizationError(
            f"Action '{action}' is not allowed in scope '{scope}' (expected one of: {expected})"
        )

    role_scopes = ROLE_SCOPES.get(normalized_role, set())
    if scope not in role_scopes:
        raise AuthorizationError(f"Role '{normalized_role}' is not allowed in scope '{scope}'")

    require_permission(normalized_role, policy.permission)


def log_auth_config() -> None:
    """Log the complete ACTION_POLICIES → accepted roles mapping at startup."""
    for action_name, policy in sorted(ACTION_POLICIES.items()):
        accepted_roles = sorted(
            role
            for role, perms in ROLE_PERMISSIONS.items()
            if policy.permission in perms
            and any(s in ROLE_SCOPES.get(role, set()) for s in policy.scopes)
        )
        _logger.info(
            "[AUTH-CONFIG] %s → scopes=%s, permission=%s, accepted_roles=%s",
            action_name,
            list(policy.scopes),
            policy.permission,
            accepted_roles,
        )
