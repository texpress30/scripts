from __future__ import annotations

from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class MetaSnapshotStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memory_snapshots: dict[int, dict[str, float | int | str]] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for Meta Postgres persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        settings = load_settings()
        if settings.app_env == "production":
            if hasattr(self, "_schema_initialized"):
                self._schema_initialized = True
            return
        if self._is_test_mode():
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS meta_sync_snapshots (
                        client_id INTEGER PRIMARY KEY,
                        spend NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        impressions INTEGER NOT NULL DEFAULT 0,
                        clicks INTEGER NOT NULL DEFAULT 0,
                        conversions INTEGER NOT NULL DEFAULT 0,
                        revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def upsert_snapshot(self, *, payload: dict[str, float | int | str]) -> None:
        self._ensure_schema()

        if self._is_test_mode():
            with self._lock:
                self._memory_snapshots[int(payload["client_id"])] = {
                    "client_id": int(payload["client_id"]),
                    "spend": float(payload["spend"]),
                    "impressions": int(payload["impressions"]),
                    "clicks": int(payload["clicks"]),
                    "conversions": int(payload["conversions"]),
                    "revenue": float(payload["revenue"]),
                    "synced_at": str(payload["synced_at"]),
                }
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meta_sync_snapshots (
                        client_id, spend, impressions, clicks, conversions, revenue, synced_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(client_id) DO UPDATE SET
                        spend=EXCLUDED.spend,
                        impressions=EXCLUDED.impressions,
                        clicks=EXCLUDED.clicks,
                        conversions=EXCLUDED.conversions,
                        revenue=EXCLUDED.revenue,
                        synced_at=EXCLUDED.synced_at
                    """,
                    (
                        int(payload["client_id"]),
                        float(payload["spend"]),
                        int(payload["impressions"]),
                        int(payload["clicks"]),
                        int(payload["conversions"]),
                        float(payload["revenue"]),
                        str(payload["synced_at"]),
                    ),
                )
            conn.commit()

    def get_snapshot(self, *, client_id: int) -> dict[str, float | int | str | bool]:
        self._ensure_schema()

        if self._is_test_mode():
            with self._lock:
                row = self._memory_snapshots.get(client_id)
            if row is None:
                return {
                    "client_id": client_id,
                    "platform": "meta_ads",
                    "spend": 0.0,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                    "synced_at": "",
                    "is_synced": False,
                }
            return {
                "client_id": int(row["client_id"]),
                "platform": "meta_ads",
                "spend": float(row["spend"]),
                "impressions": int(row["impressions"]),
                "clicks": int(row["clicks"]),
                "conversions": int(row["conversions"]),
                "revenue": float(row["revenue"]),
                "synced_at": str(row["synced_at"]),
                "is_synced": True,
            }

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT client_id, spend, impressions, clicks, conversions, revenue, synced_at
                    FROM meta_sync_snapshots
                    WHERE client_id = %s
                    """,
                    (client_id,),
                )
                row = cur.fetchone()

        if row is None:
            return {
                "client_id": client_id,
                "platform": "meta_ads",
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "synced_at": "",
                "is_synced": False,
            }

        return {
            "client_id": int(row[0]),
            "platform": "meta_ads",
            "spend": float(row[1]),
            "impressions": int(row[2]),
            "clicks": int(row[3]),
            "conversions": int(row[4]),
            "revenue": float(row[5]),
            "synced_at": str(row[6]),
            "is_synced": True,
        }

    def clear(self) -> None:
        if self._is_test_mode():
            with self._lock:
                self._memory_snapshots.clear()
            return

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM meta_sync_snapshots")
            conn.commit()


meta_snapshot_store = MetaSnapshotStore()
