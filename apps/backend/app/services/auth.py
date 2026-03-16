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


def authenticate_user_from_db(*, email: str, password: str, requested_role: str) -> AuthUser:
    normalized_email = email.strip().lower()
    normalized_role = normalize_role(requested_role)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, is_active
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

            if not is_active:
                raise AuthLoginError(status_code=403, message="User account is inactive", reason="user_inactive")
            if not verify_password(password, password_hash):
                raise AuthLoginError(status_code=401, message="Invalid email or password", reason="invalid_credentials")

            cur.execute(
                """
                SELECT id, scope_type, subaccount_id, subaccount_name
                FROM user_memberships
                WHERE user_id = %s AND role_key = %s AND status = 'active'
                ORDER BY id ASC
                """,
                (user_id, normalized_role),
            )
            memberships = cur.fetchall()
            if len(memberships) == 0:
                raise AuthLoginError(
                    status_code=403,
                    message="Rolul selectat nu este alocat utilizatorului",
                    reason="role_not_owned",
                )
            if len(memberships) > 1:
                raise AuthLoginError(
                    status_code=409,
                    message="Există mai multe accesuri active pentru acest rol și selecția de sub-account la login nu este încă implementată",
                    reason="ambiguous_membership",
                )

            membership = memberships[0]
            membership_id = int(membership[0])
            scope_type = str(membership[1])
            subaccount_id = int(membership[2]) if membership[2] is not None else None
            subaccount_name = str(membership[3] or "")

            cur.execute("UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s", (user_id,))
        conn.commit()

    return AuthUser(
        user_id=user_id,
        email=user_email,
        role=normalized_role,
        scope_type=scope_type,
        membership_id=membership_id,
        subaccount_id=subaccount_id,
        subaccount_name=subaccount_name,
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
        return AuthUser(
            email=str(payload["email"]),
            role=str(payload["role"]),
            user_id=int(payload["user_id"]) if payload.get("user_id") is not None else None,
            scope_type=str(payload["scope_type"]) if payload.get("scope_type") is not None else None,
            membership_id=int(payload["membership_id"]) if payload.get("membership_id") is not None else None,
            subaccount_id=int(payload["subaccount_id"]) if payload.get("subaccount_id") is not None else None,
            subaccount_name=str(payload.get("subaccount_name") or ""),
            is_env_admin=bool(payload.get("is_env_admin", False)),
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid token payload") from exc
