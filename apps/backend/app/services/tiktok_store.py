from __future__ import annotations

from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class TikTokSnapshotStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memory_snapshots: dict[int, dict[str, float | int | str]] = {}

    def _is_test_mode(self) -> bool:
        settings = load_settings()
        return settings.app_env == "test"

    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _ensure_schema(self) -> None:
        if getattr(self, "_schema_initialized", False):
            return
        if self._is_test_mode():
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(1, hashtext(%s))", ("ensure_schema_" + self.__class__.__name__,))
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tiktok_sync_snapshots (
                        client_id INTEGER PRIMARY KEY,
                        spend NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        impressions INTEGER NOT NULL DEFAULT 0,
                        clicks INTEGER NOT NULL DEFAULT 0,
                        conversions INTEGER NOT NULL DEFAULT 0,
                        revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        attempts INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )
            conn.commit()
        self._schema_initialized = True


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
                    "attempts": int(payload.get("attempts", 1)),
                }
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tiktok_sync_snapshots (
                        client_id, spend, impressions, clicks, conversions, revenue, synced_at, attempts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(client_id) DO UPDATE SET
                        spend=EXCLUDED.spend,
                        impressions=EXCLUDED.impressions,
                        clicks=EXCLUDED.clicks,
                        conversions=EXCLUDED.conversions,
                        revenue=EXCLUDED.revenue,
                        synced_at=EXCLUDED.synced_at,
                        attempts=EXCLUDED.attempts
                    """,
                    (
                        int(payload["client_id"]),
                        float(payload["spend"]),
                        int(payload["impressions"]),
                        int(payload["clicks"]),
                        int(payload["conversions"]),
                        float(payload["revenue"]),
                        str(payload["synced_at"]),
                        int(payload.get("attempts", 1)),
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
                    "platform": "tiktok_ads",
                    "spend": 0.0,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                    "synced_at": "",
                    "attempts": 0,
                    "is_synced": False,
                }
            return {
                "client_id": int(row["client_id"]),
                "platform": "tiktok_ads",
                "spend": float(row["spend"]),
                "impressions": int(row["impressions"]),
                "clicks": int(row["clicks"]),
                "conversions": int(row["conversions"]),
                "revenue": float(row["revenue"]),
                "synced_at": str(row["synced_at"]),
                "attempts": int(row.get("attempts", 1)),
                "is_synced": True,
            }

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT client_id, spend, impressions, clicks, conversions, revenue, synced_at, attempts
                    FROM tiktok_sync_snapshots
                    WHERE client_id = %s
                    """,
                    (client_id,),
                )
                row = cur.fetchone()

        if row is None:
            return {
                "client_id": client_id,
                "platform": "tiktok_ads",
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "synced_at": "",
                "attempts": 0,
                "is_synced": False,
            }

        return {
            "client_id": int(row[0]),
            "platform": "tiktok_ads",
            "spend": float(row[1]),
            "impressions": int(row[2]),
            "clicks": int(row[3]),
            "conversions": int(row[4]),
            "revenue": float(row[5]),
            "synced_at": str(row[6]),
            "attempts": int(row[7]),
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
                cur.execute("DELETE FROM tiktok_sync_snapshots")
            conn.commit()


tiktok_snapshot_store = TikTokSnapshotStore()
