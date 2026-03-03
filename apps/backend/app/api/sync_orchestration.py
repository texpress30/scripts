from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store

router = APIRouter(prefix="/agency/sync-runs", tags=["sync-orchestration"])


class CreateBatchSyncRunsRequest(BaseModel):
    platform: Literal["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]
    account_ids: list[str]
    job_type: Literal["historical_backfill", "rolling_refresh", "manual"] = "manual"
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = Field(default=None, ge=1, le=3650)
    chunk_days: int = Field(default=7, ge=1, le=31)
    grain: str = "account_daily"


def _normalize_account_id(value: str) -> str:
    return str(value).strip().replace("-", "")


def _resolve_date_range(payload: CreateBatchSyncRunsRequest) -> tuple[date, date]:
    if payload.start_date is not None or payload.end_date is not None:
        if payload.start_date is None or payload.end_date is None:
            raise HTTPException(status_code=400, detail="start_date și end_date trebuie furnizate împreună")
        if payload.end_date < payload.start_date:
            raise HTTPException(status_code=400, detail="end_date trebuie să fie >= start_date")
        return payload.start_date, payload.end_date

    if payload.days is None:
        raise HTTPException(status_code=400, detail="Trebuie furnizat fie start_date/end_date, fie days")

    utc_today = datetime.now(timezone.utc).date()
    end_date = utc_today - timedelta(days=1)
    start_date = end_date - timedelta(days=max(1, int(payload.days)) - 1)
    return start_date, end_date


def _build_chunks(*, start_date: date, end_date: date, chunk_days: int) -> list[tuple[int, date, date]]:
    chunks: list[tuple[int, date, date]] = []
    current = start_date
    idx = 0
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max(1, int(chunk_days)) - 1), end_date)
        chunks.append((idx, current, chunk_end))
        idx += 1
        current = chunk_end + timedelta(days=1)
    return chunks



