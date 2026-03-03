from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
import os

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_UNSET = object()


@dataclass
class ClientRecord:
    id: int
    name: str
    owner_email: str
    source: str = "manual"
    client_type: str = "lead"
    account_manager: str = ""
    currency: str = "USD"
    client_logo_url: str = ""
    media_storage_bytes: int = 0


class ClientRegistryService:
    def __init__(self) -> None:
        self._clients: list[ClientRecord] = []
        self._next_id = 1
        self._lock = Lock()
        self._memory_platform_accounts: dict[str, dict[str, dict[str, str]]] = {}
        self._memory_last_import_at: dict[str, str] = {}
        self._memory_account_client_mappings: dict[str, dict[str, set[int]]] = {}
        self._memory_account_profiles: dict[str, dict[str, dict[int, dict[str, str]]]] = {}
        self._operational_metadata_schema_initialized = False
        self._sync_state_schema_initialized = False

    def _is_test_mode(self) -> bool:
        # Use in-memory registry only while running pytest to avoid accidental data loss in deployed environments.
        return load_settings().app_env == "test" and os.environ.get("PYTEST_CURRENT_TEST") is not None

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for client registry Postgres persistence")
        return psycopg.connect(settings.database_url)

    def _connect_or_raise(self):
        conn = self._connect()
        return conn

    def _ensure_agency_platform_accounts_operational_metadata_schema(self) -> None:
        if self._is_test_mode():
            return

        if self._operational_metadata_schema_initialized:
            return

        with self._lock:
            if self._operational_metadata_schema_initialized:
                return

            with self._connect_or_raise() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.agency_platform_accounts')")
                    table_row = cur.fetchone() or (None,)
                    if table_row[0] is None:
                        raise RuntimeError("Database schema for agency_platform_accounts operational metadata is not ready; run DB migrations")

                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'agency_platform_accounts'
                          AND column_name IN ('status', 'currency_code', 'account_timezone', 'sync_start_date', 'last_synced_at')
                        """
                    )
                    columns_row = cur.fetchone() or (0,)
                    if int(columns_row[0] or 0) < 5:
                        raise RuntimeError("Database schema for agency_platform_accounts operational metadata is not ready; run DB migrations")

            self._operational_metadata_schema_initialized = True


    def _ensure_agency_platform_accounts_sync_state_schema(self) -> None:
        if self._is_test_mode():
            return

        if self._sync_state_schema_initialized:
            return

        with self._lock:
            if self._sync_state_schema_initialized:
                return

            with self._connect_or_raise() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'agency_platform_accounts'
                          AND column_name IN (
                            'rolling_window_days',
                            'backfill_completed_through',
                            'rolling_synced_through',
                            'last_success_at',
                            'last_error',
                            'last_run_id'
                          )
                        """
                    )
                    row = cur.fetchone() or (0,)
                    if int(row[0] or 0) < 6:
                        raise RuntimeError("Database schema for agency_platform_accounts sync state columns is not ready; run DB migrations")

            self._sync_state_schema_initialized = True

    def _ensure_schema(self) -> None:
        if self._is_test_mode():
            return

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_clients (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        owner_email TEXT NOT NULL,
                        google_customer_id TEXT NULL,
                        source TEXT NOT NULL DEFAULT 'manual',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual'")
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS client_type TEXT NOT NULL DEFAULT 'lead'")
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS account_manager TEXT NOT NULL DEFAULT ''")
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'USD'")
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS client_logo_url TEXT NOT NULL DEFAULT ''")
                cur.execute("ALTER TABLE agency_clients ADD COLUMN IF NOT EXISTS media_storage_bytes BIGINT NOT NULL DEFAULT 0")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_platform_accounts (
                        platform TEXT NOT NULL,
                        account_id TEXT NOT NULL,
                        account_name TEXT NOT NULL,
                        imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY(platform, account_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_platform_imports (
                        platform TEXT PRIMARY KEY,
                        last_import_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_account_client_mappings (
                        id BIGSERIAL PRIMARY KEY,
                        platform TEXT NOT NULL,
                        account_id TEXT NOT NULL,
                        client_id INTEGER NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE(platform, account_id, client_id),
                        FOREIGN KEY (platform, account_id) REFERENCES agency_platform_accounts(platform, account_id) ON DELETE CASCADE,
                        FOREIGN KEY (client_id) REFERENCES agency_clients(id) ON DELETE CASCADE
                    )
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE agency_account_client_mappings
                    DROP CONSTRAINT IF EXISTS agency_account_client_mappings_platform_account_id_key
                    """
                )
                cur.execute("ALTER TABLE agency_account_client_mappings ADD COLUMN IF NOT EXISTS client_type TEXT NULL")
                cur.execute("ALTER TABLE agency_account_client_mappings ADD COLUMN IF NOT EXISTS account_manager TEXT NULL")
                cur.execute("ALTER TABLE agency_account_client_mappings ADD COLUMN IF NOT EXISTS account_currency TEXT NULL")
                cur.execute(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'agency_account_client_mappings_unique'
                        ) THEN
                            ALTER TABLE agency_account_client_mappings
                            ADD CONSTRAINT agency_account_client_mappings_unique UNIQUE(platform, account_id, client_id);
                        END IF;
                    END$$;
                    """
                )
                # Legacy cleanup: mark obvious synthetic auto-imported rows as imported.
                cur.execute(
                    """
                    UPDATE agency_clients c
                    SET source = 'imported'
                    WHERE c.source = 'manual'
                      AND c.google_customer_id IS NULL
                      AND c.name LIKE 'Google Account %'
                    """
                )
            conn.commit()

    def initialize_schema(self) -> None:
        self._ensure_schema()

    def create_client(self, name: str, owner_email: str) -> dict[str, str | int | None]:

        if self._is_test_mode():
            with self._lock:
                record = ClientRecord(id=self._next_id, name=name, owner_email=owner_email, source="manual", client_type="lead", account_manager="", currency="USD", client_logo_url="", media_storage_bytes=0)
                self._next_id += 1
                self._clients.append(record)
                manual_count = len([c for c in self._clients if c.source == "manual"])
                return {
                    "id": record.id,
                    "display_id": manual_count,
                    "name": record.name,
                    "owner_email": record.owner_email,
                    "client_type": record.client_type,
                    "account_manager": record.account_manager,
                    "currency": record.currency,
                    "google_customer_id": None,
                    "client_logo_url": "",
                    "media_storage_bytes": 0,
                }

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agency_clients (name, owner_email, source)
                    VALUES (%s, %s, 'manual')
                    RETURNING id, name, owner_email, client_type, account_manager, currency, client_logo_url, media_storage_bytes
                    """,
                    (name, owner_email),
                )
                row = cur.fetchone()
            conn.commit()

        client_id = int(row[0])
        return {
            "id": client_id,
            "display_id": self.get_manual_display_id(client_id=client_id),
            "name": str(row[1]),
            "owner_email": str(row[2]),
            "client_type": str(row[3]),
            "account_manager": str(row[4]),
            "currency": str(row[5]),
            "client_logo_url": str(row[6]),
            "media_storage_bytes": int(row[7]),
            "google_customer_id": self.get_google_customer_for_client(client_id=client_id),
        }

    def _list_clients_test(self) -> list[dict[str, str | int | None]]:
        records: list[dict[str, str | int | None]] = []
        display_id = 0
        for c in self._clients:
            if c.source != "manual":
                continue
            display_id += 1
            records.append(
                {
                    "id": c.id,
                    "display_id": display_id,
                    "name": c.name,
                    "owner_email": c.owner_email,
                    "client_type": c.client_type,
                    "account_manager": c.account_manager,
                    "currency": c.currency,
                    "client_logo_url": c.client_logo_url,
                    "google_customer_id": next((aid for aid, client_ids in self._memory_account_client_mappings.get("google_ads", {}).items() if c.id in client_ids), None),
                    "media_storage_bytes": c.media_storage_bytes,
                }
            )
        return records

    def list_clients(self) -> list[dict[str, str | int | None]]:

        if self._is_test_mode():
            with self._lock:
                return self._list_clients_test()

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.name, c.owner_email, c.client_type, c.account_manager, c.currency, c.client_logo_url, c.media_storage_bytes,
                           ROW_NUMBER() OVER (ORDER BY c.id ASC) AS display_id,
                           (
                              SELECT m.account_id
                              FROM agency_account_client_mappings m
                              WHERE m.platform = 'google_ads' AND m.client_id = c.id
                              ORDER BY m.updated_at DESC, m.created_at DESC
                              LIMIT 1
                           ) AS google_customer_id
                    FROM agency_clients c
                    WHERE c.source = 'manual'
                    ORDER BY c.id ASC
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "id": int(row[0]),
                "name": str(row[1]),
                "owner_email": str(row[2]),
                "client_type": str(row[3]),
                "account_manager": str(row[4]),
                "currency": str(row[5]),
                "client_logo_url": str(row[6]),
                "display_id": int(row[8]),
                "media_storage_bytes": int(row[7] or 0),
                "google_customer_id": str(row[9]) if row[9] else None,
            }
            for row in rows
        ]

    def _client_exists_test(self, *, client_id: int) -> bool:
        return any(c.id == client_id and c.source == "manual" for c in self._clients)

    def attach_platform_account_to_client(self, *, platform: str, client_id: int, account_id: str) -> dict[str, str | int | None] | None:
        account_id = str(account_id).strip()
        if account_id == "":
            return None

        if self._is_test_mode():
            with self._lock:
                if not self._client_exists_test(client_id=client_id):
                    return None
                platform_accounts = self._memory_platform_accounts.get(platform, {})
                if account_id not in platform_accounts:
                    return None
                mappings = self._memory_account_client_mappings.setdefault(platform, {})
                mappings.setdefault(account_id, set()).add(client_id)
                client = next(c for c in self._clients if c.id == client_id)
                per_platform = self._memory_account_profiles.setdefault(platform, {})
                per_account = per_platform.setdefault(account_id, {})
                per_account.setdefault(client_id, {"client_type": client.client_type, "account_manager": client.account_manager, "account_currency": client.currency})
                return {
                    "id": client.id,
                    "name": client.name,
                    "owner_email": client.owner_email,
                    "google_customer_id": next((aid for aid, client_ids in mappings.items() if client.id in client_ids), None),
                }

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, owner_email FROM agency_clients WHERE id = %s AND source = 'manual'", (client_id,))
                client_row = cur.fetchone()
                if client_row is None:
                    return None

                cur.execute(
                    "SELECT 1 FROM agency_platform_accounts WHERE platform = %s AND account_id = %s",
                    (platform, account_id),
                )
                exists_row = cur.fetchone()
                if exists_row is None:
                    return None

                cur.execute(
                    """
                    INSERT INTO agency_account_client_mappings (platform, account_id, client_id, client_type, account_manager, account_currency)
                    VALUES (
                        %s,
                        %s,
                        %s,
                        (SELECT client_type FROM agency_clients WHERE id = %s),
                        (SELECT account_manager FROM agency_clients WHERE id = %s),
                        (SELECT currency FROM agency_clients WHERE id = %s)
                    )
                    ON CONFLICT(platform, account_id, client_id)
                    DO UPDATE SET updated_at = NOW()
                    """,
                    (platform, account_id, client_id, client_id, client_id, client_id),
                )
                if platform == "google_ads":
                    # Keep legacy column in sync (best effort; not used as source-of-truth).
                    cur.execute(
                        """
                        UPDATE agency_clients c
                        SET google_customer_id = (
                            SELECT m.account_id
                            FROM agency_account_client_mappings m
                            WHERE m.platform = 'google_ads' AND m.client_id = c.id
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ),
                        updated_at = NOW()
                        WHERE c.id = %s
                        """,
                        (client_id,),
                    )
            conn.commit()

        return {
            "id": int(client_row[0]),
            "name": str(client_row[1]),
            "owner_email": str(client_row[2]),
            "google_customer_id": self.get_google_customer_for_client(client_id=client_id),
        }

    def assign_google_customer(self, *, client_id: int, customer_id: str) -> dict[str, str | int | None] | None:
        return self.attach_platform_account_to_client(platform="google_ads", client_id=client_id, account_id=customer_id)

    def detach_platform_account_from_client(self, *, platform: str, client_id: int, account_id: str) -> bool:
        account_id = str(account_id).strip()
        if account_id == "":
            return False

        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.setdefault(platform, {})
                client_ids = mappings.get(account_id)
                if client_ids is None or client_id not in client_ids:
                    return False
                client_ids.remove(client_id)
                if not client_ids:
                    del mappings[account_id]
                profiles = self._memory_account_profiles.setdefault(platform, {})
                per_account = profiles.get(account_id, {})
                per_account.pop(client_id, None)
                if not per_account and account_id in profiles:
                    del profiles[account_id]
                return True

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agency_account_client_mappings WHERE platform = %s AND account_id = %s AND client_id = %s",
                    (platform, account_id, client_id),
                )
                deleted = cur.rowcount > 0
                if deleted and platform == "google_ads":
                    cur.execute(
                        """
                        UPDATE agency_clients c
                        SET google_customer_id = (
                            SELECT m.account_id
                            FROM agency_account_client_mappings m
                            WHERE m.platform = 'google_ads' AND m.client_id = c.id
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ),
                        updated_at = NOW()
                        WHERE c.id = %s
                        """,
                        (client_id,),
                    )
            conn.commit()
        return deleted

    def get_google_mapping_details_for_client(self, *, client_id: int) -> dict[str, object] | None:
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get("google_ads", {})
                for account_id, mapped_client_ids in mappings.items():
                    if client_id in mapped_client_ids:
                        return {
                            "customer_id": account_id,
                            "updated_at": None,
                        }
                return None

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT account_id, updated_at
                    FROM agency_account_client_mappings
                    WHERE platform = 'google_ads' AND client_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (client_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return {
            "customer_id": str(row[0]),
            "updated_at": str(row[1]) if row[1] else None,
        }

    def list_google_mapped_accounts(self) -> list[dict[str, object]]:
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get("google_ads", {})
                rows: list[dict[str, object]] = []
                for account_id, client_ids in mappings.items():
                    for client_id in sorted(client_ids):
                        rows.append({
                            "client_id": int(client_id),
                            "customer_id": str(account_id),
                            "updated_at": None,
                        })
                return rows

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT client_id, account_id, updated_at
                    FROM agency_account_client_mappings
                    WHERE platform = 'google_ads'
                    ORDER BY updated_at DESC, created_at DESC
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "client_id": int(row[0]),
                "customer_id": str(row[1]),
                "updated_at": str(row[2]) if row[2] else None,
            }
            for row in rows
        ]

    def get_google_customer_for_client(self, *, client_id: int) -> str | None:
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get("google_ads", {})
                for account_id, mapped_client_ids in mappings.items():
                    if client_id in mapped_client_ids:
                        return account_id
                return None

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT account_id
                    FROM agency_account_client_mappings
                    WHERE platform = 'google_ads' AND client_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (client_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return str(row[0])

    def upsert_platform_accounts(self, *, platform: str, accounts: list[dict[str, str]]) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._is_test_mode():
            with self._lock:
                platform_items = self._memory_platform_accounts.setdefault(platform, {})
                for account in accounts:
                    platform_items[str(account["id"])] = {"id": str(account["id"]), "name": str(account["name"])}
                self._memory_last_import_at[platform] = now_iso
            return

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                for account in accounts:
                    cur.execute(
                        """
                        INSERT INTO agency_platform_accounts (platform, account_id, account_name, imported_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT(platform, account_id) DO UPDATE SET
                            account_name = EXCLUDED.account_name,
                            imported_at = NOW()
                        """,
                        (platform, str(account["id"]), str(account["name"])),
                    )
                cur.execute(
                    """
                    INSERT INTO agency_platform_imports (platform, last_import_at)
                    VALUES (%s, NOW())
                    ON CONFLICT(platform) DO UPDATE SET last_import_at = EXCLUDED.last_import_at
                    """,
                    (platform,),
                )
            conn.commit()

    def list_platform_accounts(self, *, platform: str) -> list[dict[str, str | int | None]]:
        if self._is_test_mode():
            with self._lock:
                items = self._memory_platform_accounts.get(platform, {})
                mappings = self._memory_account_client_mappings.get(platform, {})
                clients_by_id = {c.id: c for c in self._clients if c.source == "manual"}
                result: list[dict[str, str | int | None]] = []
                for key in sorted(items.keys()):
                    item = dict(items[key])
                    mapped_client_ids = sorted(mappings.get(item["id"], set()))
                    mapped_client = clients_by_id.get(mapped_client_ids[0]) if mapped_client_ids else None
                    item["attached_client_id"] = mapped_client.id if mapped_client else None
                    item["attached_client_name"] = mapped_client.name if mapped_client else None
                    result.append(item)
                return result

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.account_id, a.account_name, m.client_id, c.name
                    FROM agency_platform_accounts a
                    LEFT JOIN LATERAL (
                      SELECT client_id
                      FROM agency_account_client_mappings
                      WHERE platform = a.platform AND account_id = a.account_id
                      ORDER BY updated_at DESC, created_at DESC
                      LIMIT 1
                    ) m ON TRUE
                    LEFT JOIN agency_clients c
                      ON c.id = m.client_id
                    WHERE a.platform = %s
                    ORDER BY a.imported_at DESC
                    """,
                    (platform,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(row[0]),
                "name": str(row[1]),
                "attached_client_id": int(row[2]) if row[2] is not None else None,
                "attached_client_name": str(row[3]) if row[3] else None,
            }
            for row in rows
        ]

    def update_platform_account_operational_metadata(
        self,
        *,
        platform: str,
        account_id: str,
        status: str | None | object = _UNSET,
        currency_code: str | None | object = _UNSET,
        account_timezone: str | None | object = _UNSET,
        sync_start_date: date | None | object = _UNSET,
        last_synced_at: datetime | None | object = _UNSET,
        rolling_window_days: int | None | object = _UNSET,
        backfill_completed_through: date | None | object = _UNSET,
        rolling_synced_through: date | None | object = _UNSET,
        last_success_at: datetime | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        last_run_id: str | None | object = _UNSET,
    ) -> dict[str, object] | None:
        normalized_platform = platform.strip()
        normalized_account_id = account_id.strip()

        if self._is_test_mode():
            with self._lock:
                items = self._memory_platform_accounts.get(normalized_platform, {})
                existing = items.get(normalized_account_id)
                if existing is None:
                    return None
                if status is not _UNSET:
                    existing["status"] = None if status is None else str(status)
                if currency_code is not _UNSET:
                    existing["currency_code"] = None if currency_code is None else str(currency_code)
                if account_timezone is not _UNSET:
                    existing["account_timezone"] = None if account_timezone is None else str(account_timezone)
                if sync_start_date is not _UNSET:
                    existing["sync_start_date"] = None if sync_start_date is None else str(sync_start_date)
                if last_synced_at is not _UNSET:
                    existing["last_synced_at"] = None if last_synced_at is None else str(last_synced_at)
                if rolling_window_days is not _UNSET:
                    existing["rolling_window_days"] = None if rolling_window_days is None else int(rolling_window_days)
                if backfill_completed_through is not _UNSET:
                    existing["backfill_completed_through"] = None if backfill_completed_through is None else str(backfill_completed_through)
                if rolling_synced_through is not _UNSET:
                    existing["rolling_synced_through"] = None if rolling_synced_through is None else str(rolling_synced_through)
                if last_success_at is not _UNSET:
                    existing["last_success_at"] = None if last_success_at is None else str(last_success_at)
                if last_error is not _UNSET:
                    existing["last_error"] = None if last_error is None else str(last_error)
                if last_run_id is not _UNSET:
                    existing["last_run_id"] = None if last_run_id is None else str(last_run_id)
                return {
                    "platform": normalized_platform,
                    "account_id": normalized_account_id,
                    "status": existing.get("status"),
                    "currency_code": existing.get("currency_code"),
                    "account_timezone": existing.get("account_timezone"),
                    "sync_start_date": existing.get("sync_start_date"),
                    "last_synced_at": existing.get("last_synced_at"),
                    "rolling_window_days": existing.get("rolling_window_days"),
                    "backfill_completed_through": existing.get("backfill_completed_through"),
                    "rolling_synced_through": existing.get("rolling_synced_through"),
                    "last_success_at": existing.get("last_success_at"),
                    "last_error": existing.get("last_error"),
                    "last_run_id": existing.get("last_run_id"),
                }

        self._ensure_agency_platform_accounts_operational_metadata_schema()
        has_new_sync_state_updates = any(
            value is not _UNSET
            for value in (
                rolling_window_days,
                backfill_completed_through,
                rolling_synced_through,
                last_success_at,
                last_error,
                last_run_id,
            )
        )
        if has_new_sync_state_updates:
            self._ensure_agency_platform_accounts_sync_state_schema()

        updates: list[str] = []
        params: list[object] = []
        if status is not _UNSET:
            updates.append("status = %s")
            params.append(status)
        if currency_code is not _UNSET:
            updates.append("currency_code = %s")
            params.append(currency_code)
        if account_timezone is not _UNSET:
            updates.append("account_timezone = %s")
            params.append(account_timezone)
        if sync_start_date is not _UNSET:
            updates.append("sync_start_date = %s")
            params.append(sync_start_date)
        if last_synced_at is not _UNSET:
            updates.append("last_synced_at = %s")
            params.append(last_synced_at)
        if rolling_window_days is not _UNSET:
            updates.append("rolling_window_days = %s")
            params.append(rolling_window_days)
        if backfill_completed_through is not _UNSET:
            if backfill_completed_through is None:
                updates.append("backfill_completed_through = NULL")
            else:
                updates.append("backfill_completed_through = CASE WHEN backfill_completed_through IS NULL OR backfill_completed_through < %s THEN %s ELSE backfill_completed_through END")
                params.extend([backfill_completed_through, backfill_completed_through])
        if rolling_synced_through is not _UNSET:
            if rolling_synced_through is None:
                updates.append("rolling_synced_through = NULL")
            else:
                updates.append("rolling_synced_through = CASE WHEN rolling_synced_through IS NULL OR rolling_synced_through < %s THEN %s ELSE rolling_synced_through END")
                params.extend([rolling_synced_through, rolling_synced_through])
        if last_success_at is not _UNSET:
            updates.append("last_success_at = %s")
            params.append(last_success_at)
        if last_error is not _UNSET:
            updates.append("last_error = %s")
            params.append(last_error)
        if last_run_id is not _UNSET:
            updates.append("last_run_id = %s")
            params.append(last_run_id)

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                if len(updates) > 0:
                    cur.execute(
                        f"""
                        UPDATE agency_platform_accounts
                        SET {', '.join(updates)}
                        WHERE platform = %s AND account_id = %s
                        """,
                        (*params, normalized_platform, normalized_account_id),
                    )
                    if cur.rowcount <= 0:
                        conn.commit()
                        return None
                if has_new_sync_state_updates:
                    cur.execute(
                        """
                        SELECT
                            platform,
                            account_id,
                            status,
                            currency_code,
                            account_timezone,
                            sync_start_date,
                            last_synced_at,
                            rolling_window_days,
                            backfill_completed_through,
                            rolling_synced_through,
                            last_success_at,
                            last_error,
                            last_run_id
                        FROM agency_platform_accounts
                        WHERE platform = %s AND account_id = %s
                        """,
                        (normalized_platform, normalized_account_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT platform, account_id, status, currency_code, account_timezone, sync_start_date, last_synced_at
                        FROM agency_platform_accounts
                        WHERE platform = %s AND account_id = %s
                        """,
                        (normalized_platform, normalized_account_id),
                    )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            return None
        payload = {
            "platform": str(row[0]),
            "account_id": str(row[1]),
            "status": str(row[2]) if row[2] is not None else None,
            "currency_code": str(row[3]) if row[3] is not None else None,
            "account_timezone": str(row[4]) if row[4] is not None else None,
            "sync_start_date": str(row[5]) if row[5] is not None else None,
            "last_synced_at": str(row[6]) if row[6] is not None else None,
        }
        if has_new_sync_state_updates:
            payload.update(
                {
                    "rolling_window_days": int(row[7]) if row[7] is not None else None,
                    "backfill_completed_through": str(row[8]) if row[8] is not None else None,
                    "rolling_synced_through": str(row[9]) if row[9] is not None else None,
                    "last_success_at": str(row[10]) if row[10] is not None else None,
                    "last_error": str(row[11]) if row[11] is not None else None,
                    "last_run_id": str(row[12]) if row[12] is not None else None,
                }
            )
        return payload

    def list_client_platform_accounts(self, *, platform: str, client_id: int) -> list[dict[str, str]]:
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get(platform, {})
                accounts = self._memory_platform_accounts.get(platform, {})
                result: list[dict[str, str]] = []
                profiles = self._memory_account_profiles.get(platform, {})
                for account_id, mapped_client_ids in mappings.items():
                    if client_id not in mapped_client_ids:
                        continue
                    info = accounts.get(account_id)
                    if info:
                        profile = profiles.get(account_id, {}).get(client_id, {})
                        result.append({
                            "id": info["id"],
                            "name": info["name"],
                            "client_type": str(profile.get("client_type", "lead")),
                            "account_manager": str(profile.get("account_manager", "")),
                            "currency": str(profile.get("account_currency", "USD")),
                        })
                return sorted(result, key=lambda item: item["id"])

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.account_id, a.account_name, m.client_type, m.account_manager, m.account_currency
                    FROM agency_account_client_mappings m
                    JOIN agency_platform_accounts a
                      ON a.platform = m.platform AND a.account_id = m.account_id
                    WHERE m.platform = %s AND m.client_id = %s
                    ORDER BY m.updated_at DESC, m.created_at DESC
                    """,
                    (platform, client_id),
                )
                rows = cur.fetchall()
        return [{"id": str(row[0]), "name": str(row[1]), "client_type": str(row[2]) if row[2] else "lead", "account_manager": str(row[3]) if row[3] else "", "currency": str(row[4]) if row[4] else "USD"} for row in rows]

    def get_last_import_at(self, *, platform: str) -> str | None:
        if self._is_test_mode():
            with self._lock:
                return self._memory_last_import_at.get(platform)

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT last_import_at FROM agency_platform_imports WHERE platform = %s", (platform,))
                row = cur.fetchone()
        if row is None:
            return None
        return str(row[0])

    def platform_account_summary(self) -> list[dict[str, str | int | None]]:
        platforms = ["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]
        summary: list[dict[str, str | int | None]] = []
        for platform in platforms:
            accounts = self.list_platform_accounts(platform=platform)
            summary.append(
                {
                    "platform": platform,
                    "connected_count": len(accounts),
                    "last_import_at": self.get_last_import_at(platform=platform),
                }
            )
        return summary

    def get_manual_display_id(self, *, client_id: int) -> int | None:
        if self._is_test_mode():
            with self._lock:
                display_id = 0
                for c in self._clients:
                    if c.source != "manual":
                        continue
                    display_id += 1
                    if c.id == client_id:
                        return display_id
                return None

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT display_id FROM (
                      SELECT id, ROW_NUMBER() OVER (ORDER BY id ASC) AS display_id
                      FROM agency_clients
                      WHERE source = 'manual'
                    ) ranked
                    WHERE id = %s
                    """,
                    (client_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return int(row[0])

    def get_client_details(self, *, client_id: int) -> dict[str, object] | None:
        clients = self.list_clients()
        target = next((item for item in clients if int(item["id"]) == client_id), None)
        if target is None:
            return None

        platforms = ["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]
        platform_items: list[dict[str, object]] = []
        for platform in platforms:
            accounts = self.list_client_platform_accounts(platform=platform, client_id=client_id)
            platform_items.append(
                {
                    "platform": platform,
                    "enabled": len(accounts) > 0,
                    "accounts": accounts,
                    "count": len(accounts),
                }
            )

        return {
            "client": target,
            "platforms": platform_items,
        }


    def _resolve_client_id_by_display_id(self, *, display_id: int) -> int | None:
        clients = self.list_clients()
        for item in clients:
            if int(item.get("display_id", -1)) == display_id:
                return int(item["id"])
        return None

    def get_client_details_by_display_id(self, *, display_id: int) -> dict[str, object] | None:
        client_id = self._resolve_client_id_by_display_id(display_id=display_id)
        if client_id is None:
            return None
        details = self.get_client_details(client_id=client_id)
        if details is None:
            return None
        return details

    def update_client_profile_by_display_id(
        self,
        *,
        display_id: int,
        name: str | None = None,
        client_type: str | None = None,
        account_manager: str | None = None,
        currency: str | None = None,
        client_logo_url: str | None = None,
        platform: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, object] | None:
        client_id = self._resolve_client_id_by_display_id(display_id=display_id)
        if client_id is None:
            return None

        normalized_name = name.strip() if name is not None else None
        normalized_type = client_type.strip().lower() if client_type is not None else None
        if normalized_type is not None and normalized_type not in {"lead", "e-commerce", "programmatic"}:
            normalized_type = "lead"
        normalized_manager = account_manager.strip() if account_manager is not None else None
        normalized_currency = currency.strip().upper() if currency is not None else None
        if normalized_currency is not None:
            if len(normalized_currency) != 3 or not normalized_currency.isalpha():
                normalized_currency = "USD"
        normalized_logo = client_logo_url.strip() if client_logo_url is not None else None

        if self._is_test_mode():
            with self._lock:
                for idx, c in enumerate(self._clients):
                    if c.id == client_id and c.source == "manual":
                        self._clients[idx] = ClientRecord(
                            id=c.id,
                            name=normalized_name if normalized_name is not None and normalized_name != "" else c.name,
                            owner_email=c.owner_email,
                            source=c.source,
                            client_type=normalized_type if normalized_type is not None else c.client_type,
                            account_manager=normalized_manager if normalized_manager is not None else c.account_manager,
                            currency=normalized_currency if normalized_currency is not None else c.currency,
                            client_logo_url=normalized_logo if normalized_logo is not None else c.client_logo_url,
                        )
                        normalized_platform = platform.strip() if platform is not None else None
                        normalized_account_id = account_id.strip() if account_id is not None else None
                        if normalized_platform and normalized_account_id and (normalized_type is not None or normalized_manager is not None or normalized_currency is not None):
                            per_platform = self._memory_account_profiles.setdefault(normalized_platform, {})
                            per_account = per_platform.setdefault(normalized_account_id, {})
                            profile = per_account.setdefault(client_id, {"client_type": c.client_type, "account_manager": c.account_manager, "account_currency": c.currency})
                            if normalized_type is not None:
                                profile["client_type"] = normalized_type
                            if normalized_manager is not None:
                                profile["account_manager"] = normalized_manager
                            if normalized_currency is not None:
                                profile["account_currency"] = normalized_currency
                        return self.get_client_details(client_id=client_id)
            return None

        normalized_platform = platform.strip() if platform is not None else None
        normalized_account_id = account_id.strip() if account_id is not None else None

        if normalized_platform and normalized_account_id:
            with self._connect_or_raise() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE agency_account_client_mappings
                        SET client_type = COALESCE(%s, client_type),
                            account_manager = COALESCE(%s, account_manager),
                            account_currency = COALESCE(%s, account_currency),
                            updated_at = NOW()
                        WHERE platform = %s AND account_id = %s AND client_id = %s
                        """,
                        (normalized_type, normalized_manager, normalized_currency, normalized_platform, normalized_account_id, client_id),
                    )
                conn.commit()
            return self.get_client_details(client_id=client_id)

        set_clauses: list[str] = []
        values: list[object] = []
        if normalized_name is not None and normalized_name != "":
            set_clauses.append("name = %s")
            values.append(normalized_name)
        if normalized_type is not None:
            set_clauses.append("client_type = %s")
            values.append(normalized_type)
        if normalized_manager is not None:
            set_clauses.append("account_manager = %s")
            values.append(normalized_manager)
        if normalized_currency is not None:
            set_clauses.append("currency = %s")
            values.append(normalized_currency)
        if normalized_logo is not None:
            set_clauses.append("client_logo_url = %s")
            values.append(normalized_logo)

        if set_clauses:
            with self._connect_or_raise() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE agency_clients
                        SET {", ".join(set_clauses)}, updated_at = NOW()
                        WHERE id = %s AND source = 'manual'
                        """,
                        tuple(values + [client_id]),
                    )
                conn.commit()

        return self.get_client_details(client_id=client_id)


    def get_preferred_currency_for_client(self, *, client_id: int) -> str:
        accounts = self.list_client_platform_accounts(platform="google_ads", client_id=client_id)
        for account in accounts:
            currency = str(account.get("currency") or account.get("account_currency") or "").upper()
            if len(currency) == 3 and currency.isalpha():
                return currency
        return "USD"


    def list_media_storage_usage(
        self,
        *,
        search: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, str | int]], int]:
        token = search.strip().lower()

        if self._is_test_mode():
            with self._lock:
                items = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "address": c.owner_email,
                        "media_storage_bytes": c.media_storage_bytes,
                    }
                    for c in self._clients
                    if c.source == "manual" and (token == "" or token in c.name.lower())
                ]
            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            return items[start:end], total

        clauses = ["c.source = 'manual'"]
        values: list[object] = []
        if token:
            clauses.append("LOWER(c.name) LIKE %s")
            values.append(f"%{token}%")
        where_sql = " AND ".join(clauses)
        offset = (page - 1) * page_size

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM agency_clients c WHERE {where_sql}", tuple(values))
                total = int(cur.fetchone()[0])
                cur.execute(
                    f"""
                    SELECT c.id, c.name, c.owner_email, c.media_storage_bytes
                    FROM agency_clients c
                    WHERE {where_sql}
                    ORDER BY c.id ASC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(values + [page_size, offset]),
                )
                rows = cur.fetchall()

        items = [
            {
                "id": int(row[0]),
                "name": str(row[1]),
                "address": str(row[2]),
                "media_storage_bytes": int(row[3] or 0),
            }
            for row in rows
        ]
        return items, total


    def clear(self) -> None:
        if self._is_test_mode():
            with self._lock:
                self._clients.clear()
                self._next_id = 1
                self._memory_platform_accounts.clear()
                self._memory_last_import_at.clear()
                self._memory_account_client_mappings.clear()
                self._memory_account_profiles.clear()
            return

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agency_account_client_mappings")
                cur.execute("DELETE FROM agency_clients")
                cur.execute("DELETE FROM agency_platform_accounts")
                cur.execute("DELETE FROM agency_platform_imports")
            conn.commit()


client_registry_service = ClientRegistryService()
