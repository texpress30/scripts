from __future__ import annotations

from datetime import date
import json
from typing import Any


_CAMPAIGN_UPSERT_SQL = """
INSERT INTO campaign_performance_reports (
    platform,
    account_id,
    campaign_id,
    report_date,
    spend,
    impressions,
    clicks,
    conversions,
    conversion_value,
    extra_metrics,
    source_window_start,
    source_window_end,
    source_job_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
)
ON CONFLICT (platform, account_id, campaign_id, report_date)
DO UPDATE SET
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    clicks = EXCLUDED.clicks,
    conversions = EXCLUDED.conversions,
    conversion_value = EXCLUDED.conversion_value,
    extra_metrics = EXCLUDED.extra_metrics,
    source_window_start = EXCLUDED.source_window_start,
    source_window_end = EXCLUDED.source_window_end,
    source_job_id = EXCLUDED.source_job_id,
    ingested_at = NOW()
"""

_AD_GROUP_UPSERT_SQL = """
INSERT INTO ad_group_performance_reports (
    platform,
    account_id,
    ad_group_id,
    campaign_id,
    report_date,
    spend,
    impressions,
    clicks,
    conversions,
    conversion_value,
    extra_metrics,
    source_window_start,
    source_window_end,
    source_job_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
)
ON CONFLICT (platform, account_id, ad_group_id, report_date)
DO UPDATE SET
    campaign_id = EXCLUDED.campaign_id,
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    clicks = EXCLUDED.clicks,
    conversions = EXCLUDED.conversions,
    conversion_value = EXCLUDED.conversion_value,
    extra_metrics = EXCLUDED.extra_metrics,
    source_window_start = EXCLUDED.source_window_start,
    source_window_end = EXCLUDED.source_window_end,
    source_job_id = EXCLUDED.source_job_id,
    ingested_at = NOW()
"""

_AD_UNIT_UPSERT_SQL = """
INSERT INTO ad_unit_performance_reports (
    platform,
    account_id,
    ad_id,
    campaign_id,
    ad_group_id,
    report_date,
    spend,
    impressions,
    clicks,
    conversions,
    conversion_value,
    extra_metrics,
    source_window_start,
    source_window_end,
    source_job_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
)
ON CONFLICT (platform, account_id, ad_id, report_date)
DO UPDATE SET
    campaign_id = EXCLUDED.campaign_id,
    ad_group_id = EXCLUDED.ad_group_id,
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    clicks = EXCLUDED.clicks,
    conversions = EXCLUDED.conversions,
    conversion_value = EXCLUDED.conversion_value,
    extra_metrics = EXCLUDED.extra_metrics,
    source_window_start = EXCLUDED.source_window_start,
    source_window_end = EXCLUDED.source_window_end,
    source_job_id = EXCLUDED.source_job_id,
    ingested_at = NOW()
"""


_KEYWORD_UPSERT_SQL = """
INSERT INTO keyword_performance_reports (
    platform,
    account_id,
    keyword_id,
    report_date,
    campaign_id,
    ad_group_id,
    spend,
    impressions,
    clicks,
    conversions,
    conversion_value,
    extra_metrics,
    source_window_start,
    source_window_end,
    source_job_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
)
ON CONFLICT (platform, account_id, keyword_id, report_date)
DO UPDATE SET
    campaign_id = EXCLUDED.campaign_id,
    ad_group_id = EXCLUDED.ad_group_id,
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    clicks = EXCLUDED.clicks,
    conversions = EXCLUDED.conversions,
    conversion_value = EXCLUDED.conversion_value,
    extra_metrics = EXCLUDED.extra_metrics,
    source_window_start = EXCLUDED.source_window_start,
    source_window_end = EXCLUDED.source_window_end,
    source_job_id = EXCLUDED.source_job_id,
    ingested_at = NOW()
"""


def _normalized_extra_metrics(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {})


def _to_date_or_none(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def upsert_campaign_performance_reports(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("campaign_id") or ""),
            _to_date_or_none(row.get("report_date")),
            float(row.get("spend", 0) or 0),
            int(row.get("impressions", 0) or 0),
            int(row.get("clicks", 0) or 0),
            float(row.get("conversions", 0) or 0),
            float(row.get("conversion_value", 0) or 0),
            _normalized_extra_metrics(row.get("extra_metrics")),
            _to_date_or_none(row.get("source_window_start")),
            _to_date_or_none(row.get("source_window_end")),
            row.get("source_job_id"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_CAMPAIGN_UPSERT_SQL, params)
    return len(params)


def upsert_ad_group_performance_reports(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("ad_group_id") or ""),
            row.get("campaign_id"),
            _to_date_or_none(row.get("report_date")),
            float(row.get("spend", 0) or 0),
            int(row.get("impressions", 0) or 0),
            int(row.get("clicks", 0) or 0),
            float(row.get("conversions", 0) or 0),
            float(row.get("conversion_value", 0) or 0),
            _normalized_extra_metrics(row.get("extra_metrics")),
            _to_date_or_none(row.get("source_window_start")),
            _to_date_or_none(row.get("source_window_end")),
            row.get("source_job_id"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_AD_GROUP_UPSERT_SQL, params)
    return len(params)


def upsert_ad_unit_performance_reports(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("ad_id") or ""),
            row.get("campaign_id"),
            row.get("ad_group_id"),
            _to_date_or_none(row.get("report_date")),
            float(row.get("spend", 0) or 0),
            int(row.get("impressions", 0) or 0),
            int(row.get("clicks", 0) or 0),
            float(row.get("conversions", 0) or 0),
            float(row.get("conversion_value", 0) or 0),
            _normalized_extra_metrics(row.get("extra_metrics")),
            _to_date_or_none(row.get("source_window_start")),
            _to_date_or_none(row.get("source_window_end")),
            row.get("source_job_id"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_AD_UNIT_UPSERT_SQL, params)
    return len(params)


def upsert_keyword_performance_reports(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("keyword_id") or ""),
            _to_date_or_none(row.get("report_date")),
            row.get("campaign_id"),
            row.get("ad_group_id"),
            float(row.get("spend", 0) or 0),
            int(row.get("impressions", 0) or 0),
            int(row.get("clicks", 0) or 0),
            float(row.get("conversions", 0) or 0),
            float(row.get("conversion_value", 0) or 0),
            _normalized_extra_metrics(row.get("extra_metrics")),
            _to_date_or_none(row.get("source_window_start")),
            _to_date_or_none(row.get("source_window_end")),
            row.get("source_job_id"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_KEYWORD_UPSERT_SQL, params)
    return len(params)
