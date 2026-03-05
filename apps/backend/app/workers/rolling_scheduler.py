from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.services.client_registry import client_registry_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store


def _safe_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return date.fromisoformat(raw)
    except Exception:  # noqa: BLE001
        return None


def _build_chunks(*, start_date: date, end_date: date, chunk_days: int) -> list[tuple[int, date, date]]:
    chunks: list[tuple[int, date, date]] = []
    current = start_date
    index = 0
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max(1, int(chunk_days)) - 1), end_date)
        chunks.append((index, current, chunk_end))
        index += 1
        current = chunk_end + timedelta(days=1)
    return chunks




def _is_account_inactive_for_rolling(item: dict[str, object]) -> bool:
    status_values = [item.get("status"), item.get("account_status")]
    for value in status_values:
        normalized = str(value or "").strip().lower()
        if normalized in {"inactive", "disabled", "paused", "archived", "off"}:
            return True

    is_active = item.get("is_active")
    if isinstance(is_active, bool) and not is_active:
        return True

    return False


def _resolve_rolling_window_dates(*, timezone_name: str) -> tuple[date, date]:
    local_now = datetime.now(ZoneInfo(timezone_name))
    end_date = local_now.date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    return start_date, end_date


def _is_account_eligible_for_daily_rolling(item: dict[str, object]) -> tuple[bool, str | None]:
    attached_client_id = item.get("attached_client_id")
    if attached_client_id is None:
        return False, "unmapped"

    sync_start_date = _safe_date(item.get("sync_start_date"))
    if sync_start_date is None:
        return False, "history_not_initialized"

    if _is_account_inactive_for_rolling(item):
        return False, "inactive"

    return True, None

def enqueue_rolling_sync_runs(
    *,
    platform: str = "google_ads",
    limit: int = 500,
    chunk_days: int = 7,
    force: bool = False,
) -> dict[str, object]:
    normalized_platform = str(platform).strip()
    if normalized_platform != "google_ads":
        raise ValueError("rolling scheduler currently supports only platform='google_ads'")

    rows = client_registry_service.list_platform_accounts(platform=normalized_platform)
    effective_rows = rows[: max(1, int(limit))]

    batch_id = f"rolling-{normalized_platform}-{datetime.now(timezone.utc).date().isoformat()}-{uuid4().hex[:8]}"

    enqueued_account_ids: list[str] = []
    skipped_up_to_date: list[str] = []
    skipped_unmapped: list[str] = []
    skipped_history_not_initialized: list[str] = []
    skipped_inactive: list[str] = []
    skipped_invalid_timezone: list[str] = []
    created_runs: list[dict[str, object]] = []

    for item in effective_rows:
        account_id = str(item.get("id") or "").strip()
        if account_id == "":
            continue

        eligible, reason = _is_account_eligible_for_daily_rolling(item)
        if not eligible:
            if reason == "unmapped":
                skipped_unmapped.append(account_id)
            elif reason == "history_not_initialized":
                skipped_history_not_initialized.append(account_id)
            elif reason == "inactive":
                skipped_inactive.append(account_id)
            continue

        client_id_value = item.get("attached_client_id")
        timezone_name = str(item.get("timezone") or item.get("account_timezone") or "UTC").strip() or "UTC"
        try:
            start_date, end_date = _resolve_rolling_window_dates(timezone_name=timezone_name)
        except Exception:  # noqa: BLE001
            skipped_invalid_timezone.append(account_id)
            continue

        watermark = _safe_date(item.get("rolling_synced_through"))
        if not force and watermark is not None and watermark >= end_date:
            skipped_up_to_date.append(account_id)
            continue

        chunks = _build_chunks(start_date=start_date, end_date=end_date, chunk_days=max(1, int(chunk_days)))
        job_id = uuid4().hex
        created = sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=normalized_platform,
            status="queued",
            client_id=int(client_id_value),
            account_id=account_id,
            date_start=start_date,
            date_end=end_date,
            chunk_days=max(1, int(chunk_days)),
            metadata={
                "source": "cron",
                "trigger_source": "cron",
                "batch_id": batch_id,
                "tz": timezone_name,
                "rolling_window_days": 7,
            },
            batch_id=batch_id,
            job_type="rolling_refresh",
            grain="account_daily",
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
                    "source": "cron",
                    "batch_id": batch_id,
                    "tz": timezone_name,
                    "rolling_window_days": 7,
                },
            )

        created_runs.append(
            {
                "job_id": str(created.get("job_id") if created is not None else job_id),
                "account_id": account_id,
                "client_id": int(client_id_value),
                "date_start": str(start_date),
                "date_end": str(end_date),
                "chunks_total": len(chunks),
            }
        )
        enqueued_account_ids.append(account_id)

    return {
        "status": "queued",
        "platform": normalized_platform,
        "batch_id": batch_id,
        "force": bool(force),
        "chunk_days": max(1, int(chunk_days)),
        "processed_accounts": len(effective_rows),
        "enqueued_count": len(enqueued_account_ids),
        "skipped_unmapped_count": len(skipped_unmapped),
        "skipped_up_to_date_count": len(skipped_up_to_date),
        "skipped_history_not_initialized_count": len(skipped_history_not_initialized),
        "skipped_inactive_count": len(skipped_inactive),
        "skipped_invalid_timezone_count": len(skipped_invalid_timezone),
        "enqueued_account_ids": enqueued_account_ids,
        "skipped_unmapped_account_ids": skipped_unmapped,
        "skipped_up_to_date_account_ids": skipped_up_to_date,
        "skipped_history_not_initialized_account_ids": skipped_history_not_initialized,
        "skipped_inactive_account_ids": skipped_inactive,
        "skipped_invalid_timezone_account_ids": skipped_invalid_timezone,
        "runs": created_runs,
    }


def main() -> None:
    platform = os.environ.get("ROLLING_SCHEDULER_PLATFORM", "google_ads")
    limit = int(os.environ.get("ROLLING_SCHEDULER_LIMIT", "500") or 500)
    chunk_days = int(os.environ.get("ROLLING_SCHEDULER_CHUNK_DAYS", "7") or 7)
    force = os.environ.get("ROLLING_SCHEDULER_FORCE", "0") == "1"
    summary = enqueue_rolling_sync_runs(platform=platform, limit=limit, chunk_days=chunk_days, force=force)
    print(summary)


if __name__ == "__main__":
    main()
