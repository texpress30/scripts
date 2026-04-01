from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutputFeedRepository:
    """Postgres-backed repository for output_feeds and template_render_jobs."""

    def _connect(self):
        from app.db.pool import get_connection

        return get_connection()

    # -- output_feeds -------------------------------------------------------

    def create_output_feed(self, *, subaccount_id: int, name: str, feed_source_id: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO output_feeds (subaccount_id, name, feed_source_id)
                    VALUES (%s, %s, %s)
                    RETURNING id, subaccount_id, name, feed_source_id,
                              status, enriched_feed_url, last_render_at,
                              created_at, updated_at
                    """,
                    (int(subaccount_id), str(name), feed_source_id),
                )
                row = cur.fetchone()
            conn.commit()
        return self._row_to_dict(row)

    def get_by_id(self, output_feed_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, subaccount_id, name, feed_source_id, status, enriched_feed_url, last_render_at, created_at, updated_at FROM output_feeds WHERE id = %s",
                    (str(output_feed_id),),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_by_subaccount(self, subaccount_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, subaccount_id, name, feed_source_id, status, enriched_feed_url, last_render_at, created_at, updated_at FROM output_feeds WHERE subaccount_id = %s ORDER BY updated_at DESC LIMIT %s",
                    (int(subaccount_id), max(0, int(limit))),
                )
                rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update(self, output_feed_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        fields: list[str] = []
        values: list[Any] = []
        for key in ("name", "feed_source_id", "status", "enriched_feed_url", "last_render_at"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if not fields:
            return self.get_by_id(output_feed_id)
        fields.append("updated_at = NOW()")
        values.append(str(output_feed_id))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE output_feeds SET {', '.join(fields)} WHERE id = %s RETURNING id, subaccount_id, name, feed_source_id, status, enriched_feed_url, last_render_at, created_at, updated_at",
                    values,
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            return None
        return self._row_to_dict(row)

    def delete(self, output_feed_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM output_feeds WHERE id = %s", (str(output_feed_id),))
                deleted = cur.rowcount or 0
            conn.commit()
        return deleted > 0

    # -- render jobs --------------------------------------------------------

    def create_render_job(self, *, template_id: str, output_feed_id: str, total_products: int = 0) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO template_render_jobs (template_id, output_feed_id, status, total_products, started_at)
                    VALUES (%s, %s, 'pending', %s, NOW())
                    RETURNING id, template_id, output_feed_id, status, total_products, rendered_products, errors, started_at, completed_at, created_at
                    """,
                    (str(template_id), str(output_feed_id), int(total_products)),
                )
                row = cur.fetchone()
            conn.commit()
        return self._render_job_row_to_dict(row)

    def get_latest_render_job(self, output_feed_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, template_id, output_feed_id, status, total_products, rendered_products, errors, started_at, completed_at, created_at FROM template_render_jobs WHERE output_feed_id = %s ORDER BY created_at DESC LIMIT 1",
                    (str(output_feed_id),),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._render_job_row_to_dict(row)

    # -- helpers ------------------------------------------------------------

    def _row_to_dict(self, row) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "subaccount_id": int(row[1]),
            "name": str(row[2] or ""),
            "feed_source_id": str(row[3]) if row[3] else None,
            "status": str(row[4] or "draft"),
            "enriched_feed_url": str(row[5]) if row[5] else None,
            "last_render_at": row[6].isoformat() if row[6] else None,
            "created_at": row[7].isoformat() if row[7] else "",
            "updated_at": row[8].isoformat() if row[8] else "",
        }

    def _render_job_row_to_dict(self, row) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "template_id": str(row[1] or ""),
            "output_feed_id": str(row[2] or ""),
            "status": str(row[3] or "pending"),
            "total_products": int(row[4] or 0),
            "rendered_products": int(row[5] or 0),
            "errors": row[6] if isinstance(row[6], list) else [],
            "started_at": row[7].isoformat() if row[7] else None,
            "completed_at": row[8].isoformat() if row[8] else None,
            "created_at": row[9].isoformat() if row[9] else "",
        }


output_feed_repository = OutputFeedRepository()


class OutputFeedNotFoundError(Exception):
    def __init__(self, output_feed_id: str) -> None:
        super().__init__(f"Output feed not found: {output_feed_id}")
        self.output_feed_id = output_feed_id


class OutputFeedService:
    def __init__(self, repo=None) -> None:
        self._repo = repo or output_feed_repository

    def create_output_feed(self, subaccount_id: int, name: str, feed_source_id: str | None = None) -> dict[str, Any]:
        return self._repo.create_output_feed(subaccount_id=subaccount_id, name=name, feed_source_id=feed_source_id)

    def get_output_feed(self, output_feed_id: str) -> dict[str, Any]:
        feed = self._repo.get_by_id(output_feed_id)
        if feed is None:
            raise OutputFeedNotFoundError(output_feed_id)
        return feed

    def list_output_feeds(self, subaccount_id: int) -> list[dict[str, Any]]:
        return self._repo.list_by_subaccount(subaccount_id)

    def update_output_feed(self, output_feed_id: str, data: dict[str, Any]) -> dict[str, Any]:
        result = self._repo.update(output_feed_id, data)
        if result is None:
            raise OutputFeedNotFoundError(output_feed_id)
        return result

    def delete_output_feed(self, output_feed_id: str) -> bool:
        return self._repo.delete(output_feed_id)

    def get_enriched_feed_url(self, output_feed_id: str) -> str | None:
        feed = self.get_output_feed(output_feed_id)
        if feed.get("status") != "published":
            return None
        return feed.get("enriched_feed_url")

    def start_render_job(self, output_feed_id: str, template_id: str, total_products: int = 0) -> dict[str, Any]:
        self.get_output_feed(output_feed_id)
        job = self._repo.create_render_job(template_id=template_id, output_feed_id=output_feed_id, total_products=total_products)
        self._repo.update(output_feed_id, {"status": "rendering"})
        return job

    def get_render_status(self, output_feed_id: str) -> dict[str, Any] | None:
        return self._repo.get_latest_render_job(output_feed_id)


output_feed_service = OutputFeedService()
