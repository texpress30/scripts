from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from app.core.config import load_settings


class TikTokSnapshotStore:
    def __init__(self) -> None:
        self._lock = Lock()

    def _db_path(self) -> Path:
        settings = load_settings()
        return Path(settings.tiktok_sync_db_path)

    def _ensure_schema(self) -> None:
        db_path = self._db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tiktok_sync_snapshots (
                    client_id INTEGER PRIMARY KEY,
                    spend REAL NOT NULL,
                    impressions INTEGER NOT NULL,
                    clicks INTEGER NOT NULL,
                    conversions INTEGER NOT NULL,
                    revenue REAL NOT NULL,
                    synced_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_snapshot(self, *, payload: dict[str, float | int | str]) -> None:
        self._ensure_schema()
        with self._lock:
            with sqlite3.connect(self._db_path()) as conn:
                conn.execute(
                    """
                    INSERT INTO tiktok_sync_snapshots (
                        client_id, spend, impressions, clicks, conversions, revenue, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        spend=excluded.spend,
                        impressions=excluded.impressions,
                        clicks=excluded.clicks,
                        conversions=excluded.conversions,
                        revenue=excluded.revenue,
                        synced_at=excluded.synced_at
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
        with self._lock:
            with sqlite3.connect(self._db_path()) as conn:
                row = conn.execute(
                    """
                    SELECT client_id, spend, impressions, clicks, conversions, revenue, synced_at
                    FROM tiktok_sync_snapshots
                    WHERE client_id = ?
                    """,
                    (client_id,),
                ).fetchone()

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
            "is_synced": True,
        }

    def clear(self) -> None:
        self._ensure_schema()
        with self._lock:
            with sqlite3.connect(self._db_path()) as conn:
                conn.execute("DELETE FROM tiktok_sync_snapshots")
                conn.commit()


tiktok_snapshot_store = TikTokSnapshotStore()
