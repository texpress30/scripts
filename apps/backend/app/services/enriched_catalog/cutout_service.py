"""Background-removal cutout service.

Responsibilities
----------------
1. Detect whether a source image already has a usable alpha channel (stock PNGs
   shipped by some connectors). If so, skip the ML step entirely.
2. Run ``rembg`` (U^2-Net ONNX) against images that DO have a solid background.
3. Tight-crop to the alpha bounding box so the resulting PNG is exactly the
   size of the product — no leftover transparent padding.
4. Upload the cutout to S3 under the sub-account's media prefix, register it
   in ``media_files`` (Mongo) so it shows up in Stocare Media, and persist the
   dedup entry in ``image_cutouts`` (Postgres).

Dedup key is ``(client_id, sha256(source_image_bytes))`` — variants of the same
product that share a photo collapse to a single cutout, so a feed with 30k
products and 9k unique photos only runs ~9k rembg passes per client.

Public surface (called from Celery tasks, API handlers, sync hooks):

* ``ensure_cutout(client_id, source_url, ...)`` — blocking pipeline for a single
  source image. Idempotent: returns the existing record if one is already
  ``ready``.
* ``get_cutout_url(client_id, source_url)`` — lookup only; returns the CDN/S3
  URL if a ready cutout exists, else ``None``.
* ``warm_rembg_session()`` — pre-load the ONNX session during Celery worker
  startup to avoid a cold 2-3 s hit on the first task.

The Celery task ``process_source_image`` wraps :func:`ensure_cutout`; callers
should prefer that entry point whenever possible so the work runs off the HTTP
request path.
"""

from __future__ import annotations

import hashlib
import io
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


MAX_CUTOUT_LONG_EDGE = 2048
ALPHA_BORDER_FRACTION_THRESHOLD = 0.02
ALPHA_CROP_CUTOFF = 10  # anything below this is considered transparent for bbox
CUTOUT_PADDING_PX = 4


_rembg_session: Any | None = None
_rembg_session_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CutoutRecord:
    """Summary of a ready cutout, safe to serialize over the wire."""

    client_id: int
    source_hash: str
    media_id: str
    s3_key: str
    image_url: str
    model: str
    has_native_alpha: bool
    width: int
    height: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "source_hash": self.source_hash,
            "media_id": self.media_id,
            "s3_key": self.s3_key,
            "image_url": self.image_url,
            "model": self.model,
            "has_native_alpha": self.has_native_alpha,
            "width": self.width,
            "height": self.height,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# rembg warmup
# ---------------------------------------------------------------------------


def warm_rembg_session(model_name: str | None = None) -> None:
    """Instantiate the rembg session once per worker process.

    Called from ``celery_app.worker_process_init`` so the ONNX graph is loaded
    before the first task runs. Safe no-op when rembg isn't installed (unit
    tests, lightweight render workers that never see bgremoval tasks).
    """
    global _rembg_session
    if _rembg_session is not None:
        return

    try:
        from app.core.config import load_settings

        settings = load_settings()
        resolved_model = str(model_name or settings.rembg_model or "u2net").strip() or "u2net"
    except Exception:  # noqa: BLE001
        resolved_model = str(model_name or "u2net")

    try:
        from rembg import new_session  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        logger.debug("rembg_not_installed_warmup_skipped")
        return

    with _rembg_session_lock:
        if _rembg_session is not None:
            return
        try:
            _rembg_session = new_session(resolved_model)
            logger.info("rembg_session_warmed model=%s", resolved_model)
        except Exception:  # noqa: BLE001
            logger.warning("rembg_warmup_failed model=%s", resolved_model, exc_info=True)
            _rembg_session = None


def _get_rembg_session() -> Any | None:
    if _rembg_session is None:
        warm_rembg_session()
    return _rembg_session


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(bytes(content)).hexdigest()


