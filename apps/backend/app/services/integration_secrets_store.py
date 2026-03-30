from __future__ import annotations

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from threading import Lock

from app.core.config import load_settings

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # noqa: BLE001
    Fernet = None
    InvalidToken = Exception

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


@dataclass(frozen=True)
class IntegrationSecretValue:
    provider: str
    secret_key: str
    scope: str
    value: str
    updated_at: datetime | None


class IntegrationSecretsStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(1, hashtext(%s))", ("ensure_schema_" + self.__class__.__name__,))
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS integration_secrets (
                            provider TEXT NOT NULL,
                            secret_key TEXT NOT NULL,
                            scope TEXT NOT NULL DEFAULT 'agency_default',
                            encrypted_value TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            PRIMARY KEY(provider, secret_key, scope)
                        )
                        """
                    )
                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_integration_secrets_provider_scope ON integration_secrets(provider, scope)"
                    )
                conn.commit()
            self._schema_initialized = True

    def _cipher(self):
        if Fernet is None:
            raise RuntimeError("cryptography is required for integration secret encryption")
        settings = load_settings()
        seed = (
            settings.integration_secret_encryption_key
            or settings.app_auth_secret
        ).encode("utf-8")
        fernet_key = urlsafe_b64encode(sha256(seed).digest())
        return Fernet(fernet_key)

    def encrypt_secret(self, value: str) -> str:
        return self._cipher().encrypt(str(value).encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, value: str) -> str:
        try:
            return self._cipher().decrypt(str(value).encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Failed to decrypt integration secret") from exc

    def upsert_secret(self, *, provider: str, secret_key: str, value: str, scope: str = "agency_default") -> None:
        self._ensure_schema()
        encrypted_value = self.encrypt_secret(value)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integration_secrets(provider, secret_key, scope, encrypted_value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(provider, secret_key, scope)
                    DO UPDATE SET encrypted_value = EXCLUDED.encrypted_value, updated_at = NOW()
                    """,
                    (str(provider), str(secret_key), str(scope), encrypted_value),
                )
            conn.commit()

    def get_secret(self, *, provider: str, secret_key: str, scope: str = "agency_default") -> IntegrationSecretValue | None:
        self._ensure_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, secret_key, scope, encrypted_value, updated_at
                    FROM integration_secrets
                    WHERE provider = %s AND secret_key = %s AND scope = %s
                    LIMIT 1
                    """,
                    (str(provider), str(secret_key), str(scope)),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return IntegrationSecretValue(
            provider=str(row[0]),
            secret_key=str(row[1]),
            scope=str(row[2]),
            value=self.decrypt_secret(str(row[3])),
            updated_at=row[4] if isinstance(row[4], datetime) else None,
        )


    def delete_secret(self, *, provider: str, secret_key: str, scope: str = "agency_default") -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM integration_secrets WHERE provider = %s AND secret_key = %s AND scope = %s",
                    (str(provider), str(secret_key), str(scope)),
                )
            conn.commit()


integration_secrets_store = IntegrationSecretsStore()


# ---------------------------------------------------------------------------
# HMAC-based OAuth state: no storage needed, works across restarts/instances
# ---------------------------------------------------------------------------
import hmac as _hmac
import logging as _logging
import time as _time

_oauth_state_logger = _logging.getLogger("oauth_state")

_OAUTH_STATE_MAX_AGE_SECONDS = 600  # 10 minutes


def _oauth_hmac_key() -> bytes:
    settings = load_settings()
    return str(settings.app_auth_secret).encode("utf-8")


def generate_oauth_state(provider: str) -> str:
    """Create an HMAC-signed OAuth state token: {provider}.{timestamp}.{random}.{signature}"""
    import secrets as _secrets
    timestamp = str(int(_time.time()))
    nonce = _secrets.token_urlsafe(18)
    message = f"{provider}.{timestamp}.{nonce}"
    sig = _hmac.new(_oauth_hmac_key(), message.encode("utf-8"), "sha256").hexdigest()[:32]
    state = f"{message}.{sig}"
    _oauth_state_logger.info("oauth_state_generated provider=%s state_len=%d state_prefix=%s", provider, len(state), state[:30])
    return state


def verify_oauth_state(provider: str, state: str) -> tuple[bool, str]:
    """Verify an HMAC-signed OAuth state token. Returns (valid, reason)."""
    raw = str(state)
    _oauth_state_logger.info(
        "oauth_state_verify_start provider=%s state_len=%d state_repr=%s",
        provider, len(raw), repr(raw[:80]),
    )
    parts = raw.split(".")
    if len(parts) != 4:
        reason = f"invalid_format: expected 4 dot-separated parts, got {len(parts)}"
        _oauth_state_logger.warning("oauth_state_fail provider=%s reason=%s", provider, reason)
        return False, reason
    state_provider, timestamp_str, nonce, received_sig = parts
    if state_provider != provider:
        reason = f"provider_mismatch: expected={provider} got={state_provider}"
        _oauth_state_logger.warning("oauth_state_fail provider=%s reason=%s", provider, reason)
        return False, reason
    try:
        ts = int(timestamp_str)
    except ValueError:
        reason = f"bad_timestamp: {timestamp_str!r}"
        _oauth_state_logger.warning("oauth_state_fail provider=%s reason=%s", provider, reason)
        return False, reason
    age = int(_time.time()) - ts
    if age < 0 or age > _OAUTH_STATE_MAX_AGE_SECONDS:
        reason = f"expired: age={age}s max={_OAUTH_STATE_MAX_AGE_SECONDS}s"
        _oauth_state_logger.warning("oauth_state_fail provider=%s reason=%s", provider, reason)
        return False, reason
    message = f"{state_provider}.{timestamp_str}.{nonce}"
    expected_sig = _hmac.new(_oauth_hmac_key(), message.encode("utf-8"), "sha256").hexdigest()[:32]
    valid = _hmac.compare_digest(received_sig, expected_sig)
    if not valid:
        reason = f"signature_mismatch: received={received_sig[:8]}... expected={expected_sig[:8]}..."
        _oauth_state_logger.warning("oauth_state_fail provider=%s reason=%s", provider, reason)
        return False, reason
    _oauth_state_logger.info("oauth_state_verify_ok provider=%s age=%ds", provider, age)
    return True, "ok"


# Keep old functions as no-ops for backward compatibility during rollout
def persist_oauth_state(provider: str, state: str) -> bool:
    return True

def check_oauth_state(provider: str, state: str) -> bool:
    valid, _ = verify_oauth_state(provider, state)
    return valid

def delete_oauth_state(provider: str, state: str) -> None:
    pass
