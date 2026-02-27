from __future__ import annotations

from dataclasses import dataclass
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
    source: str = "manual"


class ClientRegistryService:
    def __init__(self) -> None:
        self._clients: list[ClientRecord] = []
        self._next_id = 1
        self._lock = Lock()
        self._memory_platform_accounts: dict[str, dict[str, dict[str, str]]] = {}
        self._memory_last_import_at: dict[str, str] = {}
        self._memory_account_client_mappings: dict[str, dict[str, int]] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for client registry Postgres persistence")
        return psycopg.connect(settings.database_url)

    def _connect_or_raise(self):
        conn = self._connect()
        return conn

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
                        UNIQUE(platform, account_id),
                        FOREIGN KEY (platform, account_id) REFERENCES agency_platform_accounts(platform, account_id) ON DELETE CASCADE,
                        FOREIGN KEY (client_id) REFERENCES agency_clients(id) ON DELETE CASCADE
                    )
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
                # Backfill old one-to-one google_customer_id into mapping table.
                cur.execute(
                    """
                    INSERT INTO agency_account_client_mappings (platform, account_id, client_id)
                    SELECT 'google_ads', c.google_customer_id, c.id
                    FROM agency_clients c
                    WHERE c.google_customer_id IS NOT NULL
                      AND c.source = 'manual'
                      AND EXISTS (
                        SELECT 1
                        FROM agency_platform_accounts a
                        WHERE a.platform = 'google_ads' AND a.account_id = c.google_customer_id
                      )
                    ON CONFLICT(platform, account_id)
                    DO UPDATE SET client_id = EXCLUDED.client_id, updated_at = NOW()
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
                manual_count = len([c for c in self._clients if c.source == "manual"])
                return {
                    "id": record.id,
                    "display_id": manual_count,
                    "name": record.name,
                    "owner_email": record.owner_email,
                    "google_customer_id": self.get_google_customer_for_client(client_id=record.id),
                }

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agency_clients (name, owner_email, source)
                    VALUES (%s, %s, 'manual')
                    RETURNING id, name, owner_email
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
                    "google_customer_id": self.get_google_customer_for_client(client_id=c.id),
                }
            )
        return records

    def list_clients(self) -> list[dict[str, str | int | None]]:
        self._ensure_schema()

        if self._is_test_mode():
            with self._lock:
                return self._list_clients_test()

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.name, c.owner_email,
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
                "display_id": int(row[3]),
                "google_customer_id": str(row[4]) if row[4] else None,
            }
            for row in rows
        ]

    def _client_exists_test(self, *, client_id: int) -> bool:
        return any(c.id == client_id and c.source == "manual" for c in self._clients)

    def attach_platform_account_to_client(self, *, platform: str, client_id: int, account_id: str) -> dict[str, str | int | None] | None:
        self._ensure_schema()
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
                mappings[account_id] = client_id
                client = next(c for c in self._clients if c.id == client_id)
                return {
                    "id": client.id,
                    "name": client.name,
                    "owner_email": client.owner_email,
                    "google_customer_id": self.get_google_customer_for_client(client_id=client.id),
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
                    INSERT INTO agency_account_client_mappings (platform, account_id, client_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(platform, account_id)
                    DO UPDATE SET client_id = EXCLUDED.client_id, updated_at = NOW()
                    """,
                    (platform, account_id, client_id),
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
        self._ensure_schema()
        account_id = str(account_id).strip()
        if account_id == "":
            return False

        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.setdefault(platform, {})
                if mappings.get(account_id) != client_id:
                    return False
                del mappings[account_id]
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

    def get_google_customer_for_client(self, *, client_id: int) -> str | None:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get("google_ads", {})
                for account_id, mapped_client_id in mappings.items():
                    if mapped_client_id == client_id:
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
        self._ensure_schema()
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
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                items = self._memory_platform_accounts.get(platform, {})
                mappings = self._memory_account_client_mappings.get(platform, {})
                clients_by_id = {c.id: c for c in self._clients if c.source == "manual"}
                result: list[dict[str, str | int | None]] = []
                for key in sorted(items.keys()):
                    item = dict(items[key])
                    mapped_client_id = mappings.get(item["id"])
                    mapped_client = clients_by_id.get(mapped_client_id) if mapped_client_id else None
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
                    LEFT JOIN agency_account_client_mappings m
                      ON m.platform = a.platform AND m.account_id = a.account_id
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

    def list_client_platform_accounts(self, *, platform: str, client_id: int) -> list[dict[str, str]]:
        self._ensure_schema()
        if self._is_test_mode():
            with self._lock:
                mappings = self._memory_account_client_mappings.get(platform, {})
                accounts = self._memory_platform_accounts.get(platform, {})
                result: list[dict[str, str]] = []
                for account_id, mapped_client_id in mappings.items():
                    if mapped_client_id != client_id:
                        continue
                    info = accounts.get(account_id)
                    if info:
                        result.append({"id": info["id"], "name": info["name"]})
                return sorted(result, key=lambda item: item["id"])

        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.account_id, a.account_name
                    FROM agency_account_client_mappings m
                    JOIN agency_platform_accounts a
                      ON a.platform = m.platform AND a.account_id = m.account_id
                    WHERE m.platform = %s AND m.client_id = %s
                    ORDER BY m.updated_at DESC, m.created_at DESC
                    """,
                    (platform, client_id),
                )
                rows = cur.fetchall()
        return [{"id": str(row[0]), "name": str(row[1])} for row in rows]

    def get_last_import_at(self, *, platform: str) -> str | None:
        self._ensure_schema()
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
        self._ensure_schema()
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
        self._ensure_schema()
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


    def clear(self) -> None:
        if self._is_test_mode():
            with self._lock:
                self._clients.clear()
                self._next_id = 1
                self._memory_platform_accounts.clear()
                self._memory_last_import_at.clear()
                self._memory_account_client_mappings.clear()
            return

        self._ensure_schema()
        with self._connect_or_raise() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agency_account_client_mappings")
                cur.execute("DELETE FROM agency_clients")
                cur.execute("DELETE FROM agency_platform_accounts")
                cur.execute("DELETE FROM agency_platform_imports")
            conn.commit()


client_registry_service = ClientRegistryService()