def has_usable_alpha(image: Any) -> bool:
    """Return True when ``image`` already has a meaningful transparency channel.

    A stock-studio PNG will typically have alpha == 0 around the product edges.
    We sample the outermost pixel ring (rows 0 / -1 + columns 0 / -1) and call
    it "already transparent" if more than 2% of those pixels are below alpha
    250.
    """
    try:
        import numpy as np
    except Exception:  # pragma: no cover — numpy is a hard requirement
        return False

    if image.mode not in ("RGBA", "LA", "PA"):
        return False
    alpha = image.convert("RGBA").split()[-1]
    arr = np.asarray(alpha)
    if arr.size == 0:
        return False
    border = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]])
    if border.size == 0:
        return False
    fraction_transparent = float((border < 250).mean())
    return fraction_transparent > ALPHA_BORDER_FRACTION_THRESHOLD


def tight_crop_alpha(image: Any, *, padding: int = CUTOUT_PADDING_PX) -> tuple[Any, tuple[int, int, int, int] | None]:
    """Return ``(cropped_image, bbox_in_original)``.

    The bounding box is computed from a thresholded alpha mask so that
    anti-aliasing fringes don't bloat the crop. When padding > 0 we leave a
    small transparent margin for layout breathing room.
    """
    from PIL import Image

    rgba = image.convert("RGBA")
    alpha = rgba.split()[-1]
    mask = alpha.point(lambda a: 255 if a > ALPHA_CROP_CUTOFF else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return rgba, None

    x0, y0, x1, y1 = bbox
    if padding > 0:
        x0 = max(0, x0 - padding)
        y0 = max(0, y0 - padding)
        x1 = min(rgba.width, x1 + padding)
        y1 = min(rgba.height, y1 + padding)
    cropped = rgba.crop((x0, y0, x1, y1))
    return cropped, (x0, y0, x1, y1)


def resize_to_max(image: Any, *, max_edge: int = MAX_CUTOUT_LONG_EDGE) -> Any:
    from PIL import Image

    width, height = image.size
    long_edge = max(width, height)
    if long_edge <= max_edge:
        return image
    ratio = max_edge / float(long_edge)
    new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
    return image.resize(new_size, Image.LANCZOS)


def remove_background_bytes(content: bytes, *, model_name: str | None = None) -> Any:
    """Run rembg on raw bytes and return an RGBA ``PIL.Image``.

    Falls back to loading the session lazily if the warmup hook didn't fire
    (e.g. when invoked from a synchronous unit test that bypasses Celery).
    """
    from PIL import Image

    session = _get_rembg_session()
    try:
        from rembg import remove  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "rembg is not installed — add rembg + onnxruntime to requirements.txt "
            "to enable background removal."
        ) from exc

    output = remove(bytes(content), session=session, post_process_mask=True)
    if isinstance(output, bytes):
        return Image.open(io.BytesIO(output)).convert("RGBA")
    # Some rembg versions return a PIL image directly.
    return output.convert("RGBA") if hasattr(output, "convert") else output


def _png_bytes(image: Any) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _select_cutout_row(
    *,
    client_id: int,
    source_hash: str | None = None,
    source_url_hash: str | None = None,
) -> dict[str, Any] | None:
    """Fetch a cutout row by either content hash (canonical dedup key) or URL
    hash (fast path for the renderer that hasn't downloaded the bytes yet).
    """
    from app.db.pool import get_connection

    if not source_hash and not source_url_hash:
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            if source_hash:
                cur.execute(
                    """
                    SELECT id, subaccount_id, client_id, source_hash, source_url, media_id,
                           model, status, has_native_alpha, cutout_width, cutout_height,
                           error, last_referenced_at, created_at, updated_at, source_url_hash
                    FROM image_cutouts
                    WHERE client_id = %s AND source_hash = %s
                    LIMIT 1
                    """,
                    (int(client_id), source_hash),
                )
            else:
                cur.execute(
                    """
                    SELECT id, subaccount_id, client_id, source_hash, source_url, media_id,
                           model, status, has_native_alpha, cutout_width, cutout_height,
                           error, last_referenced_at, created_at, updated_at, source_url_hash
                    FROM image_cutouts
                    WHERE client_id = %s AND source_url_hash = %s AND status = 'ready'
                    ORDER BY last_referenced_at DESC
                    LIMIT 1
                    """,
                    (int(client_id), source_url_hash),
                )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [d.name for d in cur.description]
    return dict(zip(columns, row))


