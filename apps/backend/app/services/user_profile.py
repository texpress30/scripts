from __future__ import annotations

from app.core.config import load_settings
from app.services.auth import hash_password

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class UserProfileService:
    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _connect_or_raise(self):
        return self._connect()

    def initialize_schema(self) -> None:
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        first_name TEXT NOT NULL DEFAULT '',
                        last_name TEXT NOT NULL DEFAULT '',
                        phone TEXT NOT NULL DEFAULT '',
                        extension TEXT NOT NULL DEFAULT '',
                        platform_language TEXT NOT NULL DEFAULT 'ro',
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def _ensure_user(self, *, email: str) -> None:
        settings = load_settings()
        default_hash = hash_password(settings.app_login_password)
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, first_name, last_name, phone, extension, platform_language, password_hash)
                    VALUES (%s, '', '', '', '', 'ro', %s)
                    ON CONFLICT(email) DO NOTHING
                    """,
                    (email, default_hash),
                )
            conn.commit()

    def get_profile(self, *, email: str) -> dict[str, str]:
        self._ensure_user(email=email)
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT email, first_name, last_name, phone, extension, platform_language
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError("User profile not found")
        return {
            "email": str(row[0]),
            "first_name": str(row[1]),
            "last_name": str(row[2]),
            "phone": str(row[3]),
            "extension": str(row[4]),
            "platform_language": str(row[5]),
        }

    def update_profile(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        extension: str,
        platform_language: str,
    ) -> dict[str, str]:
        self._ensure_user(email=email)
        normalized_language = platform_language if platform_language in {"ro", "en-US"} else "ro"
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name = %s,
                        last_name = %s,
                        phone = %s,
                        extension = %s,
                        platform_language = %s,
                        updated_at = NOW()
                    WHERE email = %s
                    """,
                    (first_name, last_name, phone, extension, normalized_language, email),
                )
            conn.commit()
        return self.get_profile(email=email)

    def update_password(self, *, email: str, current_password: str, password: str) -> None:
        self._ensure_user(email=email)
        current_hash = hash_password(current_password)
        new_hash = hash_password(password)
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                if row is None or str(row[0]) != current_hash:
                    raise ValueError("Current password is invalid")
                cur.execute(
                    "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE email = %s",
                    (new_hash, email),
                )
            conn.commit()


user_profile_service = UserProfileService()
