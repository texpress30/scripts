"""Public feed endpoints — NO AUTHENTICATION.

These endpoints are designed for Google/Meta crawlers to access feed data.
Access is controlled via unique 64-char hex tokens per feed.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.services.enriched_catalog.output_feed_service import output_feed_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feeds", tags=["public-feeds"])

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter: 100 req/min per token
# ---------------------------------------------------------------------------

_RATE_LIMIT = 100
_RATE_WINDOW = 60  # seconds
_rate_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(token: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    hits = _rate_log[token]
    # Prune old entries
    _rate_log[token] = [t for t in hits if t > window_start]
    if len(_rate_log[token]) >= _RATE_LIMIT:
        return False
    _rate_log[token].append(now)
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT_TYPES = {
    "xml": "application/xml; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


def _parse_token_and_ext(filename: str) -> tuple[str, str]:
    """Split 'abcdef1234.xml' into ('abcdef1234', 'xml')."""
    if "." not in filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid feed URL")
    token, ext = filename.rsplit(".", 1)
    ext = ext.lower()
    if ext not in ("xml", "json", "csv"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported format")
    if not token or len(token) != 64:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
    return token, ext


def _lookup_feed_by_token(token: str) -> dict | None:
    """Look up a feed by token — tries output feeds first, then channels."""
    feed = output_feed_service.get_output_feed_by_token(token)
    if feed is not None:
        return {
            "s3_key": feed.get("s3_key"),
            "last_generated_at": feed.get("last_generated_at", ""),
            "products_count": feed.get("products_count", 0),
        }

    # Fallback: try feed channels
    from app.services.feed_management.channels.repository import feed_channel_repository

    channel = feed_channel_repository.get_by_token(token)
    if channel is not None:
        return {
            "s3_key": channel.s3_key,
            "last_generated_at": str(channel.last_generated_at) if channel.last_generated_at else "",
            "products_count": channel.included_products,
        }

    return None


def _serve_feed(token: str, requested_ext: str) -> Response:
    """Core handler: look up feed by token, stream content from S3."""
    if not _check_rate_limit(token):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Max 100 requests per minute.",
        )

    feed = _lookup_feed_by_token(token)
    if feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")

    s3_key = feed.get("s3_key")
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed has not been generated yet",
        )

    # Stream the feed content from S3
    from app.services.s3_provider import get_s3_client, get_s3_bucket_name

    try:
        client = get_s3_client()
        bucket = get_s3_bucket_name()
        obj = client.get_object(Bucket=bucket, Key=s3_key)
        body = obj["Body"].read()
    except Exception:
        logger.exception("Failed to read feed from S3: %s", s3_key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve feed content",
        )

    content_type = _CONTENT_TYPES.get(requested_ext, "application/octet-stream")
    last_generated = feed.get("last_generated_at", "")

    headers = {
        "Cache-Control": "public, max-age=3600",
        "X-Products-Count": str(feed.get("products_count", 0)),
    }
    if last_generated:
        headers["Last-Modified"] = str(last_generated)
        headers["ETag"] = f'"{token[:16]}-{last_generated}"'

    return Response(
        content=body,
        media_type=content_type,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{filename}")
def get_public_feed(filename: str) -> Response:
    """Serve a feed file by token.

    URL format: /feeds/{token}.{xml|json|csv}
    No authentication required — designed for crawler access.
    """
    token, ext = _parse_token_and_ext(filename)
    return _serve_feed(token, ext)