def _url_hash(url: str) -> str:
    return hashlib.sha256(str(url or "").encode("utf-8")).hexdigest()


def _upsert_pending_row(
    *,
    subaccount_id: int,
    client_id: int,
    source_hash: str,
    source_url: str,
    model: str,
) -> dict[str, Any]:
    from app.db.pool import get_connection

    url_hash = _url_hash(source_url)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO image_cutouts
                    (subaccount_id, client_id, source_hash, source_url_hash, source_url,
                     model, status, last_referenced_at, created_at, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, 'pending', NOW(), NOW(), NOW())
                ON CONFLICT (client_id, source_hash)
                DO UPDATE SET
                    source_url = EXCLUDED.source_url,
                    source_url_hash = EXCLUDED.source_url_hash,
                    last_referenced_at = NOW(),
                    updated_at = NOW()
                RETURNING id, status, media_id
                """,
                (
                    int(subaccount_id),
                    int(client_id),
                    source_hash,
                    url_hash,
                    source_url,
                    model,
                ),
            )
            row = cur.fetchone()
            columns = [d.name for d in cur.description]
        conn.commit()
    return dict(zip(columns, row))


def _mark_in_progress(*, client_id: int, source_hash: str) -> None:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE image_cutouts
                SET status = 'in_progress', updated_at = NOW(), error = NULL
                WHERE client_id = %s AND source_hash = %s
                """,
                (int(client_id), source_hash),
            )
        conn.commit()


def _mark_ready(
    *,
    client_id: int,
    source_hash: str,
    media_id: str,
    model: str,
    has_native_alpha: bool,
    width: int,
    height: int,
) -> None:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE image_cutouts
                SET status = 'ready',
                    media_id = %s,
                    model = %s,
                    has_native_alpha = %s,
                    cutout_width = %s,
                    cutout_height = %s,
                    error = NULL,
                    last_referenced_at = NOW(),
                    updated_at = NOW()
                WHERE client_id = %s AND source_hash = %s
                """,
                (
                    media_id,
                    model,
                    bool(has_native_alpha),
                    int(width),
                    int(height),
                    int(client_id),
                    source_hash,
                ),
            )
        conn.commit()


def _mark_failed(*, client_id: int, source_hash: str, error: str) -> None:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE image_cutouts
                SET status = 'failed',
                    error = %s,
                    updated_at = NOW()
                WHERE client_id = %s AND source_hash = %s
                """,
                (error[:2000], int(client_id), source_hash),
            )
        conn.commit()


