from __future__ import annotations

from datetime import date
from typing import Any

from app.services.platform_account_watermarks_store import (
    ALLOWED_PLATFORM_ACCOUNT_WATERMARK_GRAINS,
    upsert_platform_account_watermark,
)

FACT_TABLE_BY_GRAIN: dict[str, str] = {
    "campaign_daily": "campaign_performance_reports",
    "ad_group_daily": "ad_group_performance_reports",
    "ad_daily": "ad_unit_performance_reports",
}

_DEFAULT_RECONCILE_GRAINS: tuple[str, ...] = ("campaign_daily", "ad_group_daily", "ad_daily")


def _validate_reconcile_grain(grain: str) -> None:
    if grain not in FACT_TABLE_BY_GRAIN:
        raise ValueError(f"Unsupported reconcile grain '{grain}'")
    if grain not in ALLOWED_PLATFORM_ACCOUNT_WATERMARK_GRAINS:
        raise ValueError(f"Unsupported watermark grain '{grain}'")


def derive_fact_coverage_by_account(
    conn,
    *,
    platform: str,
    account_ids: list[str],
    grain: str,
) -> list[dict[str, Any]]:
    _validate_reconcile_grain(grain)
    if not account_ids:
        return []

    fact_table = FACT_TABLE_BY_GRAIN[grain]

    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            WITH requested AS (
              SELECT account_id, ord
              FROM unnest(%s::text[]) WITH ORDINALITY AS t(account_id, ord)
            ),
            fact_agg AS (
              SELECT
                account_id,
                MIN(report_date) AS min_date,
                MAX(report_date) AS max_date,
                COUNT(*)::bigint AS row_count
              FROM {fact_table}
              WHERE platform = %s
                AND account_id = ANY(%s::text[])
              GROUP BY account_id
            )
            SELECT
              r.account_id,
              f.min_date,
              f.max_date,
              COALESCE(f.row_count, 0)::bigint AS row_count
            FROM requested r
            LEFT JOIN fact_agg f ON f.account_id = r.account_id
            ORDER BY r.ord
            """,
            (account_ids, platform, account_ids),
        )
        rows = cursor.fetchall()

    return [
        {
            "account_id": row[0],
            "grain": grain,
            "min_date": row[1],
            "max_date": row[2],
            "row_count": int(row[3] or 0),
        }
        for row in rows
    ]


def reconcile_platform_account_watermarks_from_facts(
    conn,
    *,
    platform: str,
    account_ids: list[str],
    grains: list[str] | None = None,
) -> dict[str, Any]:
    reconcile_grains = grains if grains is not None else list(_DEFAULT_RECONCILE_GRAINS)
    for grain in reconcile_grains:
        _validate_reconcile_grain(grain)

    summary = {
        "platform": platform,
        "requested_accounts": len(account_ids),
        "grains": reconcile_grains,
        "updated_count_by_grain": {grain: 0 for grain in reconcile_grains},
        "skipped_no_data_by_grain": {grain: 0 for grain in reconcile_grains},
    }

    if not account_ids:
        return summary

    for grain in reconcile_grains:
        coverage_rows = derive_fact_coverage_by_account(
            conn,
            platform=platform,
            account_ids=account_ids,
            grain=grain,
        )

        for coverage in coverage_rows:
            min_date = coverage.get("min_date")
            max_date = coverage.get("max_date")
            if max_date is None:
                summary["skipped_no_data_by_grain"][grain] += 1
                continue

            upsert_platform_account_watermark(
                conn,
                platform=platform,
                account_id=str(coverage["account_id"]),
                grain=grain,
                sync_start_date=min_date if isinstance(min_date, date) else None,
                historical_synced_through=max_date if isinstance(max_date, date) else None,
            )
            summary["updated_count_by_grain"][grain] += 1

    return summary


def reconcile_platform_account_watermarks(
    conn,
    *,
    platform: str,
    account_id: str,
    grains: list[str] | None = None,
) -> dict[str, Any]:
    return reconcile_platform_account_watermarks_from_facts(
        conn,
        platform=platform,
        account_ids=[str(account_id)],
        grains=grains,
    )
