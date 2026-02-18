from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from app.core.config import load_settings


@dataclass(frozen=True)
class AuthUser:
    email: str
    role: str


class AuthError(RuntimeError):
    pass


def _sign(payload: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def validate_login_credentials(email: str, password: str) -> bool:
    settings = load_settings()
    return email.strip().lower() == settings.app_login_email.strip().lower() and password == settings.app_login_password


def create_access_token(email: str, role: str) -> str:
    settings = load_settings()
    payload = json.dumps({"email": email, "role": role}, separators=(",", ":"), sort_keys=True)
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
        return AuthUser(email=payload["email"], role=payload["role"])
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid token payload") from exc
