"""HTTP endpoints for the background-removal pipeline.

These routes are intentionally thin — most of the logic lives in
``cutout_service`` and the Celery tasks. The API is there so the UI can:

* enqueue a bulk run when activating the feature on an existing feed
* poll the progress of that bulk run
* list cutouts for a given client so the Media Storage page can show counts
  and status chips without re-querying Mongo
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.services.auth import AuthUser

router = APIRouter(prefix="/cutouts", tags=["cutouts"])


class CutoutBatchRequest(BaseModel):
    subaccount_id: int
    feed_source_id: str
    limit: int | None = None


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
def enqueue_batch(
    payload: CutoutBatchRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Kick off bulk background removal for every product of a feed source.

    Runs on the ``bgremoval_bulk`` queue so it can't starve interactive
    shuffles. Returns the count of tasks enqueued — the caller should then
    poll ``GET /cutouts/batch/{id}`` for progress.
    """
    enforce_subaccount_action(
        user=user,
        action="creative:write",
        subaccount_id=int(payload.subaccount_id),
    )
    from app.db.pool import get_connection
    from app.services.feed_management.products_repository import feed_products_repository
    from app.services.enriched_catalog.shuffle_service import _first_image_url

    try:
        from app.workers.tasks.bg_removal import process_source_image_bulk
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="Background worker unavailable",
        )

    # Insert a tracking row so the front-end can show a progress bar.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cutout_batch_jobs
                    (subaccount_id, client_id, feed_source_id, kind, total, status,
                     created_at, updated_at)
                VALUES
                    (%s, %s, %s::uuid, 'bulk', 0, 'pending', NOW(), NOW())
                RETURNING id
                """,
                (
                    int(payload.subaccount_id),
                    int(payload.subaccount_id),
                    str(payload.feed_source_id),
                ),
            )
            job_id = int(cur.fetchone()[0])
        conn.commit()

    # Stream the products in batches to avoid pulling the entire catalog into
    # memory. Each product becomes a Celery task; dedup in ``cutout_service``
    # guarantees identical images only run once.
    enqueued = 0
    batch_size = 500
    skip = 0
    max_limit = int(payload.limit or 1_000_000)
    while enqueued < max_limit:
        batch = feed_products_repository.list_products(
            payload.feed_source_id, skip=skip, limit=batch_size
        )
        if not batch:
            break
        for doc in batch:
            data = doc.get("data", doc) if isinstance(doc, dict) else {}
            image_src = _first_image_url(data)
            if not image_src:
                continue
            try:
                process_source_image_bulk.apply_async(
                    kwargs={
                        "client_id": int(payload.subaccount_id),
                        "subaccount_id": int(payload.subaccount_id),
                        "source_url": image_src,
                    },
                    queue="bgremoval_bulk",
                )
                enqueued += 1
                if enqueued >= max_limit:
                    break
            except Exception:  # noqa: BLE001
                pass
        if len(batch) < batch_size:
            break
        skip += batch_size

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cutout_batch_jobs
                SET total = %s, status = 'in_progress', updated_at = NOW()
                WHERE id = %s
                """,
                (int(enqueued), int(job_id)),
            )
        conn.commit()

    return {"job_id": job_id, "enqueued": enqueued}


@router.get("/batch/{job_id}")
def get_batch_status(
    job_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, subaccount_id, client_id, feed_source_id::text, kind,
                       total, done, failed, status, error, created_at, updated_at
                FROM cutout_batch_jobs
                WHERE id = %s
                """,
                (int(job_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="batch not found")
    enforce_subaccount_action(
        user=user, action="creative:list", subaccount_id=int(row[1])
    )
    return {
        "job_id": int(row[0]),
        "subaccount_id": int(row[1]),
        "client_id": int(row[2]),
        "feed_source_id": row[3],
        "kind": row[4],
        "total": int(row[5] or 0),
        "done": int(row[6] or 0),
        "failed": int(row[7] or 0),
        "status": row[8],
        "error": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
    }


@router.get("")
def list_cutouts(
    subaccount_id: int = Query(...),
    limit: int = Query(200, ge=1, le=1000),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return recent cutout rows for a client.

    Used by the Media Storage counts bar and by monitoring dashboards. The
    response is capped at 1000 rows; for large clients the UI should filter
    to a specific feed source instead of listing everything.
    """
    enforce_subaccount_action(
        user=user, action="creative:list", subaccount_id=int(subaccount_id)
    )
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_hash, source_url, media_id, model, status,
                       has_native_alpha, cutout_width, cutout_height, error,
                       last_referenced_at, created_at, updated_at
                FROM image_cutouts
                WHERE client_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (int(subaccount_id), int(limit)),
            )
            rows = cur.fetchall() or []

    return {
        "items": [
            {
                "id": int(r[0]),
                "source_hash": r[1],
                "source_url": r[2],
                "media_id": r[3],
                "model": r[4],
                "status": r[5],
                "has_native_alpha": bool(r[6]),
                "cutout_width": int(r[7] or 0),
                "cutout_height": int(r[8] or 0),
                "error": r[9],
                "last_referenced_at": r[10].isoformat() if r[10] else None,
                "created_at": r[11].isoformat() if r[11] else None,
                "updated_at": r[12].isoformat() if r[12] else None,
            }
            for r in rows
        ]
    }
