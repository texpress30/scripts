from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


@dataclass
class ClientRecord:
    id: int
    name: str
    owner_email: str
    google_customer_id: str | None = None
    source: str = "manual"


class ClientRegistryService:
    def __init__(self) -> None:
        self._clients: list[ClientRecord] = []
        self._next_id = 1
        self._lock = Lock()
        self._memory_platform_accounts: dict[str, dict[str, dict[str, str]]] = {}
        self._memory_last_import_at: dict[str, str] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for client registry Postgres persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._is_test_mode():
            return

        with self._connect() as conn:
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
                # Legacy cleanup: mark only obvious old synthetic imports as imported.
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

    def create_client(self, name: str, owner_email: str) -> dict[str, str | int | None]:
        self._ensure_schema()

        if self._is_test_mode():
            with self._lock:
                record = ClientRecord(id=self._next_id, name=name, owner_email=owner_email, source="manual")
                self._next_id += 1
                self._clients.append(record)
                payload = asdict(record)
                payload.pop("source", None)
                return payload

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agency_clients (name, owner_email, source)
                    VALUES (%s, %s, 'manual')
                    RETURNING id, name, owner_email, google_customer_id
                    """,
                    (name, owner_email),
                )
                row = cur.fetchone()
            conn.commit()

        return {
            "id": int(row[0]),
            "name": str(row[1]),
            "owner_email": str(row[2]),
            "google_customer_id": str(row[3]) if row[3] else None,
        }

    def list_clients(self) -> list[dict[str, str | int | None]]:
        self._ensure_schema()

        if self._is_test_mode():
            with self._lock:
                return [
                    {
                        "id": c.id,
                        "name": c.name,
                        "owner_email": c.owner_email,
                        "google_customer_id": c.google_customer_id,
                    }
                    for c in self._clients
                    if c.source == "manual"
                ]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, owner_email, google_customer_id
                    FROM agency_clients
                    WHERE source = 'manual'
                    ORDER BY id ASC
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "id": int(row[0]),
                "name": str(row[1]),
                "owner_email": str(row[2]),
                "google_customer_id": str(row[3]) if row[3] else None,
            }
            for row in rows
        ]

    def assign_google_customer(self, *, client_id: int, customer_id: str) -> dict[str, str | int | None] | None:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                for idx, client in enumerate(self._clients):
                    if client.id == client_id and client.source == "manual":
                        updated = ClientRecord(
                            id=client.id,
                            name=client.name,
                            owner_email=client.owner_email,
                            google_customer_id=customer_id,
                            source=client.source,
                        )
                        self._clients[idx] = updated
                        payload = asdict(updated)
                        payload.pop("source", None)
                        return payload
            return None

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agency_clients
                    SET google_customer_id = %s, updated_at = NOW()
                    WHERE id = %s AND source = 'manual'
                    RETURNING id, name, owner_email, google_customer_id
                    """,
                    (customer_id, client_id),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            return None
        return {
            "id": int(row[0]),
            "name": str(row[1]),
            "owner_email": str(row[2]),
            "google_customer_id": str(row[3]) if row[3] else None,
        }

    def get_google_customer_for_client(self, *, client_id: int) -> str | None:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                for client in self._clients:
                    if client.id == client_id and client.source == "manual":
                        return client.google_customer_id
            return None

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT google_customer_id FROM agency_clients WHERE id = %s AND source = 'manual'", (client_id,))
                row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return str(row[0])

    def upsert_platform_accounts(self, *, platform: str, accounts: list[dict[str, str]]) -> None:
        self._ensure_schema()
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._is_test_mode():
            with self._lock:
                platform_items = self._memory_platform_accounts.setdefault(platform, {})
                for account in accounts:
                    platform_items[str(account["id"])] = {"id": str(account["id"]), "name": str(account["name"])}
                self._memory_last_import_at[platform] = now_iso
            return

        with self._connect() as conn:
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

    def list_platform_accounts(self, *, platform: str) -> list[dict[str, str]]:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                items = self._memory_platform_accounts.get(platform, {})
                return [items[key] for key in sorted(items.keys())]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT account_id, account_name FROM agency_platform_accounts WHERE platform = %s ORDER BY imported_at DESC",
                    (platform,),
                )
                rows = cur.fetchall()
        return [{"id": str(row[0]), "name": str(row[1])} for row in rows]

    def get_last_import_at(self, *, platform: str) -> str | None:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                return self._memory_last_import_at.get(platform)

        with self._connect() as conn:
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

    def clear(self) -> None:
        if self._is_test_mode():
            with self._lock:
                self._clients.clear()
                self._next_id = 1
                self._memory_platform_accounts.clear()
                self._memory_last_import_at.clear()
            return

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agency_clients")
                cur.execute("DELETE FROM agency_platform_accounts")
                cur.execute("DELETE FROM agency_platform_imports")
            conn.commit()


client_registry_service = ClientRegistryService()
