from __future__ import annotations

from dataclasses import dataclass

from app.core.config import load_settings
from app.services.auth import hash_password
from app.services.client_registry import client_registry_service

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

CANONICAL_ROLE_KEYS: tuple[str, ...] = (
    "agency_admin",
    "agency_member",
    "agency_viewer",
    "subaccount_admin",
    "subaccount_user",
    "subaccount_viewer",
)

_UI_TO_CANONICAL_ROLE_MAP: dict[tuple[str, str], str] = {
    ("agency", "admin"): "agency_admin",
    ("agency", "member"): "agency_member",
    ("agency", "viewer"): "agency_viewer",
    ("client", "admin"): "subaccount_admin",
    ("client", "member"): "subaccount_user",
    ("client", "viewer"): "subaccount_viewer",
}

_CANONICAL_TO_UI_ROLE_MAP: dict[str, tuple[str, str]] = {
    "agency_admin": ("agency", "admin"),
    "agency_member": ("agency", "member"),
    "agency_viewer": ("agency", "viewer"),
    "subaccount_admin": ("client", "admin"),
    "subaccount_user": ("client", "member"),
    "subaccount_viewer": ("client", "viewer"),
}


@dataclass(frozen=True)
class SubaccountRef:
    id: int
    name: str


class TeamMembersService:
    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for team member persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                # identity table reused by user_profile and future auth flow
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
                        password_hash TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_reset_password BOOLEAN NOT NULL DEFAULT FALSE")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ NULL")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT NOT NULL DEFAULT ''")

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_memberships (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role_key TEXT NOT NULL,
                        scope_type TEXT NOT NULL,
                        subaccount_id INTEGER NULL,
                        subaccount_name TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT user_memberships_scope_type_check CHECK (scope_type IN ('agency', 'subaccount')),
                        CONSTRAINT user_memberships_role_key_check CHECK (role_key IN ('agency_admin','agency_member','agency_viewer','subaccount_admin','subaccount_user','subaccount_viewer')),
                        CONSTRAINT user_memberships_scope_subaccount_guard CHECK (
                            (scope_type = 'agency' AND subaccount_id IS NULL)
                            OR
                            (scope_type = 'subaccount' AND subaccount_id IS NOT NULL)
                        )
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_memberships_unique_scope_role
                    ON user_memberships (user_id, role_key, scope_type, COALESCE(subaccount_id, -1))
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_memberships_scope_type ON user_memberships(scope_type)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_memberships_subaccount_id ON user_memberships(subaccount_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_memberships_role_key ON user_memberships(role_key)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_memberships_status ON user_memberships(status)")

                # transitional/legacy storage retained for backward compatibility during migration.
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

    def map_payload_role_to_canonical(self, *, user_type: str, user_role: str) -> str:
        key = (user_type.strip().lower(), user_role.strip().lower())
        role_key = _UI_TO_CANONICAL_ROLE_MAP.get(key)
        if role_key is None:
            raise ValueError("Rol invalid pentru tipul de utilizator selectat")
        return role_key

    def map_canonical_to_payload_role(self, *, role_key: str) -> tuple[str, str]:
        mapped = _CANONICAL_TO_UI_ROLE_MAP.get(role_key.strip().lower())
        if mapped is None:
            raise ValueError(f"Rol canonic necunoscut: {role_key}")
        return mapped

    def _resolve_subaccount_ref(self, *, subaccount: str) -> SubaccountRef:
        candidate = subaccount.strip()
        if candidate == "" or candidate.lower() == "toate":
            raise ValueError("Pentru utilizatorii de tip client trebuie selectat un sub-account valid")

        clients = client_registry_service.list_clients()
        if not clients:
            raise ValueError("Nu există sub-account-uri disponibile pentru asociere")

        by_id = {str(int(item["id"])): item for item in clients if item.get("id") is not None}
        by_display_id = {str(int(item["display_id"])): item for item in clients if item.get("display_id") is not None}
        by_name = {str(item.get("name", "")).strip().lower(): item for item in clients}

        record = by_id.get(candidate) or by_display_id.get(candidate) or by_name.get(candidate.lower())
        if record is None:
            raise ValueError("Sub-account invalid sau inexistent")

        return SubaccountRef(id=int(record["id"]), name=str(record.get("name") or ""))

    def _upsert_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        extension: str,
        avatar_url: str,
        password: str | None,
    ) -> int:
        settings = load_settings()
        password_hash = hash_password(password.strip()) if password and password.strip() else hash_password(settings.app_login_password)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (
                        email, first_name, last_name, phone, extension, avatar_url, platform_language,
                        password_hash, is_active, must_reset_password
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'ro', %s, TRUE, FALSE)
                    ON CONFLICT(email) DO UPDATE
                    SET first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        phone = EXCLUDED.phone,
                        extension = EXCLUDED.extension,
                        avatar_url = EXCLUDED.avatar_url,
                        password_hash = COALESCE(EXCLUDED.password_hash, users.password_hash),
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        email,
                        first_name,
                        last_name,
                        phone,
                        extension,
                        avatar_url,
                        password_hash,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Nu am putut salva utilizatorul")
        return int(row[0])

    def _upsert_membership(
        self,
        *,
        user_id: int,
        role_key: str,
        scope_type: str,
        subaccount_id: int | None,
        subaccount_name: str,
    ) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM user_memberships
                    WHERE user_id = %s
                      AND role_key = %s
                      AND scope_type = %s
                      AND COALESCE(subaccount_id, -1) = COALESCE(%s, -1)
                    LIMIT 1
                    """,
                    (user_id, role_key, scope_type, subaccount_id),
                )
                found = cur.fetchone()
                if found is not None:
                    membership_id = int(found[0])
                    cur.execute(
                        """
                        UPDATE user_memberships
                        SET subaccount_name = %s,
                            status = 'active',
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (subaccount_name, membership_id),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO user_memberships (
                            user_id, role_key, scope_type, subaccount_id, subaccount_name, status
                        )
                        VALUES (%s, %s, %s, %s, %s, 'active')
                        RETURNING id
                        """,
                        (user_id, role_key, scope_type, subaccount_id, subaccount_name),
                    )
                    inserted = cur.fetchone()
                    if inserted is None:
                        raise RuntimeError("Nu am putut salva membership-ul utilizatorului")
                    membership_id = int(inserted[0])
            conn.commit()
        return membership_id

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
        normalized_email = email.strip().lower()
        normalized_first_name = first_name.strip()
        normalized_last_name = last_name.strip()
        normalized_phone = phone.strip()
        normalized_extension = extension.strip()
        normalized_location = (location or "").strip() or "România"

        if normalized_email == "":
            raise ValueError("Email este obligatoriu")
        if normalized_first_name == "":
            raise ValueError("Prenumele este obligatoriu")
        if normalized_last_name == "":
            raise ValueError("Numele este obligatoriu")

        role_key = self.map_payload_role_to_canonical(user_type=user_type, user_role=user_role)

        if role_key.startswith("agency_"):
            scope_type = "agency"
            subaccount_id = None
            subaccount_name = "Toate"
        else:
            scope_type = "subaccount"
            resolved = self._resolve_subaccount_ref(subaccount=subaccount)
            subaccount_id = resolved.id
            subaccount_name = resolved.name

        user_id = self._upsert_user(
            first_name=normalized_first_name,
            last_name=normalized_last_name,
            email=normalized_email,
            phone=normalized_phone,
            extension=normalized_extension,
            avatar_url="",
            password=password,
        )
        membership_id = self._upsert_membership(
            user_id=user_id,
            role_key=role_key,
            scope_type=scope_type,
            subaccount_id=subaccount_id,
            subaccount_name=subaccount_name,
        )

        mapped_user_type, mapped_user_role = self.map_canonical_to_payload_role(role_key=role_key)
        return {
            "id": membership_id,
            "first_name": normalized_first_name,
            "last_name": normalized_last_name,
            "email": normalized_email,
            "phone": normalized_phone,
            "extension": normalized_extension,
            "user_type": mapped_user_type,
            "user_role": mapped_user_role,
            "location": normalized_location,
            "subaccount": subaccount_name,
        }

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
        clauses: list[str] = ["um.status = 'active'"]
        values: list[object] = []

        if search.strip():
            token = f"%{search.strip().lower()}%"
            clauses.append(
                "(LOWER(u.first_name || ' ' || u.last_name) LIKE %s OR LOWER(u.email) LIKE %s OR LOWER(u.phone) LIKE %s OR CAST(um.id AS TEXT) LIKE %s)"
            )
            values.extend([token, token, token, token])

        if user_type.strip() and user_role.strip():
            role_key = self.map_payload_role_to_canonical(user_type=user_type, user_role=user_role)
            clauses.append("um.role_key = %s")
            values.append(role_key)
        elif user_type.strip():
            normalized_type = user_type.strip().lower()
            if normalized_type == "agency":
                clauses.append("um.scope_type = 'agency'")
            elif normalized_type == "client":
                clauses.append("um.scope_type = 'subaccount'")
            else:
                raise ValueError("Tip utilizator invalid")
        elif user_role.strip():
            normalized_role = user_role.strip().lower()
            role_keys = [
                role_key
                for (mapped_type, mapped_role), role_key in _UI_TO_CANONICAL_ROLE_MAP.items()
                if mapped_role == normalized_role
            ]
            if not role_keys:
                raise ValueError("Rol invalid")
            clauses.append("um.role_key = ANY(%s)")
            values.append(role_keys)

        if subaccount.strip():
            clauses.append("(LOWER(um.subaccount_name) = LOWER(%s) OR CAST(COALESCE(um.subaccount_id, -1) AS TEXT) = %s)")
            values.extend([subaccount.strip(), subaccount.strip()])

        where_sql = f"WHERE {' AND '.join(clauses)}"
        offset = (page - 1) * page_size

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM user_memberships um
                    JOIN users u ON u.id = um.user_id
                    {where_sql}
                    """,
                    tuple(values),
                )
                total = int(cur.fetchone()[0])

                cur.execute(
                    f"""
                    SELECT um.id, um.user_id, u.first_name, u.last_name, u.email, u.phone, u.extension, um.role_key, um.subaccount_name
                    FROM user_memberships um
                    JOIN users u ON u.id = um.user_id
                    {where_sql}
                    ORDER BY um.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(values + [page_size, offset]),
                )
                rows = cur.fetchall()

        items: list[dict[str, object]] = []
        for row in rows:
            role_key = str(row[7])
            mapped_user_type, mapped_user_role = self.map_canonical_to_payload_role(role_key=role_key)
            membership_id = int(row[0])
            items.append(
                {
                    "id": membership_id,
                    "membership_id": membership_id,
                    "user_id": int(row[1]),
                    "first_name": str(row[2]),
                    "last_name": str(row[3]),
                    "email": str(row[4]),
                    "phone": str(row[5]),
                    "extension": str(row[6]),
                    "user_type": mapped_user_type,
                    "user_role": mapped_user_role,
                    "location": "România",
                    "subaccount": str(row[8] or "Toate"),
                }
            )
        return items, total


    def _resolve_subaccount_by_id(self, *, subaccount_id: int) -> SubaccountRef:
        for item in client_registry_service.list_clients():
            try:
                item_id = int(item.get("id"))
            except Exception:  # noqa: BLE001
                continue
            if item_id == int(subaccount_id):
                name = str(item.get("name") or "").strip()
                if name == "":
                    name = f"Sub-account {item_id}"
                return SubaccountRef(id=item_id, name=name)
        raise ValueError("Sub-account inexistent")

    def _role_label(self, *, role_key: str) -> str:
        labels = {
            "agency_admin": "Agency Admin",
            "agency_member": "Agency Member",
            "agency_viewer": "Agency Viewer",
            "subaccount_admin": "Subaccount Admin",
            "subaccount_user": "Subaccount User",
            "subaccount_viewer": "Subaccount Viewer",
        }
        return labels.get(role_key, role_key)

    def list_subaccount_members(
        self,
        *,
        subaccount_id: int,
        search: str,
        user_role: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        subaccount_ref = self._resolve_subaccount_by_id(subaccount_id=subaccount_id)
        clauses_direct: list[str] = [
            "um.status = 'active'",
            "um.scope_type = 'subaccount'",
            "um.subaccount_id = %s",
        ]
        values_direct: list[object] = [int(subaccount_id)]

        clauses_agency: list[str] = [
            "um.status = 'active'",
            "um.scope_type = 'agency'",
        ]
        values_agency: list[object] = []

        if search.strip():
            token = f"%{search.strip().lower()}%"
            matcher = "(LOWER(u.first_name || ' ' || u.last_name) LIKE %s OR LOWER(u.email) LIKE %s OR LOWER(u.phone) LIKE %s)"
            clauses_direct.append(matcher)
            clauses_agency.append(matcher)
            values_direct.extend([token, token, token])
            values_agency.extend([token, token, token])

        if user_role.strip():
            role_candidate = user_role.strip().lower()
            if role_candidate in {"admin", "member", "viewer"}:
                role_candidate = {
                    "admin": "subaccount_admin",
                    "member": "subaccount_user",
                    "viewer": "subaccount_viewer",
                }[role_candidate]
            if role_candidate not in CANONICAL_ROLE_KEYS:
                raise ValueError("Rol invalid")
            if role_candidate.startswith("agency_"):
                clauses_agency.append("um.role_key = %s")
                values_agency.append(role_candidate)
                clauses_direct.append("1=0")
            else:
                clauses_direct.append("um.role_key = %s")
                values_direct.append(role_candidate)
                clauses_agency.append("1=0")

        where_direct = f"WHERE {' AND '.join(clauses_direct)}"
        where_agency = f"WHERE {' AND '.join(clauses_agency)}"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT um.id
                        FROM user_memberships um
                        JOIN users u ON u.id = um.user_id
                        {where_direct}
                        UNION ALL
                        SELECT um.id
                        FROM user_memberships um
                        JOIN users u ON u.id = um.user_id
                        {where_agency}
                    ) t
                    """,
                    tuple(values_direct + values_agency),
                )
                total = int(cur.fetchone()[0])

                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    SELECT * FROM (
                        SELECT
                            um.id AS membership_id,
                            u.id AS user_id,
                            u.first_name,
                            u.last_name,
                            u.email,
                            u.phone,
                            u.extension,
                            um.role_key,
                            um.status,
                            'subaccount' AS source_scope,
                            FALSE AS is_inherited,
                            um.subaccount_name AS source_label
                        FROM user_memberships um
                        JOIN users u ON u.id = um.user_id
                        {where_direct}
                        UNION ALL
                        SELECT
                            um.id AS membership_id,
                            u.id AS user_id,
                            u.first_name,
                            u.last_name,
                            u.email,
                            u.phone,
                            u.extension,
                            um.role_key,
                            um.status,
                            'agency' AS source_scope,
                            TRUE AS is_inherited,
                            'Agency access' AS source_label
                        FROM user_memberships um
                        JOIN users u ON u.id = um.user_id
                        {where_agency}
                    ) combined
                    ORDER BY membership_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(values_direct + values_agency + [page_size, offset]),
                )
                rows = cur.fetchall()

        items: list[dict[str, object]] = []
        for row in rows:
            role_key = str(row[7])
            membership_id = int(row[0])
            user_id = int(row[1])
            items.append(
                {
                    "membership_id": membership_id,
                    "user_id": user_id,
                    "display_id": f"TM-{membership_id}",
                    "first_name": str(row[2]),
                    "last_name": str(row[3]),
                    "email": str(row[4]),
                    "phone": str(row[5]),
                    "extension": str(row[6]),
                    "role_key": role_key,
                    "role_label": self._role_label(role_key=role_key),
                    "source_scope": str(row[9]),
                    "source_label": str(row[11] or subaccount_ref.name),
                    "is_active": str(row[8]) == "active",
                    "is_inherited": bool(row[10]),
                }
            )
        return items, total

    def create_subaccount_member(
        self,
        *,
        subaccount_id: int,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        extension: str,
        user_role: str,
        password: str | None,
    ) -> dict[str, object]:
        normalized_email = email.strip().lower()
        normalized_first_name = first_name.strip()
        normalized_last_name = last_name.strip()
        normalized_phone = phone.strip()
        normalized_extension = extension.strip()

        if normalized_email == "":
            raise ValueError("Email este obligatoriu")
        if normalized_first_name == "":
            raise ValueError("Prenumele este obligatoriu")
        if normalized_last_name == "":
            raise ValueError("Numele este obligatoriu")

        role_key = user_role.strip().lower() or "subaccount_user"
        if role_key in {"admin", "member", "viewer"}:
            role_key = {
                "admin": "subaccount_admin",
                "member": "subaccount_user",
                "viewer": "subaccount_viewer",
            }[role_key]
        if role_key not in {"subaccount_admin", "subaccount_user", "subaccount_viewer"}:
            raise ValueError("Rol invalid pentru endpointul de sub-account")

        sub_ref = self._resolve_subaccount_by_id(subaccount_id=subaccount_id)

        user_id = self._upsert_user(
            first_name=normalized_first_name,
            last_name=normalized_last_name,
            email=normalized_email,
            phone=normalized_phone,
            extension=normalized_extension,
            avatar_url="",
            password=password,
        )
        membership_id = self._upsert_membership(
            user_id=user_id,
            role_key=role_key,
            scope_type="subaccount",
            subaccount_id=sub_ref.id,
            subaccount_name=sub_ref.name,
        )

        return {
            "membership_id": membership_id,
            "user_id": user_id,
            "display_id": f"TM-{membership_id}",
            "first_name": normalized_first_name,
            "last_name": normalized_last_name,
            "email": normalized_email,
            "phone": normalized_phone,
            "extension": normalized_extension,
            "role_key": role_key,
            "role_label": self._role_label(role_key=role_key),
            "source_scope": "subaccount",
            "source_label": sub_ref.name,
            "is_active": True,
            "is_inherited": False,
        }


    def get_membership_with_user(self, *, membership_id: int) -> dict[str, object] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT um.id, um.user_id, um.scope_type, um.subaccount_id, um.status, u.email, u.is_active
                    FROM user_memberships um
                    JOIN users u ON u.id = um.user_id
                    WHERE um.id = %s
                    LIMIT 1
                    """,
                    (int(membership_id),),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "membership_id": int(row[0]),
            "user_id": int(row[1]),
            "scope_type": str(row[2]),
            "subaccount_id": int(row[3]) if row[3] is not None else None,
            "status": str(row[4]),
            "email": str(row[5] or "").strip().lower(),
            "is_active": bool(row[6]),
        }



team_members_service = TeamMembersService()
