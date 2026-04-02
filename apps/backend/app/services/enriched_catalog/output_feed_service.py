from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_MAX_PRODUCTS_WARNING = 100_000
_MAX_PRODUCTS_LIMIT = 1_000_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_token() -> str:
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FeedGenerationResult:
    output_feed_id: str
    products_count: int
    file_size_bytes: int
    s3_key: str
    public_url: str
    format: str
    generated_at: str


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class OutputFeedRepository:
    """Postgres-backed repository for output_feeds and template_render_jobs."""

    def _connect(self):
        from app.db.pool import get_connection

        return get_connection()

    # -- output_feeds -------------------------------------------------------

    _SELECT_COLS = (
        "id, subaccount_id, name, feed_source_id, status, enriched_feed_url, "
        "last_render_at, created_at, updated_at, "
        "feed_format, public_token, refresh_interval_hours, "
        "last_generated_at, products_count, file_size_bytes, "
        "field_mapping_id, s3_key"
    )

    def create_output_feed(
        self,
        *,
        subaccount_id: int,
        name: str,
        feed_source_id: str | None = None,
        feed_format: str = "xml",
        field_mapping_id: str | None = None,
    ) -> dict[str, Any]:
        token = _generate_token()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO output_feeds
                        (subaccount_id, name, feed_source_id, feed_format,
                         field_mapping_id, public_token)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING {self._SELECT_COLS}
                    """,
                    (
                        int(subaccount_id),
                        str(name),
                        feed_source_id,
                        feed_format,
                        field_mapping_id,
                        token,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return self._row_to_dict(row)

    def get_by_id(self, output_feed_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._SELECT_COLS} FROM output_feeds WHERE id = %s",
                    (str(output_feed_id),),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def get_by_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._SELECT_COLS} FROM output_feeds WHERE public_token = %s",
                    (str(token),),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_by_subaccount(self, subaccount_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._SELECT_COLS} FROM output_feeds WHERE subaccount_id = %s ORDER BY updated_at DESC LIMIT %s",
                    (int(subaccount_id), max(0, int(limit))),
                )
                rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update(self, output_feed_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        allowed = (
            "name", "feed_source_id", "status", "enriched_feed_url",
            "last_render_at", "feed_format", "public_token",
            "refresh_interval_hours", "last_generated_at",
            "products_count", "file_size_bytes", "field_mapping_id", "s3_key",
        )
        fields: list[str] = []
        values: list[Any] = []
        for key in allowed:
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
                    f"UPDATE output_feeds SET {', '.join(fields)} WHERE id = %s RETURNING {self._SELECT_COLS}",
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

    def list_due_for_refresh(self) -> list[dict[str, Any]]:
        """Return feeds whose last_generated_at + refresh_interval has elapsed."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {self._SELECT_COLS}
                    FROM output_feeds
                    WHERE status = 'published'
                      AND refresh_interval_hours > 0
                      AND (
                          last_generated_at IS NULL
                          OR last_generated_at + (refresh_interval_hours || ' hours')::interval < NOW()
                      )
                    ORDER BY last_generated_at ASC NULLS FIRST
                    """,
                )
                rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

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
            "feed_format": str(row[9] or "xml"),
            "public_token": str(row[10]) if row[10] else None,
            "refresh_interval_hours": int(row[11]) if row[11] is not None else 24,
            "last_generated_at": row[12].isoformat() if row[12] else None,
            "products_count": int(row[13] or 0),
            "file_size_bytes": int(row[14] or 0),
            "field_mapping_id": str(row[15]) if row[15] else None,
            "s3_key": str(row[16]) if row[16] else None,
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


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OutputFeedNotFoundError(Exception):
    def __init__(self, output_feed_id: str) -> None:
        super().__init__(f"Output feed not found: {output_feed_id}")
        self.output_feed_id = output_feed_id


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class OutputFeedService:
    def __init__(self, repo=None) -> None:
        self._repo = repo or output_feed_repository

    # -- Basic CRUD --------------------------------------------------------

    def create_output_feed(
        self,
        subaccount_id: int,
        name: str,
        feed_source_id: str | None = None,
        feed_format: str = "xml",
        field_mapping_id: str | None = None,
    ) -> dict[str, Any]:
        return self._repo.create_output_feed(
            subaccount_id=subaccount_id,
            name=name,
            feed_source_id=feed_source_id,
            feed_format=feed_format,
            field_mapping_id=field_mapping_id,
        )

    def get_output_feed(self, output_feed_id: str) -> dict[str, Any]:
        feed = self._repo.get_by_id(output_feed_id)
        if feed is None:
            raise OutputFeedNotFoundError(output_feed_id)
        return feed

    def get_output_feed_by_token(self, token: str) -> dict[str, Any] | None:
        return self._repo.get_by_token(token)

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

    # -- Render jobs -------------------------------------------------------

    def start_render_job(self, output_feed_id: str, template_id: str, total_products: int = 0) -> dict[str, Any]:
        self.get_output_feed(output_feed_id)
        job = self._repo.create_render_job(template_id=template_id, output_feed_id=output_feed_id, total_products=total_products)
        self._repo.update(output_feed_id, {"status": "rendering"})
        return job

    def get_render_status(self, output_feed_id: str) -> dict[str, Any] | None:
        return self._repo.get_latest_render_job(output_feed_id)

    # -- Feed generation ---------------------------------------------------

    def generate_feed(self, output_feed_id: str) -> FeedGenerationResult:
        """Full feed generation pipeline: fetch products, apply mapping, format, upload to S3."""
        feed = self.get_output_feed(output_feed_id)
        feed_source_id = feed.get("feed_source_id")
        field_mapping_id = feed.get("field_mapping_id")
        feed_format = feed.get("feed_format", "xml")
        subaccount_id = feed["subaccount_id"]

        # 1. Fetch products from MongoDB
        products = self._fetch_products(feed_source_id)
        if len(products) > _MAX_PRODUCTS_WARNING:
            logger.warning(
                "Feed %s has %d products (warning threshold: %d)",
                output_feed_id, len(products), _MAX_PRODUCTS_WARNING,
            )
        if len(products) > _MAX_PRODUCTS_LIMIT:
            logger.error(
                "Feed %s exceeds max product limit (%d > %d), truncating",
                output_feed_id, len(products), _MAX_PRODUCTS_LIMIT,
            )
            products = products[:_MAX_PRODUCTS_LIMIT]

        # 2. Apply field mapping transformations
        if field_mapping_id:
            products = self._apply_field_mapping(products, field_mapping_id)

        # 3. Format feed
        content = self._format_feed(products, feed_format, feed)

        # 4. Upload to S3
        ext = self._format_extension(feed_format)
        s3_key = f"feeds/{subaccount_id}/{output_feed_id}/feed.{ext}"
        content_type = self._content_type_for_format(feed_format)
        self._upload_to_s3(s3_key, content, content_type)

        # 5. Update metadata
        now = _utcnow()
        self._repo.update(output_feed_id, {
            "status": "published",
            "products_count": len(products),
            "file_size_bytes": len(content.encode("utf-8")),
            "last_generated_at": now,
            "s3_key": s3_key,
        })

        public_url = self.get_public_url(output_feed_id)
        return FeedGenerationResult(
            output_feed_id=output_feed_id,
            products_count=len(products),
            file_size_bytes=len(content.encode("utf-8")),
            s3_key=s3_key,
            public_url=public_url,
            format=feed_format,
            generated_at=now.isoformat(),
        )

    def get_public_url(self, output_feed_id: str) -> str:
        """Return the public URL for the given output feed."""
        feed = self.get_output_feed(output_feed_id)
        token = feed.get("public_token", "")
        ext = self._format_extension(feed.get("feed_format", "xml"))
        return f"https://api.omarosa.ro/feeds/{token}.{ext}"

    def regenerate_token(self, output_feed_id: str) -> str:
        """Generate a new public token, invalidating the old URL."""
        new_token = _generate_token()
        self._repo.update(output_feed_id, {"public_token": new_token})
        return new_token

    def schedule_refresh(self, output_feed_id: str, hours: int) -> dict[str, Any]:
        """Set the refresh interval for a feed."""
        return self.update_output_feed(output_feed_id, {"refresh_interval_hours": max(1, hours)})

    def get_feed_stats(self, output_feed_id: str) -> dict[str, Any]:
        """Return generation statistics for a feed."""
        feed = self.get_output_feed(output_feed_id)
        return {
            "output_feed_id": output_feed_id,
            "products_count": feed.get("products_count", 0),
            "file_size_bytes": feed.get("file_size_bytes", 0),
            "last_generated_at": feed.get("last_generated_at"),
            "feed_format": feed.get("feed_format", "xml"),
            "refresh_interval_hours": feed.get("refresh_interval_hours", 24),
            "status": feed.get("status", "draft"),
            "s3_key": feed.get("s3_key"),
        }

    # -- Internal helpers --------------------------------------------------

    def _fetch_products(self, feed_source_id: str | None) -> list[dict[str, Any]]:
        """Load all products for the given feed source from MongoDB."""
        if not feed_source_id:
            return []
        from app.services.feed_management.products_repository import feed_products_repository

        raw = feed_products_repository.list_products(feed_source_id, limit=200)
        # For large feeds we need to paginate through all products
        all_products: list[dict[str, Any]] = []
        skip = 0
        batch_size = 200
        while True:
            batch = feed_products_repository.list_products(feed_source_id, skip=skip, limit=batch_size)
            if not batch:
                break
            for doc in batch:
                data = doc.get("data", doc)
                all_products.append(data)
            if len(batch) < batch_size:
                break
            skip += batch_size
        return all_products

    def _apply_field_mapping(
        self,
        products: list[dict[str, Any]],
        field_mapping_id: str,
    ) -> list[dict[str, Any]]:
        """Apply field mapping rules to each product."""
        from app.services.feed_management.field_mapping.repository import FieldMappingRepository
        from app.services.feed_management.field_mapping.transformer import field_transformer

        repo = FieldMappingRepository()
        mapping = repo.get_by_id(field_mapping_id)
        rules = mapping.rules
        return [field_transformer.apply_mapping(product, rules) for product in products]

    def _format_feed(
        self,
        products: list[dict[str, Any]],
        feed_format: str,
        feed: dict[str, Any],
    ) -> str:
        from app.services.enriched_catalog.feed_formatter import feed_formatter

        if feed_format == "google_shopping_xml":
            return feed_formatter.format_google_shopping_xml(products)
        if feed_format == "meta_csv":
            catalog_type = "product"  # Could be derived from feed_source catalog_type
            return feed_formatter.format_meta_catalog_csv(products, catalog_type)
        if feed_format == "json":
            return feed_formatter.format_as_json(products)
        if feed_format == "csv":
            return feed_formatter.format_as_csv(products)
        # Default: XML
        return feed_formatter.format_as_xml(products)

    def _upload_to_s3(self, s3_key: str, content: str, content_type: str) -> None:
        from app.services.s3_provider import get_s3_client, get_s3_bucket_name

        client = get_s3_client()
        bucket = get_s3_bucket_name()
        client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
            CacheControl="public, max-age=3600",
        )

    @staticmethod
    def _format_extension(feed_format: str) -> str:
        extensions = {
            "xml": "xml",
            "json": "json",
            "csv": "csv",
            "google_shopping_xml": "xml",
            "meta_csv": "csv",
        }
        return extensions.get(feed_format, "xml")

    @staticmethod
    def _content_type_for_format(feed_format: str) -> str:
        types = {
            "xml": "application/xml; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "csv": "text/csv; charset=utf-8",
            "google_shopping_xml": "application/rss+xml; charset=utf-8",
            "meta_csv": "text/csv; charset=utf-8",
        }
        return types.get(feed_format, "application/xml; charset=utf-8")


output_feed_service = OutputFeedService()
