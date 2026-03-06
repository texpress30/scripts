from __future__ import annotations

from datetime import date, datetime
from typing import Any

ALLOWED_PLATFORM_ACCOUNT_WATERMARK_GRAINS: tuple[str, ...] = (
    "account_daily",
    "campaign_daily",
    "ad_group_daily",
    "ad_daily",
)


def _validate_grain(grain: str) -> None:
    if grain not in ALLOWED_PLATFORM_ACCOUNT_WATERMARK_GRAINS:
        raise ValueError(f"Invalid grain '{grain}'. Allowed: {', '.join(ALLOWED_PLATFORM_ACCOUNT_WATERMARK_GRAINS)}")


def _row_to_dict(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "platform": row[0],
        "account_id": row[1],
        "grain": row[2],
        "sync_start_date": row[3],
        "historical_synced_through": row[4],
        "rolling_synced_through": row[5],
        "last_success_at": row[6],
        "last_error": row[7],
        "last_job_id": row[8],
        "updated_at": row[9],
    }


def get_platform_account_watermark(
    conn,
    *,
    platform: str,
    account_id: str,
    grain: str,
) -> dict[str, Any] | None:
    _validate_grain(grain)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              platform,
              account_id,
              grain,
              sync_start_date,
              historical_synced_through,
              rolling_synced_through,
              last_success_at,
              last_error,
              last_job_id,
              updated_at
            FROM platform_account_watermarks
            WHERE platform = %s AND account_id = %s AND grain = %s
            """,
            (platform, account_id, grain),
        )
        return _row_to_dict(cursor.fetchone())


def upsert_platform_account_watermark(
    conn,
    *,
    platform: str,
    account_id: str,
    grain: str,
    sync_start_date: date | None = None,
    historical_synced_through: date | None = None,
    rolling_synced_through: date | None = None,
    last_success_at: datetime | None = None,
    last_error: str | None = None,
    last_job_id: str | None = None,
) -> dict[str, Any]:
    _validate_grain(grain)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO platform_account_watermarks (
              platform,
              account_id,
              grain,
              sync_start_date,
              historical_synced_through,
              rolling_synced_through,
              last_success_at,
              last_error,
              last_job_id,
              updated_at
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (platform, account_id, grain)
            DO UPDATE SET
              sync_start_date = CASE
                WHEN platform_account_watermarks.sync_start_date IS NULL THEN EXCLUDED.sync_start_date
                WHEN EXCLUDED.sync_start_date IS NULL THEN platform_account_watermarks.sync_start_date
                ELSE LEAST(platform_account_watermarks.sync_start_date, EXCLUDED.sync_start_date)
              END,
              historical_synced_through = CASE
                WHEN platform_account_watermarks.historical_synced_through IS NULL THEN EXCLUDED.historical_synced_through
                WHEN EXCLUDED.historical_synced_through IS NULL THEN platform_account_watermarks.historical_synced_through
                ELSE GREATEST(platform_account_watermarks.historical_synced_through, EXCLUDED.historical_synced_through)
              END,
              rolling_synced_through = CASE
                WHEN platform_account_watermarks.rolling_synced_through IS NULL THEN EXCLUDED.rolling_synced_through
                WHEN EXCLUDED.rolling_synced_through IS NULL THEN platform_account_watermarks.rolling_synced_through
                ELSE GREATEST(platform_account_watermarks.rolling_synced_through, EXCLUDED.rolling_synced_through)
              END,
              last_success_at = CASE
                WHEN platform_account_watermarks.last_success_at IS NULL THEN EXCLUDED.last_success_at
                WHEN EXCLUDED.last_success_at IS NULL THEN platform_account_watermarks.last_success_at
                ELSE GREATEST(platform_account_watermarks.last_success_at, EXCLUDED.last_success_at)
              END,
              last_error = COALESCE(EXCLUDED.last_error, platform_account_watermarks.last_error),
              last_job_id = COALESCE(EXCLUDED.last_job_id, platform_account_watermarks.last_job_id),
              updated_at = NOW()
            RETURNING
              platform,
              account_id,
              grain,
              sync_start_date,
              historical_synced_through,
              rolling_synced_through,
              last_success_at,
              last_error,
              last_job_id,
              updated_at
            """,
            (
                platform,
                account_id,
                grain,
                sync_start_date,
                historical_synced_through,
                rolling_synced_through,
                last_success_at,
                last_error,
                last_job_id,
            ),
        )
        row = cursor.fetchone()

    data = _row_to_dict(row)
    if data is None:
        raise RuntimeError("Failed to upsert platform account watermark")
    return data