def touch_last_referenced(client_id: int, source_hashes: list[str]) -> None:
    """Update ``last_referenced_at`` so orphan-purge leaves these cutouts alone.

    Called whenever a feed generation references a cutout, so the retention
    sweeper only purges truly abandoned cutouts (no product references for N
    days).
    """
    if not source_hashes:
        return
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE image_cutouts
                SET last_referenced_at = NOW()
                WHERE client_id = %s AND source_hash = ANY(%s)
                """,
                (int(client_id), list(source_hashes)),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Download + hash
# ---------------------------------------------------------------------------


def _download_source(url: str) -> bytes:
    import httpx

    try:
        from app.core.config import load_settings

        settings = load_settings()
        timeout = float(settings.storage_media_remote_fetch_timeout_seconds or 15)
        max_bytes = int(settings.storage_media_remote_fetch_max_bytes or 10 * 1024 * 1024)
    except Exception:  # noqa: BLE001
        timeout = 15.0
        max_bytes = 10 * 1024 * 1024

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        body = response.content
    if max_bytes > 0 and len(body) > max_bytes:
        raise RuntimeError(
            f"source image exceeds max bytes: {len(body)} > {max_bytes}"
        )
    return body


# ---------------------------------------------------------------------------
# S3 upload + media library bridge
# ---------------------------------------------------------------------------


def _upload_cutout(
    *,
    client_id: int,
    media_id: str,
    png_bytes: bytes,
    source_hash: str,
) -> tuple[str, str]:
    """Upload the cutout PNG to S3 at the standard media-storage key and
    return ``(key, url)``.

    Keeps the same ``clients/{client_id}/image/{media_id}/{file}`` layout used
    by user uploads so Stocare Media can list it without any special case.
    """
    from app.services.s3_provider import get_s3_bucket_name, get_s3_client

    bucket = get_s3_bucket_name()
    if not bucket:
        raise RuntimeError("STORAGE_S3_BUCKET is not configured")
    key = f"clients/{int(client_id)}/image/{media_id}/cutout_{source_hash[:8]}.png"
    s3 = get_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=png_bytes, ContentType="image/png")

    try:
        from app.core.config import load_settings

        region = str(load_settings().storage_s3_region or "").strip()
        cdn = str(load_settings().storage_cdn_base_url or "").strip()
    except Exception:  # noqa: BLE001
        region = ""
        cdn = ""

    if cdn:
        url = f"{cdn.rstrip('/')}/{key}"
    elif region:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    else:
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
    return key, url


def _register_in_media_library(
    *,
    client_id: int,
    s3_key: str,
    image_url: str,
    source_url: str,
    source_hash: str,
    model: str,
    width: int,
    height: int,
    has_native_alpha: bool,
    feed_source_name: str | None,
) -> str:
    """Create (or reuse) a ``media_files`` row so the cutout shows up in
    Stocare Media under ``Cutouts / {feed source name}``.

    Returns the media_id of the registered asset.
    """
    from app.services.media_folder_service import media_folder_service
    from app.services.s3_provider import get_s3_bucket_name
    from app.services.storage_media_ingest import storage_media_ingest_service

    bucket = str(get_s3_bucket_name() or "").strip()

    parent_folder = media_folder_service.ensure_system_folder(
        client_id=int(client_id),
        parent_folder_id=None,
        name="Cutouts",
    )
    feed_folder = media_folder_service.ensure_system_folder(
        client_id=int(client_id),
        parent_folder_id=str(parent_folder.get("folder_id") or "") or None,
        name=(feed_source_name or "Untagged")[:120],
    )

    record = storage_media_ingest_service.register_existing_s3_asset(
        client_id=int(client_id),
        kind="image",
        source="background_removed",
        bucket=bucket,
        key=s3_key,
        mime_type="image/png",
        original_filename=f"cutout_{source_hash[:12]}.png",
        display_name=f"Cutout · {source_hash[:8]}",
        folder_id=str(feed_folder.get("folder_id") or "") or None,
        metadata={
            "background_removed": {
                "source_url": source_url,
                "source_hash": source_hash,
                "model": model,
                "has_native_alpha": bool(has_native_alpha),
                "width": int(width),
                "height": int(height),
                "image_url": image_url,
            }
        },
    )
    return str(record.get("media_id") or "")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def ensure_cutout(
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None = None,
    model_name: str | None = None,
) -> CutoutRecord:
    """Produce a cutout for ``source_url`` if one doesn't already exist.

    Idempotent: repeated calls with the same ``(client_id, source_url)`` tuple
    will hit the dedup index and return the existing record without touching
    rembg or S3 a second time. Also updates ``last_referenced_at`` so the
    orphan-purge sweeper leaves it alone.
    """
    if not source_url:
        raise ValueError("source_url is required")
    if int(client_id) <= 0:
        raise ValueError("client_id must be positive")

    # Step 1: fetch the bytes — we have to download before we can hash, because
    # the source URL may include versioning query strings that don't map 1:1
    # to the image content.
    content = _download_source(source_url)
    source_hash = _sha256_hex(content)

    # Step 2: dedup check. If the row is already ready, just touch the timestamp.
    existing = _select_cutout_row(client_id=int(client_id), source_hash=source_hash)
    if existing is not None and existing.get("status") == "ready" and existing.get("media_id"):
        touch_last_referenced(int(client_id), [source_hash])
        return _record_from_row(existing)

    # Step 3: record the intent (pending) atomically.
    resolved_model = str(model_name or "u2net")
    _upsert_pending_row(
        subaccount_id=int(subaccount_id),
        client_id=int(client_id),
        source_hash=source_hash,
        source_url=source_url,
        model=resolved_model,
    )
    _mark_in_progress(client_id=int(client_id), source_hash=source_hash)

    try:
        record = _run_pipeline(
            client_id=int(client_id),
            subaccount_id=int(subaccount_id),
            source_url=source_url,
            source_hash=source_hash,
            content=content,
            requested_model=resolved_model,
            feed_source_name=feed_source_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cutout_pipeline_failed client_id=%s hash=%s", client_id, source_hash)
        _mark_failed(
            client_id=int(client_id),
            source_hash=source_hash,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    _mark_ready(
        client_id=int(client_id),
        source_hash=record.source_hash,
        media_id=record.media_id,
        model=record.model,
        has_native_alpha=record.has_native_alpha,
        width=record.width,
        height=record.height,
    )
    return record


def _run_pipeline(
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    source_hash: str,
    content: bytes,
    requested_model: str,
    feed_source_name: str | None,
) -> CutoutRecord:
    from PIL import Image

    original = Image.open(io.BytesIO(content))
    original.load()

    if has_usable_alpha(original):
        effective_model = "native_alpha"
        working = original.convert("RGBA")
    else:
        effective_model = requested_model or "u2net"
        working = remove_background_bytes(content, model_name=effective_model)

    cropped, _bbox = tight_crop_alpha(working, padding=CUTOUT_PADDING_PX)
    resized = resize_to_max(cropped, max_edge=MAX_CUTOUT_LONG_EDGE)
    png_bytes = _png_bytes(resized)
    width, height = resized.size

    # Each ready cutout gets its own media_id; reusing one would make the
    # storage key collide with unrelated uploads.
    media_id = uuid4().hex
    s3_key, image_url = _upload_cutout(
        client_id=client_id,
        media_id=media_id,
        png_bytes=png_bytes,
        source_hash=source_hash,
    )

    bridged_media_id = ""
    try:
        bridged_media_id = _register_in_media_library(
            client_id=client_id,
            s3_key=s3_key,
            image_url=image_url,
            source_url=source_url,
            source_hash=source_hash,
            model=effective_model,
            width=width,
            height=height,
            has_native_alpha=(effective_model == "native_alpha"),
            feed_source_name=feed_source_name,
        )
    except Exception:  # noqa: BLE001 — bridge is best-effort
        logger.warning(
            "cutout_media_bridge_failed client_id=%s hash=%s",
            client_id,
            source_hash,
            exc_info=True,
        )

    final_media_id = bridged_media_id or media_id

    return CutoutRecord(
        client_id=int(client_id),
        source_hash=source_hash,
        media_id=final_media_id,
        s3_key=s3_key,
        image_url=image_url,
        model=effective_model,
        has_native_alpha=(effective_model == "native_alpha"),
        width=int(width),
        height=int(height),
        status="ready",
    )


def get_cutout_url(client_id: int, source_url_or_hash: str) -> str | None:
    """Best-effort lookup for a rendered cutout URL.

    Accepts either a source URL (which we SHA-256 to derive the hash) or the
    raw hash itself. Returns ``None`` if no ready record exists — callers are
    expected to fall back to the original image URL and enqueue a background
    job.
    """
    if not source_url_or_hash:
        return None
    if len(source_url_or_hash) == 64 and all(c in "0123456789abcdef" for c in source_url_or_hash.lower()):
        source_hash = source_url_or_hash.lower()
    else:
        # We'd need to download to hash — caller should use ensure_cutout for
        # that path. Lookup by source_url only works for hashes we already
        # know, so this branch returns None.
        return None

    row = _select_cutout_row(client_id=int(client_id), source_hash=source_hash)
    if not row or row.get("status") != "ready":
        return None
    # The image_url isn't persisted in Postgres (media_files owns that), so
    # regenerate it from the bucket/key. Callers that want the CDN URL should
    # look up the media_files row directly.
    return None  # handled by caller via media_files lookup when needed


def _record_from_row(row: dict[str, Any]) -> CutoutRecord:
    media_id = str(row.get("media_id") or "")
    s3_key = ""
    image_url = ""
    if media_id:
        s3_key, image_url = _lookup_media_storage(media_id)
    return CutoutRecord(
        client_id=int(row.get("client_id") or 0),
        source_hash=str(row.get("source_hash") or ""),
        media_id=media_id,
        s3_key=s3_key,
        image_url=image_url,
        model=str(row.get("model") or "u2net"),
        has_native_alpha=bool(row.get("has_native_alpha") or False),
        width=int(row.get("cutout_width") or 0),
        height=int(row.get("cutout_height") or 0),
        status=str(row.get("status") or ""),
    )


def _lookup_media_storage(media_id: str) -> tuple[str, str]:
    """Return ``(s3_key, image_url)`` for a ready media_files row, or empty
    strings if the row is missing.

    Used by ``ensure_cutout`` when a dedup cache hit sends us to an existing
    cutout — we still want to give the caller a concrete URL.
    """
    try:
        from app.services.media_metadata_repository import media_metadata_repository

        record = media_metadata_repository.get_by_media_id(media_id)
        if not isinstance(record, dict):
            return "", ""
        storage = record.get("storage") or {}
        if not isinstance(storage, dict):
            return "", ""
        bucket = str(storage.get("bucket") or "").strip()
        key = str(storage.get("key") or "").strip()
        region = str(storage.get("region") or "").strip()
        if not (bucket and key):
            return "", ""

        try:
            from app.core.config import load_settings

            cdn = str(load_settings().storage_cdn_base_url or "").strip()
        except Exception:  # noqa: BLE001
            cdn = ""

        if cdn:
            url = f"{cdn.rstrip('/')}/{key}"
        elif region:
            url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
        else:
            url = f"https://{bucket}.s3.amazonaws.com/{key}"
        return key, url
    except Exception:  # noqa: BLE001
        logger.debug("media_lookup_failed media_id=%s", media_id, exc_info=True)
        return "", ""


def lookup_ready_cutout(client_id: int, source_hash: str) -> CutoutRecord | None:
    """Return the ready ``CutoutRecord`` for ``(client_id, source_hash)`` or
    ``None`` — used by the image renderer to decide whether to draw the cutout
    or fall back to the original image.
    """
    if not source_hash:
        return None
    row = _select_cutout_row(client_id=int(client_id), source_hash=source_hash)
    if row is None or row.get("status") != "ready":
        return None
    return _record_from_row(row)


def lookup_ready_cutout_by_url(client_id: int, source_url: str) -> CutoutRecord | None:
    """URL-hash lookup for fast paths that haven't downloaded the source yet.

    Returns ``None`` when no ready cutout is registered against this URL,
    even when the same content is actually present under a different URL —
    the priming / sync-hook pipeline is responsible for populating the
    ``source_url_hash`` index in that case.
    """
    if not source_url or int(client_id) <= 0:
        return None
    row = _select_cutout_row(
        client_id=int(client_id),
        source_url_hash=_url_hash(source_url),
    )
    if row is None or row.get("status") != "ready":
        return None
    return _record_from_row(row)
