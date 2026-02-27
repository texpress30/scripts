from __future__ import annotations

import hashlib

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


def _hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TeamMembersService:
    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for team member persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS team_members (
                        id BIGSERIAL PRIMARY KEY,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        phone TEXT NOT NULL DEFAULT '',
                        extension TEXT NOT NULL DEFAULT '',
                        user_type TEXT NOT NULL DEFAULT 'agency',
                        user_role TEXT NOT NULL DEFAULT 'member',
                        location TEXT NOT NULL DEFAULT 'România',
                        subaccount TEXT NOT NULL DEFAULT 'Toate',
                        password_hash TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def list_members(
        self,
        *,
        search: str,
        user_type: str,
        user_role: str,
        subaccount: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        clauses: list[str] = []
        values: list[object] = []
        if search.strip():
            token = f"%{search.strip().lower()}%"
            clauses.append(
                "(LOWER(first_name || ' ' || last_name) LIKE %s OR LOWER(email) LIKE %s OR LOWER(phone) LIKE %s OR CAST(id AS TEXT) LIKE %s)"
            )
            values.extend([token, token, token, token])
        if user_type.strip():
            clauses.append("user_type = %s")
            values.append(user_type.strip())
        if user_role.strip():
            clauses.append("user_role = %s")
            values.append(user_role.strip())
        if subaccount.strip():
            clauses.append("subaccount = %s")
            values.append(subaccount.strip())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM team_members {where_sql}", tuple(values))
                total = int(cur.fetchone()[0])

                cur.execute(
                    f"""
                    SELECT id, first_name, last_name, email, phone, extension, user_type, user_role, location, subaccount
                    FROM team_members
                    {where_sql}
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(values + [page_size, offset]),
                )
                rows = cur.fetchall()

        items: list[dict[str, object]] = []
        for row in rows:
            items.append(
                {
                    "id": int(row[0]),
                    "first_name": str(row[1]),
                    "last_name": str(row[2]),
                    "email": str(row[3]),
                    "phone": str(row[4]),
                    "extension": str(row[5]),
                    "user_type": str(row[6]),
                    "user_role": str(row[7]),
                    "location": str(row[8]),
                    "subaccount": str(row[9]),
                }
            )
        return items, total

    def create_member(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        extension: str,
        user_type: str,
        user_role: str,
        location: str,
        subaccount: str,
        password: str | None,
    ) -> dict[str, object]:
        settings = load_settings()
        normalized_email = email.strip().lower()
        password_hash = _hash_password(password.strip()) if password and password.strip() else _hash_password(settings.app_login_password)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO team_members (
                        first_name, last_name, email, phone, extension, user_type, user_role, location, subaccount, password_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, first_name, last_name, email, phone, extension, user_type, user_role, location, subaccount
                    """,
                    (
                        first_name.strip(),
                        last_name.strip(),
                        normalized_email,
                        phone.strip(),
                        extension.strip(),
                        user_type.strip() or "agency",
                        user_role.strip() or "member",
                        location.strip() or "România",
                        subaccount.strip() or "Toate",
                        password_hash,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        return {
            "id": int(row[0]),
            "first_name": str(row[1]),
            "last_name": str(row[2]),
            "email": str(row[3]),
            "phone": str(row[4]),
            "extension": str(row[5]),
            "user_type": str(row[6]),
            "user_role": str(row[7]),
            "location": str(row[8]),
            "subaccount": str(row[9]),
        }


team_members_service = TeamMembersService()
