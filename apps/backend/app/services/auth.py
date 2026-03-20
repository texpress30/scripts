from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from app.core.config import load_settings
from app.services.rbac import normalize_role

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


@dataclass(frozen=True)
class AuthUser:
    email: str
    role: str
    user_id: int | None = None
    scope_type: str | None = None
    membership_id: int | None = None
    subaccount_id: int | None = None
    subaccount_name: str = ""
    access_scope: str | None = None
    allowed_subaccount_ids: tuple[int, ...] = ()
    allowed_subaccounts: tuple[dict[str, object], ...] = ()
    primary_subaccount_id: int | None = None
    membership_ids: tuple[int, ...] = ()
    is_env_admin: bool = False


class AuthError(RuntimeError):
    pass


class AuthLoginError(RuntimeError):
    def __init__(self, *, status_code: int, message: str, reason: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reason = reason


def _connect():
    settings = load_settings()
    if psycopg is None:
        raise RuntimeError("psycopg is required for DB-backed authentication")
    return psycopg.connect(settings.database_url)


def hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), str(password_hash))


def _sign(payload: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def validate_login_credentials(email: str, password: str) -> bool:
    settings = load_settings()
    return email.strip().lower() == settings.app_login_email.strip().lower() and password == settings.app_login_password




def validate_new_password(password: str) -> str:
    candidate = str(password or "")
    if len(candidate.strip()) < 8:
        raise ValueError("Parola nouă trebuie să aibă cel puțin 8 caractere")
    return candidate


def find_active_user_by_email(email: str) -> dict[str, object] | None:
    normalized_email = str(email or "").strip().lower()
    if normalized_email == "":
        return None

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, is_active
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    is_active = bool(row[2])
    if not is_active:
        return None

    return {
        "id": int(row[0]),
        "email": str(row[1]).strip().lower(),
        "is_active": True,
    }


def is_active_user_id(user_id: int) -> bool:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT is_active
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
    if row is None:
        return False
    return bool(row[0])


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return None


def _normalize_int_list(values: object) -> tuple[int, ...]:
    if not isinstance(values, list):
        return ()
    result: list[int] = []
    for value in values:
        numeric = _coerce_int(value)
        if numeric is None:
            continue
        if numeric not in result:
            result.append(numeric)
    return tuple(result)


def _normalize_subaccount_objects(values: object) -> tuple[dict[str, object], ...]:
    if not isinstance(values, list):
        return ()
    normalized: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        subaccount_id = _coerce_int(value.get("id"))
        if subaccount_id is None:
            continue
        name = str(value.get("name") or "")
        normalized.append({"id": subaccount_id, "name": name})
    return tuple(normalized)


def set_user_password(*, user_id: int, new_password: str) -> None:
    normalized = validate_new_password(new_password)
    password_hash = hash_password(normalized)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s, must_reset_password = FALSE, updated_at = NOW()
                WHERE id = %s AND is_active = TRUE
                """,
                (password_hash, int(user_id)),
            )
            if int(cur.rowcount or 0) != 1:
                raise ValueError("Utilizator inactiv sau inexistent")
        conn.commit()

def _is_subaccount_role(role: str) -> bool:
    return role in {"subaccount_admin", "subaccount_user", "subaccount_viewer"}


def _resolve_role_from_memberships(
    memberships: list[tuple[int, str, str, int | None, str]],
    requested_role: str | None,
) -> tuple[str, list[tuple[int, str, str, int | None, str]]]:
    by_role: dict[str, list[tuple[int, str, str, int | None, str]]] = {}
    for membership in memberships:
        role_key = normalize_role(str(membership[1] or ""))
        by_role.setdefault(role_key, []).append(membership)

    normalized_requested = normalize_role(str(requested_role or "").strip())
    if normalized_requested:
        selected = by_role.get(normalized_requested, [])
        if not selected:
            raise AuthLoginError(
                status_code=403,
                message="Rolul selectat nu este alocat utilizatorului",
                reason="role_not_owned",
            )
        return normalized_requested, selected

    role_priority = (
        "super_admin",
        "agency_owner",
        "agency_admin",
        "agency_member",
        "agency_viewer",
        "subaccount_admin",
        "subaccount_user",
        "subaccount_viewer",
    )
    for role_key in role_priority:
        selected = by_role.get(role_key, [])
        if selected:
            return role_key, selected

    raise AuthLoginError(
        status_code=403,
        message="User has no active membership",
        reason="no_active_membership",
    )


def authenticate_user_from_db(*, email: str, password: str, requested_role: str | None = None) -> AuthUser:
    normalized_email = email.strip().lower()

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, is_active, must_reset_password
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            )
            user_row = cur.fetchone()
            if user_row is None:
                raise AuthLoginError(status_code=401, message="Invalid email or password", reason="invalid_credentials")

            user_id = int(user_row[0])
            user_email = str(user_row[1]).strip().lower()
            password_hash = str(user_row[2] or "")
            is_active = bool(user_row[3])
            must_reset_password = bool(user_row[4])

            if not is_active:
                raise AuthLoginError(status_code=403, message="User account is inactive", reason="user_inactive")
            if must_reset_password:
                raise AuthLoginError(
                    status_code=403,
                    message="User must set password before login",
                    reason="password_setup_required",
                )
            if not verify_password(password, password_hash):
                raise AuthLoginError(status_code=401, message="Invalid email or password", reason="invalid_credentials")

            cur.execute(
                """
                SELECT id, role_key, scope_type, subaccount_id, subaccount_name
                FROM user_memberships
                WHERE user_id = %s AND status = 'active'
                ORDER BY id ASC
                """,
                (user_id,),
            )
            memberships = cur.fetchall()
            if len(memberships) == 0:
                raise AuthLoginError(status_code=403, message="User has no active membership", reason="no_active_membership")

            normalized_memberships = [
                (
                    int(row[0]),
                    normalize_role(str(row[1] or "")),
                    str(row[2] or ""),
                    _coerce_int(row[3]),
                    str(row[4] or ""),
                )
                for row in memberships
            ]
            normalized_role, selected_memberships = _resolve_role_from_memberships(normalized_memberships, requested_role)
            role_is_subaccount = _is_subaccount_role(normalized_role)

            membership_ids = tuple(int(row[0]) for row in selected_memberships)
            first_membership = selected_memberships[0]
            scope_type = str(first_membership[2] or "") or None

            allowed_subaccounts_map: dict[int, str] = {}
            if normalized_role in {"agency_member", "agency_viewer"}:
                selected_membership_ids = [int(row[0]) for row in selected_memberships]
                if selected_membership_ids:
                    cur.execute(
                        """
                        SELECT subaccount_id
                        FROM membership_subaccount_access_grants
                        WHERE membership_id = ANY(%s)
                        ORDER BY subaccount_id ASC
                        """,
                        (selected_membership_ids,),
                    )
                    grant_rows = cur.fetchall()
                    for grant_row in grant_rows:
                        subaccount_id = _coerce_int(grant_row[0])
                        if subaccount_id is None:
                            continue
                        if subaccount_id not in allowed_subaccounts_map:
                            allowed_subaccounts_map[subaccount_id] = ""
            else:
                for row in selected_memberships:
                    subaccount_id = _coerce_int(row[3])
                    if subaccount_id is None:
                        continue
                    if subaccount_id not in allowed_subaccounts_map:
                        allowed_subaccounts_map[subaccount_id] = str(row[4] or "")

            allowed_subaccount_ids = tuple(sorted(allowed_subaccounts_map.keys()))
            allowed_subaccounts = tuple(
                {"id": sub_id, "name": allowed_subaccounts_map[sub_id]}
                for sub_id in allowed_subaccount_ids
            )
            primary_subaccount_id = allowed_subaccount_ids[0] if len(allowed_subaccount_ids) == 1 else None
            primary_subaccount_name = allowed_subaccounts_map.get(primary_subaccount_id or -1, "")

            membership_id: int | None
            if len(selected_memberships) == 1:
                membership_id = int(first_membership[0])
            else:
                membership_id = None

            if role_is_subaccount:
                access_scope = "subaccount"
                resolved_scope_type = "subaccount"
                resolved_subaccount_id = primary_subaccount_id
                resolved_subaccount_name = primary_subaccount_name
            else:
                access_scope = "agency"
                resolved_scope_type = scope_type or "agency"
                resolved_subaccount_id = _coerce_int(first_membership[3])
                resolved_subaccount_name = str(first_membership[4] or "")

            cur.execute("UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s", (user_id,))
        conn.commit()

    return AuthUser(
        user_id=user_id,
        email=user_email,
        role=normalized_role,
        scope_type=resolved_scope_type,
        membership_id=membership_id,
        subaccount_id=resolved_subaccount_id,
        subaccount_name=resolved_subaccount_name,
        access_scope=access_scope,
        allowed_subaccount_ids=allowed_subaccount_ids,
        allowed_subaccounts=allowed_subaccounts,
        primary_subaccount_id=primary_subaccount_id,
        membership_ids=membership_ids,
        is_env_admin=False,
    )


def create_access_token(
    email: str,
    role: str,
    *,
    user_id: int | None = None,
    scope_type: str | None = None,
    membership_id: int | None = None,
    subaccount_id: int | None = None,
    subaccount_name: str = "",
    access_scope: str | None = None,
    allowed_subaccount_ids: tuple[int, ...] = (),
    allowed_subaccounts: tuple[dict[str, object], ...] = (),
    primary_subaccount_id: int | None = None,
    membership_ids: tuple[int, ...] = (),
    is_env_admin: bool = False,
) -> str:
    settings = load_settings()
    payload = json.dumps(
        {
            "email": email,
            "role": role,
            "user_id": user_id,
            "scope_type": scope_type,
            "membership_id": membership_id,
            "subaccount_id": subaccount_id,
            "subaccount_name": subaccount_name,
            "access_scope": access_scope,
            "allowed_subaccount_ids": list(allowed_subaccount_ids),
            "allowed_subaccounts": list(allowed_subaccounts),
            "primary_subaccount_id": primary_subaccount_id,
            "membership_ids": list(membership_ids),
            "is_env_admin": is_env_admin,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    payload_encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")
    signature = _sign(payload_encoded, settings.app_auth_secret)
    return f"{payload_encoded}.{signature}"


def decode_access_token(token: str) -> AuthUser:
    settings = load_settings()
    try:
        payload_encoded, signature = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise AuthError("Invalid token format") from exc

    expected_signature = _sign(payload_encoded, settings.app_auth_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthError("Invalid token signature")

    try:
        raw = base64.urlsafe_b64decode(payload_encoded.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw)

        legacy_subaccount_id = _coerce_int(payload.get("subaccount_id"))
        allowed_subaccount_ids = _normalize_int_list(payload.get("allowed_subaccount_ids"))
        if not allowed_subaccount_ids and legacy_subaccount_id is not None:
            allowed_subaccount_ids = (legacy_subaccount_id,)

        allowed_subaccounts = _normalize_subaccount_objects(payload.get("allowed_subaccounts"))
        if not allowed_subaccounts and legacy_subaccount_id is not None:
            allowed_subaccounts = ({"id": legacy_subaccount_id, "name": str(payload.get("subaccount_name") or "")},)

        primary_subaccount_id = _coerce_int(payload.get("primary_subaccount_id"))
        if primary_subaccount_id is None and len(allowed_subaccount_ids) == 1:
            primary_subaccount_id = allowed_subaccount_ids[0]

        membership_ids = _normalize_int_list(payload.get("membership_ids"))
        membership_id = _coerce_int(payload.get("membership_id"))
        if not membership_ids and membership_id is not None:
            membership_ids = (membership_id,)

        access_scope = str(payload.get("access_scope") or "").strip() or None
        if access_scope is None:
            scope_type_raw = str(payload.get("scope_type") or "").strip()
            if scope_type_raw:
                access_scope = scope_type_raw
            elif allowed_subaccount_ids:
                access_scope = "subaccount"

        return AuthUser(
            email=str(payload["email"]),
            role=str(payload["role"]),
            user_id=_coerce_int(payload.get("user_id")),
            scope_type=str(payload["scope_type"]) if payload.get("scope_type") is not None else None,
            membership_id=membership_id,
            subaccount_id=legacy_subaccount_id,
            subaccount_name=str(payload.get("subaccount_name") or ""),
            access_scope=access_scope,
            allowed_subaccount_ids=allowed_subaccount_ids,
            allowed_subaccounts=allowed_subaccounts,
            primary_subaccount_id=primary_subaccount_id,
            membership_ids=membership_ids,
            is_env_admin=bool(payload.get("is_env_admin", False)),
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid token payload") from exc
