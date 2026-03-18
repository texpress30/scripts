from __future__ import annotations

from dataclasses import dataclass

from app.core.config import load_settings
from app.services.auth import AuthUser, hash_password
from app.services.client_registry import client_registry_service
from app.services.rbac import normalize_role

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


@dataclass(frozen=True)
class ModuleCatalogItem:
    key: str
    label: str
    order: int
    scope: str = "subaccount"


SUBACCOUNT_MODULE_CATALOG: tuple[ModuleCatalogItem, ...] = (
    ModuleCatalogItem(key="dashboard", label="Dashboard", order=1),
    ModuleCatalogItem(key="campaigns", label="Campaigns", order=2),
    ModuleCatalogItem(key="rules", label="Rules", order=3),
    ModuleCatalogItem(key="creative", label="Creative", order=4),
    ModuleCatalogItem(key="recommendations", label="Recommendations", order=5),
)

SUBACCOUNT_MODULE_KEY_SET: set[str] = {item.key for item in SUBACCOUNT_MODULE_CATALOG}
ALLOWED_MEMBERSHIP_STATUSES: set[str] = {"active", "inactive"}


class TeamMembersService:
    def _normalize_membership_status(self, value: object) -> str:
        candidate = str(value or "").strip().lower()
        if candidate not in ALLOWED_MEMBERSHIP_STATUSES:
            return "active"
        return candidate

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return None

    def _safe_map_member_role(self, *, role_key: object, scope_type: object) -> tuple[str, str]:
        normalized_role_key = str(role_key or "").strip().lower()
        try:
            return self.map_canonical_to_payload_role(role_key=normalized_role_key)
        except ValueError:
            normalized_scope = str(scope_type or "").strip().lower()
            if normalized_scope == "subaccount":
                return ("client", "member")
            return ("agency", "member")

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for team member persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        settings = load_settings()
        default_hash = hash_password(settings.app_login_password)
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

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS membership_module_permissions (
                        id BIGSERIAL PRIMARY KEY,
                        membership_id BIGINT NOT NULL REFERENCES user_memberships(id) ON DELETE CASCADE,
                        module_key TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_module_permissions_unique
                    ON membership_module_permissions (membership_id, module_key)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_membership_module_permissions_membership_id
                    ON membership_module_permissions (membership_id)
                    """
                )

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

    def list_module_catalog(self, *, scope: str = "subaccount") -> list[dict[str, object]]:
        normalized_scope = str(scope or "").strip().lower()
        if normalized_scope != "subaccount":
            raise ValueError("Scope invalid pentru catalogul de module")
        return [
            {"key": item.key, "label": item.label, "order": item.order, "scope": item.scope}
            for item in SUBACCOUNT_MODULE_CATALOG
        ]

    def default_module_keys_for_role(self, *, role_key: str) -> list[str]:
        normalized_role = normalize_role(role_key)
        if normalized_role.startswith("subaccount_"):
            return [item.key for item in SUBACCOUNT_MODULE_CATALOG]
        return []

    def _normalize_subaccount_module_keys(self, module_keys: list[str] | tuple[str, ...] | None) -> list[str]:
        if module_keys is None:
            return []

        normalized: list[str] = []
        seen: set[str] = set()
        for module_key in module_keys:
            key = str(module_key or "").strip().lower()
            if key == "":
                continue
            if key in seen:
                continue
            if key not in SUBACCOUNT_MODULE_KEY_SET:
                raise ValueError(f"Modul invalid: {key}")
            seen.add(key)
            normalized.append(key)
        return normalized

    def _resolve_create_module_keys(
        self,
        *,
        scope_type: str,
        role_key: str,
        requested_module_keys: list[str] | None,
        subaccount_id: int | None,
        actor_user: AuthUser | None,
    ) -> list[str]:
        if scope_type != "subaccount":
            if requested_module_keys:
                raise ValueError("module_keys este permis doar pentru membership-uri de sub-account")
            return []

        normalized = self._normalize_subaccount_module_keys(requested_module_keys)
        if len(normalized) == 0:
            normalized = self.default_module_keys_for_role(role_key=role_key)

        if actor_user is not None:
            grantable = self.get_grantable_module_keys_for_actor(actor_user=actor_user, subaccount_id=int(subaccount_id or 0))
            if len(grantable) > 0:
                forbidden = [key for key in normalized if key not in grantable]
                if forbidden:
                    joined = ", ".join(forbidden)
                    raise ValueError(f"Nu poți acorda module în afara permisiunilor proprii: {joined}")
        return normalized

    def get_membership_module_keys(self, *, membership_id: int, role_key: str, scope_type: str) -> list[str]:
        normalized_scope = str(scope_type or "").strip().lower()
        if normalized_scope != "subaccount":
            return []

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT module_key
                    FROM membership_module_permissions
                    WHERE membership_id = %s
                    ORDER BY module_key ASC
                    """,
                    (int(membership_id),),
                )
                rows = cur.fetchall()

        try:
            stored = self._normalize_subaccount_module_keys([str(row[0]) for row in rows])
        except ValueError:
            return self.default_module_keys_for_role(role_key=role_key)
        if len(stored) == 0:
            return self.default_module_keys_for_role(role_key=role_key)
        return stored

    def set_membership_module_keys(self, *, membership_id: int, scope_type: str, module_keys: list[str]) -> None:
        if scope_type != "subaccount":
            if module_keys:
                raise ValueError("module_keys este permis doar pentru membership-uri de sub-account")
            return

        normalized = self._normalize_subaccount_module_keys(module_keys)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM membership_module_permissions WHERE membership_id = %s", (int(membership_id),))
                for module_key in normalized:
                    cur.execute(
                        """
                        INSERT INTO membership_module_permissions (membership_id, module_key)
                        VALUES (%s, %s)
                        ON CONFLICT (membership_id, module_key) DO NOTHING
                        """,
                        (int(membership_id), module_key),
                    )
            conn.commit()

    def _membership_module_keys_map(self, membership_rows: list[tuple[int, str, str]]) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for membership_id, role_key, scope_type in membership_rows:
            out[int(membership_id)] = self.get_membership_module_keys(
                membership_id=int(membership_id),
                role_key=str(role_key),
                scope_type=str(scope_type),
            )
        return out

    def get_grantable_module_keys_for_actor(self, *, actor_user: AuthUser, subaccount_id: int) -> set[str]:
        actor_role = normalize_role(actor_user.role)
        if not actor_role.startswith("subaccount_"):
            return set(SUBACCOUNT_MODULE_KEY_SET)

        if actor_user.user_id is None:
            return set()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, role_key, scope_type
                    FROM user_memberships
                    WHERE user_id = %s
                      AND role_key = %s
                      AND scope_type = 'subaccount'
                      AND subaccount_id = %s
                      AND status = 'active'
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (int(actor_user.user_id), actor_role, int(subaccount_id)),
                )
                row = cur.fetchone()

        if row is None:
            return set()

        module_keys = self.get_membership_module_keys(
            membership_id=int(row[0]),
            role_key=str(row[1]),
            scope_type=str(row[2]),
        )
        return set(module_keys)

    def get_subaccount_my_access(self, *, actor_user: AuthUser, subaccount_id: int) -> dict[str, object]:
        actor_role = normalize_role(actor_user.role)
        access_scope = str(actor_user.access_scope or "").strip().lower() or "agency"

        if not actor_role.startswith("subaccount_"):
            return {
                "subaccount_id": int(subaccount_id),
                "role": actor_role,
                "module_keys": [item.key for item in SUBACCOUNT_MODULE_CATALOG],
                "source_scope": "agency",
                "access_scope": access_scope,
                "unrestricted_modules": True,
            }

        if actor_user.user_id is None:
            return {
                "subaccount_id": int(subaccount_id),
                "role": actor_role,
                "module_keys": [item.key for item in SUBACCOUNT_MODULE_CATALOG],
                "source_scope": "legacy_fallback",
                "access_scope": "subaccount",
                "unrestricted_modules": False,
            }

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, role_key, scope_type
                    FROM user_memberships
                    WHERE user_id = %s
                      AND scope_type = 'subaccount'
                      AND subaccount_id = %s
                      AND status = 'active'
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (int(actor_user.user_id), int(subaccount_id)),
                )
                row = cur.fetchone()

        if row is None:
            raise PermissionError("Nu ai acces la acest sub-account")

        membership_id = int(row[0])
        membership_role = str(row[1] or actor_role).strip().lower() or actor_role
        scope_type = str(row[2] or "subaccount")
        module_keys = self.get_membership_module_keys(
            membership_id=membership_id,
            role_key=membership_role,
            scope_type=scope_type,
        )

        return {
            "subaccount_id": int(subaccount_id),
            "role": membership_role,
            "module_keys": module_keys,
            "source_scope": "subaccount",
            "access_scope": "subaccount",
            "unrestricted_modules": False,
        }

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
        module_keys: list[str] | None = None,
        actor_user: AuthUser | None = None,
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

        resolved_module_keys = self._resolve_create_module_keys(
            scope_type=scope_type,
            role_key=role_key,
            requested_module_keys=module_keys,
            subaccount_id=subaccount_id,
            actor_user=actor_user,
        )

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

        self.set_membership_module_keys(
            membership_id=membership_id,
            scope_type=scope_type,
            module_keys=resolved_module_keys,
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
            "module_keys": resolved_module_keys,
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
        clauses: list[str] = []
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

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
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
                    SELECT um.id, um.user_id, u.first_name, u.last_name, u.email, u.phone, u.extension, um.role_key, um.subaccount_name, um.scope_type, um.status
                    FROM user_memberships um
                    JOIN users u ON u.id = um.user_id
                    {where_sql}
                    ORDER BY um.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(values + [page_size, offset]),
                )
                rows = cur.fetchall()

        membership_module_map = self._membership_module_keys_map([
            (int(row[0]), str(row[7] or ""), str(row[9] or ""))
            for row in rows
            if self._safe_int(row[0]) is not None
        ])

        items: list[dict[str, object]] = []
        for row in rows:
            membership_id = self._safe_int(row[0])
            user_id = self._safe_int(row[1])
            if membership_id is None or user_id is None:
                continue

            mapped_user_type, mapped_user_role = self._safe_map_member_role(role_key=row[7], scope_type=row[9])
            items.append(
                {
                    "id": membership_id,
                    "membership_id": membership_id,
                    "user_id": user_id,
                    "first_name": str(row[2] or ""),
                    "last_name": str(row[3] or ""),
                    "email": str(row[4] or ""),
                    "phone": str(row[5] or ""),
                    "extension": str(row[6] or ""),
                    "user_type": mapped_user_type,
                    "user_role": mapped_user_role,
                    "location": "România",
                    "subaccount": str(row[8] or "Toate"),
                    "module_keys": membership_module_map.get(membership_id, []),
                    "membership_status": self._normalize_membership_status(row[10] if len(row) > 10 else "active"),
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
            "um.scope_type = 'subaccount'",
            "um.subaccount_id = %s",
        ]
        values_direct: list[object] = [int(subaccount_id)]

        clauses_agency: list[str] = [
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

        membership_module_map = self._membership_module_keys_map([
            (int(row[0]), str(row[7] or ""), str(row[9] or ""))
            for row in rows
            if self._safe_int(row[0]) is not None
        ])

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
                    "membership_status": self._normalize_membership_status(row[8]),
                    "is_inherited": bool(row[10]),
                    "module_keys": membership_module_map.get(membership_id, []),
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
        module_keys: list[str] | None = None,
        actor_user: AuthUser | None = None,
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

        resolved_module_keys = self._resolve_create_module_keys(
            scope_type="subaccount",
            role_key=role_key,
            requested_module_keys=module_keys,
            subaccount_id=sub_ref.id,
            actor_user=actor_user,
        )

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
        self.set_membership_module_keys(
            membership_id=membership_id,
            scope_type="subaccount",
            module_keys=resolved_module_keys,
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
            "module_keys": resolved_module_keys,
        }


    def _normalize_update_role_for_scope(self, *, scope_type: str, user_role: str) -> str:
        normalized_scope = str(scope_type or "").strip().lower()
        candidate = str(user_role or "").strip().lower()
        if candidate == "":
            raise ValueError("Rol invalid")

        if normalized_scope == "agency":
            aliases = {
                "admin": "agency_admin",
                "member": "agency_member",
                "viewer": "agency_viewer",
            }
            candidate = aliases.get(candidate, candidate)
            if candidate not in {"agency_admin", "agency_member", "agency_viewer"}:
                raise ValueError("Rol invalid pentru membership agency")
            return candidate

        if normalized_scope == "subaccount":
            aliases = {
                "admin": "subaccount_admin",
                "member": "subaccount_user",
                "viewer": "subaccount_viewer",
            }
            candidate = aliases.get(candidate, candidate)
            if candidate not in {"subaccount_admin", "subaccount_user", "subaccount_viewer"}:
                raise ValueError("Rol invalid pentru membership sub-account")
            return candidate

        raise ValueError("Scope membership invalid")

    def _actor_can_manage_membership(self, *, actor_user: AuthUser, target_scope: str, target_subaccount_id: int | None) -> tuple[bool, bool]:
        actor_role = normalize_role(actor_user.role)
        if actor_role in {"super_admin", "agency_owner", "agency_admin"}:
            return True, False

        if actor_role.startswith("subaccount_"):
            if actor_role != "subaccount_admin":
                return False, False
            if str(target_scope or "").strip().lower() != "subaccount" or target_subaccount_id is None:
                return False, True

            allowed = {int(value) for value in actor_user.allowed_subaccount_ids}
            if len(allowed) > 0:
                return int(target_subaccount_id) in allowed, False

            legacy_subaccount_id = actor_user.subaccount_id if actor_user.subaccount_id is not None else actor_user.primary_subaccount_id
            if legacy_subaccount_id is None:
                return False, False
            return int(legacy_subaccount_id) == int(target_subaccount_id), False

        return False, False

    def get_membership_detail(self, *, membership_id: int, actor_user: AuthUser) -> dict[str, object] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      um.id,
                      um.user_id,
                      um.scope_type,
                      um.subaccount_id,
                      um.subaccount_name,
                      um.role_key,
                      um.status,
                      u.first_name,
                      u.last_name,
                      u.email,
                      u.phone,
                      u.extension
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

        target_scope = str(row[2] or "")
        target_subaccount_id = int(row[3]) if row[3] is not None else None
        can_manage, inherited_for_actor = self._actor_can_manage_membership(
            actor_user=actor_user,
            target_scope=target_scope,
            target_subaccount_id=target_subaccount_id,
        )
        if not can_manage and not inherited_for_actor:
            raise PermissionError("Nu ai acces la acest membership")

        role_key = str(row[5] or "")
        scope_type = str(row[2] or "")
        module_keys = self.get_membership_module_keys(
            membership_id=int(row[0]),
            role_key=role_key,
            scope_type=scope_type,
        )

        return {
            "membership_id": int(row[0]),
            "user_id": int(row[1]),
            "scope_type": scope_type,
            "subaccount_id": target_subaccount_id,
            "subaccount_name": str(row[4] or ""),
            "role_key": role_key,
            "role_label": self._role_label(role_key=role_key),
            "module_keys": module_keys,
            "source_scope": scope_type,
            "is_inherited": bool(inherited_for_actor),
            "is_active": str(row[6] or "") == "active",
            "membership_status": self._normalize_membership_status(row[6]),
            "first_name": str(row[7] or ""),
            "last_name": str(row[8] or ""),
            "email": str(row[9] or "").strip().lower(),
            "phone": str(row[10] or ""),
            "extension": str(row[11] or ""),
        }

    def update_membership(self, *, membership_id: int, actor_user: AuthUser, user_role: str | None, module_keys: list[str] | None) -> dict[str, object]:
        current = self.get_membership_detail(membership_id=membership_id, actor_user=actor_user)
        if current is None:
            raise LookupError("Membership inexistent")
        if bool(current.get("is_inherited")):
            raise RuntimeError("Access moștenit: acest membership nu poate fi editat local")

        scope_type = str(current.get("scope_type") or "").strip().lower()
        role_key = str(current.get("role_key") or "").strip().lower()
        subaccount_id = current.get("subaccount_id")
        resolved_module_keys = current.get("module_keys") if isinstance(current.get("module_keys"), list) else []

        if user_role is not None:
            role_key = self._normalize_update_role_for_scope(scope_type=scope_type, user_role=user_role)

        if scope_type == "agency":
            if module_keys is not None:
                raise ValueError("module_keys nu este permis pentru membership-uri agency")
            resolved_module_keys = []
        elif scope_type == "subaccount":
            if module_keys is not None:
                resolved_module_keys = self._normalize_subaccount_module_keys(module_keys)
                if len(resolved_module_keys) == 0:
                    raise ValueError("Selectează cel puțin un modul")
            if normalize_role(actor_user.role).startswith("subaccount_"):
                grantable = self.get_grantable_module_keys_for_actor(actor_user=actor_user, subaccount_id=int(subaccount_id or 0))
                forbidden = [key for key in resolved_module_keys if key not in grantable]
                if forbidden:
                    joined = ", ".join(forbidden)
                    raise PermissionError(f"Nu poți acorda module în afara permisiunilor proprii: {joined}")
        else:
            raise ValueError("Scope membership invalid")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE user_memberships
                    SET role_key = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (role_key, int(membership_id)),
                )
                if int(cur.rowcount or 0) != 1:
                    raise LookupError("Membership inexistent")

                cur.execute("DELETE FROM membership_module_permissions WHERE membership_id = %s", (int(membership_id),))
                if scope_type == "subaccount":
                    for module_key in resolved_module_keys:
                        cur.execute(
                            """
                            INSERT INTO membership_module_permissions (membership_id, module_key)
                            VALUES (%s, %s)
                            ON CONFLICT (membership_id, module_key) DO NOTHING
                            """,
                            (int(membership_id), module_key),
                        )
            conn.commit()

        updated = self.get_membership_detail(membership_id=membership_id, actor_user=actor_user)
        if updated is None:
            raise LookupError("Membership inexistent")
        return updated

    def _transition_membership_status(self, *, membership_id: int, actor_user: AuthUser, target_status: str) -> dict[str, object]:
        normalized_target = self._normalize_membership_status(target_status)
        if normalized_target not in {"active", "inactive"}:
            raise ValueError("Status invalid")

        current = self.get_membership_detail(membership_id=membership_id, actor_user=actor_user)
        if current is None:
            raise LookupError("Membership inexistent")
        if bool(current.get("is_inherited")):
            raise RuntimeError("Access moștenit: acest membership nu poate fi modificat local")

        current_status = self._normalize_membership_status(current.get("membership_status"))
        if current_status == normalized_target:
            message = "Membership-ul este deja activ" if normalized_target == "active" else "Membership-ul este deja inactiv"
            return {"membership_id": int(membership_id), "status": normalized_target, "message": message}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE user_memberships
                    SET status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (normalized_target, int(membership_id)),
                )
                if int(cur.rowcount or 0) != 1:
                    raise LookupError("Membership inexistent")
            conn.commit()

        message = "Membership dezactivat" if normalized_target == "inactive" else "Membership reactivat"
        return {"membership_id": int(membership_id), "status": normalized_target, "message": message}

    def deactivate_membership(self, *, membership_id: int, actor_user: AuthUser) -> dict[str, object]:
        return self._transition_membership_status(membership_id=membership_id, actor_user=actor_user, target_status="inactive")

    def reactivate_membership(self, *, membership_id: int, actor_user: AuthUser) -> dict[str, object]:
        return self._transition_membership_status(membership_id=membership_id, actor_user=actor_user, target_status="active")

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
