from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
from threading import Lock
import os

from app.core.config import load_settings
from app.services.account_currency_resolver import resolve_client_reporting_currency, resolve_effective_attached_account_currency
from app.services.platform_account_watermarks_store import list_platform_account_watermarks

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_UNSET = object()
_SUCCESS_RUN_STATUSES = {"done", "success", "completed"}
logger = logging.getLogger(__name__)


def _coalesce_date_max(*values: object | None) -> object | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def _coalesce_date_min(*values: object | None) -> object | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


def _derive_effective_last_error(*, explicit_last_error: object | None, latest_run_error: object | None, latest_run_status: object | None) -> object | None:
    normalized_status = str(latest_run_status or "").strip().lower()
    if normalized_status in _SUCCESS_RUN_STATUSES:
        return None
    if explicit_last_error is not None:
        return explicit_last_error
    return latest_run_error


def _safe_row_value(row: tuple[object, ...], index: int) -> object | None:
    if index < 0 or index >= len(row):
        return None
    return row[index]




def _coalesce_iso_date_max(existing: object | None, candidate: object | None) -> object | None:
    if candidate is None:
        return existing
    if existing is None:
        return candidate
    try:
        existing_date = date.fromisoformat(str(existing))
        candidate_date = date.fromisoformat(str(candidate))
        return str(max(existing_date, candidate_date))
    except Exception:
        return candidate


def _coalesce_iso_datetime_max(existing: object | None, candidate: object | None) -> object | None:
    if candidate is None:
        return existing
    if existing is None:
        return candidate
    try:
        existing_dt = datetime.fromisoformat(str(existing))
        candidate_dt = datetime.fromisoformat(str(candidate))
        return candidate if candidate_dt >= existing_dt else existing
    except Exception:
        return candidate


def _normalize_account_sync_metadata_payload(*, platform: str, account_id: str, display_name: str, attached_client_id: int | None, attached_client_name: str | None, timezone_value: str | None, currency_value: str | None, account_status: object | None, sync_start_date: object | None, backfill_completed_through: object | None, rolling_synced_through: object | None, last_success_at: object | None, last_error: object | None, last_run_status: object | None, last_run_type: object | None, last_run_started_at: object | None, last_run_finished_at: object | None, has_active_sync: bool) -> dict[str, object]:
    return {
        "id": str(account_id),
        "name": str(display_name),
        "platform": str(platform),
        "account_id": str(account_id),
        "display_name": str(display_name),
        "attached_client_id": int(attached_client_id) if attached_client_id is not None else None,
        "attached_client_name": str(attached_client_name) if attached_client_name is not None else None,
        "timezone": str(timezone_value) if timezone_value is not None else None,
        "currency": str(currency_value) if currency_value is not None else None,
        "status": str(account_status) if account_status is not None else None,
        "sync_start_date": str(sync_start_date) if sync_start_date is not None else None,
        "backfill_completed_through": str(backfill_completed_through) if backfill_completed_through is not None else None,
        "rolling_synced_through": str(rolling_synced_through) if rolling_synced_through is not None else None,
        "last_success_at": str(last_success_at) if last_success_at is not None else None,
        "last_error": str(last_error) if last_error is not None else None,
        "last_run_status": str(last_run_status) if last_run_status is not None else None,
        "last_run_type": str(last_run_type) if last_run_type is not None else None,
        "last_run_started_at": str(last_run_started_at) if last_run_started_at is not None else None,
        "last_run_finished_at": str(last_run_finished_at) if last_run_finished_at is not None else None,
        "has_active_sync": bool(has_active_sync),
        "entity_watermarks": _empty_entity_watermarks_payload(),
    }


def _empty_entity_watermarks_payload() -> dict[str, dict[str, object | None] | None]:
    return {
        "campaign_daily": None,
        "ad_group_daily": None,
        "ad_daily": None,
        "keyword_daily": None,
    }


def _normalize_entity_watermark_payload(value: dict[str, object] | None) -> dict[str, object | None] | None:
    if value is None:
        return None
    return {
        "sync_start_date": value.get("sync_start_date"),
        "historical_synced_through": value.get("historical_synced_through"),
        "rolling_synced_through": value.get("rolling_synced_through"),
        "last_success_at": value.get("last_success_at"),
        "last_error": value.get("last_error"),
        "last_job_id": value.get("last_job_id"),
    }




