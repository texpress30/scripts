from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


PASSWORD_RESET_TOKEN_TYPE = "password_reset"


@dataclass(frozen=True)
class PasswordResetTokenRecord:
    id: int
    user_id: int
    email: str
    token_type: str
    expires_at: datetime
    consumed_at: datetime | None
    metadata_json: str


class AuthEmailTokenError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "invalid_token", status_code: int = 400):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code


class AuthEmailTokensService:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for email token persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS auth_email_tokens (
                            id BIGSERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            token_type TEXT NOT NULL,
                            token_hash TEXT NOT NULL,
                            email TEXT NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            consumed_at TIMESTAMPTZ NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            metadata_json TEXT NOT NULL DEFAULT '{}'
                        )
                        """
                    )
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_email_tokens_user_type ON auth_email_tokens(user_id, token_type)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_email_tokens_hash_type ON auth_email_tokens(token_hash, token_type)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_email_tokens_active_expiry ON auth_email_tokens(token_type, consumed_at, expires_at)")
                conn.commit()
            self._schema_initialized = True

    def _hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def _read_token(self, *, token_hash: str, token_type: str) -> PasswordResetTokenRecord | None:
        self.initialize_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, email, token_type, expires_at, consumed_at, metadata_json
                    FROM auth_email_tokens
                    WHERE token_hash = %s AND token_type = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (token_hash, token_type),
                )
                row = cur.fetchone()
        if row is None:
            return None
        expires_at = row[4]
        consumed_at = row[5]
        return PasswordResetTokenRecord(
            id=int(row[0]),
            user_id=int(row[1]),
            email=str(row[2]),
            token_type=str(row[3]),
            expires_at=expires_at if isinstance(expires_at, datetime) else datetime.now(tz=timezone.utc),
            consumed_at=consumed_at if isinstance(consumed_at, datetime) else None,
            metadata_json=str(row[6] or "{}"),
        )

    def _assert_token_usable(self, record: PasswordResetTokenRecord | None) -> PasswordResetTokenRecord:
        if record is None:
            raise AuthEmailTokenError("Token invalid", reason="invalid_token", status_code=400)
        now = datetime.now(tz=timezone.utc)
        if record.consumed_at is not None:
            raise AuthEmailTokenError("Token deja folosit", reason="token_consumed", status_code=400)
        if record.expires_at <= now:
            raise AuthEmailTokenError("Token expirat", reason="token_expired", status_code=400)
        return record

    def invalidate_active_tokens(self, *, user_id: int, token_type: str, exclude_token_id: int | None = None) -> None:
        self.initialize_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                if exclude_token_id is None:
                    cur.execute(
                        """
                        UPDATE auth_email_tokens
                        SET consumed_at = NOW()
                        WHERE user_id = %s
                          AND token_type = %s
                          AND consumed_at IS NULL
                          AND expires_at > NOW()
                        """,
                        (int(user_id), str(token_type)),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE auth_email_tokens
                        SET consumed_at = NOW()
                        WHERE user_id = %s
                          AND token_type = %s
                          AND consumed_at IS NULL
                          AND expires_at > NOW()
                          AND id <> %s
                        """,
                        (int(user_id), str(token_type), int(exclude_token_id)),
                    )
            conn.commit()

    def create_password_reset_token(self, *, user_id: int, email: str, expires_in_minutes: int = 60) -> tuple[str, datetime]:
        self.initialize_schema()
        self.invalidate_active_tokens(user_id=user_id, token_type=PASSWORD_RESET_TOKEN_TYPE)

        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=max(1, int(expires_in_minutes)))

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_email_tokens(user_id, token_type, token_hash, email, expires_at, metadata_json)
                    VALUES (%s, %s, %s, %s, %s, '{}')
                    """,
                    (int(user_id), PASSWORD_RESET_TOKEN_TYPE, token_hash, str(email).strip().lower(), expires_at),
                )
            conn.commit()

        return raw_token, expires_at

    def consume_password_reset_token(self, *, raw_token: str) -> PasswordResetTokenRecord:
        token_hash = self._hash_token(str(raw_token).strip())
        record = self._assert_token_usable(self._read_token(token_hash=token_hash, token_type=PASSWORD_RESET_TOKEN_TYPE))

        self.initialize_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE auth_email_tokens
                    SET consumed_at = NOW()
                    WHERE id = %s AND consumed_at IS NULL
                    """,
                    (record.id,),
                )
                if int(cur.rowcount or 0) != 1:
                    raise AuthEmailTokenError("Token invalid", reason="invalid_token", status_code=400)
            conn.commit()

        return PasswordResetTokenRecord(
            id=record.id,
            user_id=record.user_id,
            email=record.email,
            token_type=record.token_type,
            expires_at=record.expires_at,
            consumed_at=datetime.now(tz=timezone.utc),
            metadata_json=record.metadata_json,
        )

    def debug_get_token_hash_for_raw(self, *, raw_token: str) -> str:
        return self._hash_token(raw_token)


auth_email_tokens_service = AuthEmailTokensService()