def _serialize_run(item: dict[str, object]) -> dict[str, object]:
    return {
        "job_id": item.get("job_id"),
        "batch_id": item.get("batch_id"),
        "job_type": item.get("job_type"),
        "grain": item.get("grain"),
        "platform": item.get("platform"),
        "account_id": item.get("account_id"),
        "client_id": item.get("client_id"),
        "status": item.get("status"),
        "date_start": item.get("date_start"),
        "date_end": item.get("date_end"),
        "chunk_days": item.get("chunk_days"),
        "chunks_total": item.get("chunks_total"),
        "chunks_done": item.get("chunks_done"),
        "rows_written": item.get("rows_written"),
        "error": item.get("error"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "metadata": item.get("metadata") or {},
    }


def _serialize_chunk(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item.get("id"),
        "job_id": item.get("job_id"),
        "chunk_index": item.get("chunk_index"),
        "status": item.get("status"),
        "date_start": item.get("date_start"),
        "date_end": item.get("date_end"),
        "attempts": item.get("attempts"),
        "rows_written": item.get("rows_written"),
        "duration_ms": item.get("duration_ms"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "error": item.get("error"),
        "metadata": item.get("metadata") or {},
    }

@router.post("/batch")
def create_batch_sync_runs(payload: CreateBatchSyncRunsRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:sync", scope="agency")

    normalized_account_ids: list[str] = []
    for raw in payload.account_ids:
        normalized = _normalize_account_id(raw)
        if normalized != "" and normalized not in normalized_account_ids:
            normalized_account_ids.append(normalized)

    if len(normalized_account_ids) <= 0:
        raise HTTPException(status_code=400, detail="account_ids trebuie să conțină cel puțin un id valid")

    start_date, end_date = _resolve_date_range(payload)

    platform_accounts = client_registry_service.list_platform_accounts(platform=payload.platform)
    accounts_map: dict[str, int | None] = {}
    for item in platform_accounts:
        normalized = _normalize_account_id(str(item.get("id") or ""))
        if normalized == "":
            continue
        attached = item.get("attached_client_id")
        accounts_map[normalized] = int(attached) if attached is not None else None

    valid_account_ids = [account_id for account_id in normalized_account_ids if account_id in accounts_map]
    invalid_account_ids = [account_id for account_id in normalized_account_ids if account_id not in accounts_map]

    if len(valid_account_ids) <= 0:
        raise HTTPException(status_code=400, detail={"message": "Niciun account_id valid pentru platformă", "invalid_account_ids": invalid_account_ids})

    batch_id = uuid4().hex
    created_runs: list[dict[str, object]] = []

    for account_id in valid_account_ids:
        job_id = uuid4().hex
        chunks = _build_chunks(start_date=start_date, end_date=end_date, chunk_days=payload.chunk_days)
        created = sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=payload.platform,
            status="queued",
            date_start=start_date,
            date_end=end_date,
            chunk_days=int(payload.chunk_days),
            client_id=accounts_map.get(account_id),
            account_id=account_id,
            metadata={
                "source": "agency_batch",
                "job_type": payload.job_type,
                "grain": payload.grain,
                "batch_id": batch_id,
            },
            batch_id=batch_id,
            job_type=payload.job_type,
            grain=payload.grain,
            chunks_total=len(chunks),
            chunks_done=0,
            rows_written=0,
        )

        for chunk_index, chunk_start, chunk_end in chunks:
            sync_run_chunks_store.create_sync_run_chunk(
                job_id=job_id,
                chunk_index=chunk_index,
                status="queued",
                date_start=chunk_start,
                date_end=chunk_end,
                metadata={
                    "source": "agency_batch",
                    "batch_id": batch_id,
                    "job_type": payload.job_type,
                    "grain": payload.grain,
                },
            )

        created_runs.append(
            {
                "job_id": str(created.get("job_id") if created is not None else job_id),
                "account_id": account_id,
                "client_id": created.get("client_id") if created is not None else accounts_map.get(account_id),
                "status": "queued",
                "chunks_total": len(chunks),
            }
        )

    return {
        "status": "queued",
        "batch_id": batch_id,
        "platform": payload.platform,
        "job_type": payload.job_type,
        "grain": payload.grain,
        "date_range": {"start": str(start_date), "end": str(end_date)},
        "chunk_days": int(payload.chunk_days),
        "created_count": len(created_runs),
        "invalid_account_ids": invalid_account_ids,
        "runs": created_runs,
    }


@router.get("/batch/{batch_id}")
def get_batch_sync_runs_status(batch_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    batch_progress = sync_runs_store.get_batch_progress(str(batch_id))
    runs = sync_runs_store.list_sync_runs_by_batch(str(batch_id))

    chunks_total = int(batch_progress.get("chunks_total_sum") or 0)
    chunks_done = int(batch_progress.get("chunks_done_sum") or 0)
    percent = 0.0 if chunks_total <= 0 else round((chunks_done / chunks_total) * 100.0, 2)

    progress = {
        "total_runs": int(batch_progress.get("total_runs") or 0),
        "queued": int((batch_progress.get("status_counts") or {}).get("queued") or 0),
        "running": int((batch_progress.get("status_counts") or {}).get("running") or 0),
        "done": int((batch_progress.get("status_counts") or {}).get("done") or 0),
        "error": int((batch_progress.get("status_counts") or {}).get("error") or 0),
        "chunks_total": chunks_total,
        "chunks_done": chunks_done,
        "rows_written": int(batch_progress.get("rows_written_sum") or 0),
        "percent": percent,
    }

    return {
        "batch_id": str(batch_id),
        "progress": progress,
        "runs": [_serialize_run(item) for item in runs],
    }


@router.get("/accounts/{platform}/{account_id}")
def list_account_sync_runs(
    platform: str,
    account_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    normalized_platform = str(platform).strip()
    normalized_account_id = str(account_id).strip()
    runs = sync_runs_store.list_sync_runs_for_account(
        platform=normalized_platform,
        account_id=normalized_account_id,
        limit=int(limit),
    )

    return {
        "platform": normalized_platform,
        "account_id": normalized_account_id,
        "limit": int(limit),
        "runs": [_serialize_run(item) for item in runs],
    }


@router.get("/{job_id}")
def get_sync_run_details(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    run = sync_runs_store.get_sync_run(str(job_id).strip())
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return _serialize_run(run)


@router.get("/{job_id}/chunks")
def list_sync_run_chunks(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    normalized_job_id = str(job_id).strip()
    run = sync_runs_store.get_sync_run(normalized_job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")

    chunks = sync_run_chunks_store.list_sync_run_chunks(normalized_job_id)
    return {
        "job_id": normalized_job_id,
        "chunks": [_serialize_chunk(item) for item in chunks],
    }