class PlatformAccountAlreadyAttachedError(Exception):
    def __init__(self, *, platform: str, account_id: str, existing_client_id: int) -> None:
        self.platform = str(platform)
        self.account_id = str(account_id)
        self.existing_client_id = int(existing_client_id)
        super().__init__(f"Account {self.platform}:{self.account_id} is already attached to client {self.existing_client_id}")

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
                        return

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
                        return

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
                        return

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
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS currency_code TEXT NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS account_timezone TEXT NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS sync_start_date DATE NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS rolling_window_days INTEGER DEFAULT 7")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS backfill_completed_through DATE NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS rolling_synced_through DATE NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMPTZ NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS last_error TEXT NULL")
                cur.execute("ALTER TABLE agency_platform_accounts ADD COLUMN IF NOT EXISTS last_run_id TEXT NULL")
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

    def _backfill_blank_mapping_account_currency(self, *, conn) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agency_account_client_mappings m
                SET account_currency = apa.currency_code,
                    updated_at = NOW()
                FROM agency_platform_accounts apa
                WHERE m.platform = apa.platform
                  AND m.account_id = apa.account_id
                  AND (m.account_currency IS NULL OR TRIM(m.account_currency) = '')
                  AND apa.currency_code IS NOT NULL
                  AND TRIM(apa.currency_code) <> ''
                """
            )

    def initialize_schema(self) -> None:
        self._ensure_schema()
        if self._is_test_mode():
            return
        with self._connect_or_raise() as conn:
            self._backfill_blank_mapping_account_currency(conn=conn)
            conn.commit()

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
                existing_client_ids = mappings.get(account_id, set())
                if len(existing_client_ids) > 0 and client_id not in existing_client_ids:
                    existing_client_id = sorted(existing_client_ids)[0]
                    raise PlatformAccountAlreadyAttachedError(platform=platform, account_id=account_id, existing_client_id=existing_client_id)
                mappings[account_id] = {client_id}
                client = next(c for c in self._clients if c.id == client_id)
                per_platform = self._memory_account_profiles.setdefault(platform, {})
                per_account = per_platform.setdefault(account_id, {})
                existing_profile = per_account.get(client_id, {}) if isinstance(per_account.get(client_id), dict) else {}
                resolved_currency, _ = resolve_effective_attached_account_currency(
                    mapping_account_currency=existing_profile.get("account_currency"),
                    platform_account_currency_code=(platform_accounts.get(account_id) or {}).get("currency_code"),
                    client_currency=client.currency,
                    fallback="USD",
                )
                if client_id not in per_account:
                    per_account[client_id] = {"client_type": client.client_type, "account_manager": client.account_manager, "account_currency": resolved_currency}
                else:
                    current = str(existing_profile.get("account_currency") or "").strip()
                    if current == "":
                        per_account[client_id]["account_currency"] = resolved_currency
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
                    SELECT client_id
                    FROM agency_account_client_mappings
                    WHERE platform = %s AND account_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (platform, account_id),
                )
                mapping_row = cur.fetchone()
                if mapping_row is not None and int(mapping_row[0]) != int(client_id):
                    raise PlatformAccountAlreadyAttachedError(platform=platform, account_id=account_id, existing_client_id=int(mapping_row[0]))

                cur.execute(
                    """
                    INSERT INTO agency_account_client_mappings (platform, account_id, client_id, client_type, account_manager, account_currency)
                    VALUES (
                        %s,
                        %s,
                        %s,
                        (SELECT client_type FROM agency_clients WHERE id = %s),
                        (SELECT account_manager FROM agency_clients WHERE id = %s),
                        COALESCE(
                            NULLIF(TRIM((SELECT currency_code FROM agency_platform_accounts WHERE platform = %s AND account_id = %s)), ''),
                            (SELECT currency FROM agency_clients WHERE id = %s)
                        )
                    )
                    ON CONFLICT(platform, account_id, client_id)
                    DO UPDATE SET
                        account_currency = CASE
                            WHEN agency_account_client_mappings.account_currency IS NULL OR TRIM(agency_account_client_mappings.account_currency) = ''
                                THEN EXCLUDED.account_currency
                            ELSE agency_account_client_mappings.account_currency
                        END,
                        updated_at = NOW()
                    """,
                    (platform, account_id, client_id, client_id, client_id, platform, account_id, client_id),
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

    def list_platform_accounts(self, *, platform: str) -> list[dict[str, object]]:
        if self._is_test_mode():
            with self._lock:
                items = self._memory_platform_accounts.get(platform, {})
                mappings = self._memory_account_client_mappings.get(platform, {})
                clients_by_id = {c.id: c for c in self._clients if c.source == "manual"}
                result: list[dict[str, object]] = []
                for key in sorted(items.keys()):
                    item = dict(items[key])
                    mapped_client_ids = sorted(mappings.get(item["id"], set()))
                    mapped_client = clients_by_id.get(mapped_client_ids[0]) if mapped_client_ids else None
                    account_id = str(item["id"])
                    display_name = str(item.get("name") or account_id)
                    result.append(
                        _normalize_account_sync_metadata_payload(
                            platform=str(platform),
                            account_id=account_id,
                            display_name=display_name,
                            attached_client_id=mapped_client.id if mapped_client else None,
                            attached_client_name=mapped_client.name if mapped_client else None,
                            timezone_value=item.get("account_timezone"),
                            currency_value=item.get("currency_code"),
                            account_status=item.get("status"),
                            sync_start_date=item.get("sync_start_date"),
                            backfill_completed_through=item.get("backfill_completed_through"),
                            rolling_synced_through=item.get("rolling_synced_through"),
                            last_success_at=item.get("last_success_at"),
                            last_error=item.get("last_error"),
                            last_run_status=item.get("last_run_status"),
                            last_run_type=item.get("last_run_type"),
                            last_run_started_at=item.get("last_run_started_at"),
                            last_run_finished_at=item.get("last_run_finished_at"),
                            has_active_sync=bool(item.get("has_active_sync") or False),
                        )
                    )
                return result

        try:
            from app.services.sync_runs_store import sync_runs_store

            sync_runs_store._ensure_schema()
        except Exception:
            pass

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.account_id,
                        a.account_name,
                        m.client_id,
                        c.name,
                        a.account_timezone,
                        a.currency_code,
                        a.status,
                        a.sync_start_date,
                        a.backfill_completed_through,
                        a.rolling_synced_through,
                        a.last_success_at,
                        a.last_error,
                        latest.status,
                        latest.job_type,
                        latest.started_at,
                        latest.finished_at,
                        latest.error,
                        COALESCE(active.has_active_sync, FALSE),
                        hist.min_start_date,
                        hist.max_end_date,
                        roll.max_end_date,
                        success.last_success_at,
                        recovered_hist.min_start_date,
                        recovered_hist.max_end_date,
                        recovered_hist.last_success_at
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
                    LEFT JOIN LATERAL (
                      SELECT
                        sr.status,
                        sr.job_type,
                        sr.started_at,
                        sr.finished_at,
                        sr.error
                      FROM sync_runs sr
                      WHERE sr.platform = a.platform AND sr.account_id = a.account_id
                      ORDER BY sr.created_at DESC
                      LIMIT 1
                    ) latest ON TRUE
                    LEFT JOIN LATERAL (
                      SELECT
                        BOOL_OR(sr.status IN ('queued', 'running', 'pending')) AS has_active_sync
                      FROM sync_runs sr
                      WHERE sr.platform = a.platform AND sr.account_id = a.account_id
                    ) active ON TRUE
                    LEFT JOIN LATERAL (
                      SELECT
                        MIN(sr.date_start) AS min_start_date,
                        MAX(sr.date_end) AS max_end_date
                      FROM sync_runs sr
                      WHERE sr.platform = a.platform
                        AND sr.account_id = a.account_id
                        AND sr.job_type = 'historical_backfill'
                        AND sr.status = 'done'
                    ) hist ON TRUE
                    LEFT JOIN LATERAL (
                      SELECT MAX(sr.date_end) AS max_end_date
                      FROM sync_runs sr
                      WHERE sr.platform = a.platform
                        AND sr.account_id = a.account_id
                        AND sr.job_type = 'rolling_refresh'
                        AND sr.status = 'done'
                    ) roll ON TRUE
                    LEFT JOIN LATERAL (
                      SELECT MAX(sr.finished_at) AS last_success_at
                      FROM sync_runs sr
                      WHERE sr.platform = a.platform
                        AND sr.account_id = a.account_id
                        AND sr.status = 'done'
                    ) success ON TRUE
                    LEFT JOIN LATERAL (
                      SELECT
                        MIN(sr.date_start) AS min_start_date,
                        MAX(sr.date_end) AS max_end_date,
                        MAX(retry_success.last_success_at) AS last_success_at
                      FROM sync_runs sr
                      LEFT JOIN LATERAL (
                        SELECT MAX(rr.finished_at) AS last_success_at
                        FROM sync_runs rr
                        WHERE rr.platform = sr.platform
                          AND rr.account_id = sr.account_id
                          AND rr.job_type = 'historical_backfill'
                          AND rr.status = 'done'
                          AND COALESCE(rr.metadata->>'retry_of_job_id', '') = sr.job_id
                          AND COALESCE(rr.metadata->>'retry_reason', '') = 'failed_chunks'
                      ) retry_success ON TRUE
                      WHERE sr.platform = a.platform
                        AND sr.account_id = a.account_id
                        AND sr.job_type = 'historical_backfill'
                        AND sr.status = 'error'
                        AND EXISTS (
                          SELECT 1
                          FROM sync_run_chunks src
                          WHERE src.job_id = sr.job_id
                            AND src.status IN ('error', 'failed')
                        )
                        AND NOT EXISTS (
                          SELECT 1
                          FROM sync_run_chunks src
                          WHERE src.job_id = sr.job_id
                            AND src.status IN ('error', 'failed')
                            AND NOT EXISTS (
                              SELECT 1
                              FROM sync_runs rr
                              JOIN sync_run_chunks rc
                                ON rc.job_id = rr.job_id
                              WHERE rr.platform = sr.platform
                                AND rr.account_id = sr.account_id
                                AND rr.job_type = 'historical_backfill'
                                AND rr.status = 'done'
                                AND COALESCE(rr.metadata->>'retry_of_job_id', '') = sr.job_id
                                AND COALESCE(rr.metadata->>'retry_reason', '') = 'failed_chunks'
                                AND rc.status IN ('done', 'success', 'completed')
                                AND COALESCE(rc.metadata->>'retry_of_job_id', '') = sr.job_id
                                AND COALESCE(rc.metadata->>'retry_reason', '') = 'failed_chunks'
                                AND rc.date_start = src.date_start
                                AND rc.date_end = src.date_end
                            )
                        )
                    ) recovered_hist ON TRUE
                    WHERE a.platform = %s
                    ORDER BY a.imported_at DESC
                    """,
                    (platform,),
                )
                rows = cur.fetchall()

            result: list[dict[str, object]] = []
            for row in rows:
                account_id = str(row[0])
                display_name = str(row[1]) if row[1] is not None else account_id
                recovered_sync_start_date = _safe_row_value(row, 22)
                recovered_backfill_completed_through = _safe_row_value(row, 23)
                recovered_last_success_at = _safe_row_value(row, 24)

                account_status = _safe_row_value(row, 6)
                explicit_sync_start_date = _safe_row_value(row, 7)
                explicit_backfill_completed_through = _safe_row_value(row, 8)
                explicit_rolling_synced_through = _safe_row_value(row, 9)
                explicit_last_success_at = _safe_row_value(row, 10)
                explicit_last_error = _safe_row_value(row, 11)
                latest_status = _safe_row_value(row, 12)
                latest_error = _safe_row_value(row, 16)
                hist_min_start = _safe_row_value(row, 18)
                hist_max_end = _safe_row_value(row, 19)
                roll_max_end = _safe_row_value(row, 20)
                last_success_from_done = _safe_row_value(row, 21)

                sync_start_date = _coalesce_date_min(explicit_sync_start_date, hist_min_start, recovered_sync_start_date)
                backfill_completed_through = _coalesce_date_max(explicit_backfill_completed_through, hist_max_end, recovered_backfill_completed_through)
                rolling_synced_through = explicit_rolling_synced_through if explicit_rolling_synced_through is not None else roll_max_end
                last_success_at = _coalesce_date_max(explicit_last_success_at, last_success_from_done, recovered_last_success_at)
                last_error = _derive_effective_last_error(explicit_last_error=explicit_last_error, latest_run_error=latest_error, latest_run_status=latest_status)
                if recovered_sync_start_date is not None or recovered_backfill_completed_through is not None:
                    logger.info(
                        "client_registry.recovered_historical_backfill platform=%s account_id=%s sync_start_date=%s backfill_completed_through=%s",
                        platform,
                        account_id,
                        sync_start_date,
                        backfill_completed_through,
                    )
                result.append(
                    _normalize_account_sync_metadata_payload(
                        platform=str(platform),
                        account_id=account_id,
                        display_name=display_name,
                        attached_client_id=int(row[2]) if row[2] is not None else None,
                        attached_client_name=str(row[3]) if row[3] is not None else None,
                        timezone_value=str(row[4]) if row[4] is not None else None,
                        currency_value=str(row[5]) if row[5] is not None else None,
                        account_status=account_status,
                        sync_start_date=sync_start_date,
                        backfill_completed_through=backfill_completed_through,
                        rolling_synced_through=rolling_synced_through,
                        last_success_at=last_success_at,
                        last_error=last_error,
                        last_run_status=_safe_row_value(row, 12),
                        last_run_type=_safe_row_value(row, 13),
                        last_run_started_at=_safe_row_value(row, 14),
                        last_run_finished_at=_safe_row_value(row, 15),
                        has_active_sync=bool(_safe_row_value(row, 17)),
                    )
                )

            account_ids = [str(item.get("account_id") or "") for item in result if item.get("account_id")]
            watermark_by_account = list_platform_account_watermarks(
                conn,
                platform=str(platform),
                account_ids=account_ids,
                grains=["campaign_daily", "ad_group_daily", "ad_daily", "keyword_daily"],
            )
            for item in result:
                account_id = str(item.get("account_id") or "")
                by_grain = watermark_by_account.get(account_id, {})
                item["entity_watermarks"] = {
                    "campaign_daily": _normalize_entity_watermark_payload(by_grain.get("campaign_daily")),
                    "ad_group_daily": _normalize_entity_watermark_payload(by_grain.get("ad_group_daily")),
                    "ad_daily": _normalize_entity_watermark_payload(by_grain.get("ad_daily")),
                    "keyword_daily": _normalize_entity_watermark_payload(by_grain.get("keyword_daily")),
                }
            return result

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
                    if backfill_completed_through is None:
                        existing["backfill_completed_through"] = None
                    else:
                        existing["backfill_completed_through"] = _coalesce_iso_date_max(
                            existing.get("backfill_completed_through"),
                            str(backfill_completed_through),
                        )
                if rolling_synced_through is not _UNSET:
                    if rolling_synced_through is None:
                        existing["rolling_synced_through"] = None
                    else:
                        existing["rolling_synced_through"] = _coalesce_iso_date_max(
                            existing.get("rolling_synced_through"),
                            str(rolling_synced_through),
                        )
                if last_success_at is not _UNSET:
                    if last_success_at is None:
                        existing["last_success_at"] = None
                    else:
                        existing["last_success_at"] = _coalesce_iso_datetime_max(
                            existing.get("last_success_at"),
                            str(last_success_at),
                        )
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

    def list_client_platform_accounts(self, *, platform: str, client_id: int) -> list[dict[str, object]]:
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
                        effective_currency, currency_source = resolve_effective_attached_account_currency(
                            mapping_account_currency=profile.get("account_currency"),
                            platform_account_currency_code=info.get("currency_code") if isinstance(info, dict) else None,
                            client_currency=next((c.currency for c in self._clients if c.id == client_id), "USD"),
                            fallback="USD",
                        )
                        result.append({
                            "id": info["id"],
                            "name": info["name"],
                            "client_type": str(profile.get("client_type", "lead")),
                            "account_manager": str(profile.get("account_manager", "")),
                            "currency": effective_currency,
                            "effective_account_currency": effective_currency,
                            "account_currency_source": currency_source,
                            "mapping_account_currency": profile.get("account_currency"),
                            "platform_account_currency": info.get("currency_code") if isinstance(info, dict) else None,
                        })
                return sorted(result, key=lambda item: item["id"])

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.account_id,
                        a.account_name,
                        m.client_type,
                        m.account_manager,
                        m.account_currency,
                        a.currency_code,
                        c.currency,
                        COALESCE(NULLIF(TRIM(m.account_currency), ''), NULLIF(TRIM(a.currency_code), ''), NULLIF(TRIM(c.currency), ''), 'USD') AS effective_account_currency,
                        CASE
                            WHEN NULLIF(TRIM(m.account_currency), '') IS NOT NULL THEN 'mapping_account_currency'
                            WHEN NULLIF(TRIM(a.currency_code), '') IS NOT NULL THEN 'platform_account_currency'
                            WHEN NULLIF(TRIM(c.currency), '') IS NOT NULL THEN 'client_currency'
                            ELSE 'fallback'
                        END AS account_currency_source
                    FROM agency_account_client_mappings m
                    JOIN agency_platform_accounts a
                      ON a.platform = m.platform AND a.account_id = m.account_id
                    JOIN agency_clients c
                      ON c.id = m.client_id
                    WHERE m.platform = %s AND m.client_id = %s
                    ORDER BY m.updated_at DESC, m.created_at DESC
                    """,
                    (platform, client_id),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(row[0]),
                "name": str(row[1]),
                "client_type": str(row[2]) if row[2] else "lead",
                "account_manager": str(row[3]) if row[3] else "",
                "currency": str(row[7]) if row[7] else "USD",
                "effective_account_currency": str(row[7]) if row[7] else "USD",
                "account_currency_source": str(row[8]) if row[8] else "fallback",
                "mapping_account_currency": str(row[4]) if row[4] else None,
                "platform_account_currency": str(row[5]) if row[5] else None,
                "client_currency": str(row[6]) if row[6] else None,
            }
            for row in rows
        ]

    def list_client_accounts(self, *, client_id: int, platform: str | None = None) -> list[dict[str, object]]:
        target_platforms = [str(platform)] if platform else ["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads", "reddit_ads"]
        rows: list[dict[str, object]] = []
        for platform_name in target_platforms:
            accounts = self.list_client_platform_accounts(platform=platform_name, client_id=client_id)
            for item in accounts:
                account_id = str(item.get("id") or item.get("account_id") or "")
                account_name = str(item.get("name") or item.get("account_name") or account_id)
                rows.append({
                    "platform": platform_name,
                    "account_id": account_id,
                    "account_name": account_name,
                    "id": account_id,
                    "name": account_name,
                    "is_attached": True,
                    "client_type": item.get("client_type"),
                    "account_manager": item.get("account_manager"),
                    "currency": item.get("currency"),
                    "effective_account_currency": item.get("effective_account_currency") or item.get("currency"),
                    "account_currency_source": item.get("account_currency_source"),
                })
        return rows

    def list_platform_accounts_for_mapping(self, *, platform: str) -> list[dict[str, object]]:
        items = self.list_platform_accounts(platform=platform)
        rows: list[dict[str, object]] = []
        for item in items:
            account_id = str(item.get("account_id") or item.get("id") or "")
            account_name = str(item.get("display_name") or item.get("name") or account_id)
            attached_client_id = item.get("attached_client_id")
            rows.append({
                "platform": str(platform),
                "account_id": account_id,
                "account_name": account_name,
                "client_id": int(attached_client_id) if attached_client_id is not None else None,
                "client_name": item.get("attached_client_name"),
                "is_attached": attached_client_id is not None,
                "status": item.get("status"),
                "currency": item.get("currency"),
                "timezone": item.get("timezone"),
                "sync_start_date": item.get("sync_start_date"),
                "backfill_completed_through": item.get("backfill_completed_through"),
                "rolling_synced_through": item.get("rolling_synced_through"),
                "last_success_at": item.get("last_success_at"),
                "last_error": item.get("last_error"),
                "last_run_status": item.get("last_run_status"),
                "last_run_type": item.get("last_run_type"),
                "last_run_started_at": item.get("last_run_started_at"),
                "last_run_finished_at": item.get("last_run_finished_at"),
                "has_active_sync": item.get("has_active_sync"),
            })
        return rows

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


    def get_client_reporting_currency_decision(
        self,
        *,
        client_id: int,
        platforms: tuple[str, ...] = ("google_ads", "meta_ads", "tiktok_ads"),
        safe_fallback: str = "USD",
    ) -> dict[str, object]:
        platform_set = {str(item) for item in platforms}
        attached_accounts = [
            item
            for item in self.list_client_accounts(client_id=client_id)
            if str(item.get("platform") or "") in platform_set
        ]
        attached_effective_currencies = [
            item.get("effective_account_currency") or item.get("currency")
            for item in attached_accounts
        ]

        client_currency = None
        for item in self.list_clients():
            if int(item.get("id") or 0) == int(client_id):
                client_currency = item.get("currency")
                break

        reporting_currency, source, mixed, summary = resolve_client_reporting_currency(
            attached_effective_currencies=attached_effective_currencies,
            client_currency=client_currency,
            fallback=safe_fallback,
        )

        return {
            "reporting_currency": reporting_currency,
            "reporting_currency_source": source,
            "client_display_currency": reporting_currency,
            "display_currency_source": source,
            "mixed_attached_account_currencies": mixed,
            "attached_account_currency_summary": summary,
            "attached_account_count": len(attached_accounts),
            "client_default_currency": str(client_currency or "").strip().upper() or None,
            "platforms_considered": sorted(platform_set),
        }

    def get_preferred_currency_for_client(self, *, client_id: int) -> str:
        decision = self.get_client_reporting_currency_decision(client_id=client_id)
        return str(decision.get("reporting_currency") or "USD")


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
