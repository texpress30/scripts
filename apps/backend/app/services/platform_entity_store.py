from __future__ import annotations

import json
from typing import Any


_CAMPAIGN_UPSERT_SQL = """
INSERT INTO platform_campaigns (
    platform,
    account_id,
    account_id_norm,
    campaign_id,
    name,
    status,
    raw_payload,
    payload_hash
) VALUES (
    %s, %s, regexp_replace(COALESCE(%s, ''), '[^0-9]', '', 'g'), %s, %s, %s, %s::jsonb, %s
)
ON CONFLICT (platform, account_id, campaign_id)
DO UPDATE SET
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload,
    payload_hash = EXCLUDED.payload_hash,
    account_id_norm = EXCLUDED.account_id_norm,
    fetched_at = NOW(),
    last_seen_at = NOW()
"""

_AD_GROUP_UPSERT_SQL = """
INSERT INTO platform_ad_groups (
    platform,
    account_id,
    account_id_norm,
    ad_group_id,
    campaign_id,
    name,
    status,
    raw_payload,
    payload_hash
) VALUES (
    %s, %s, regexp_replace(COALESCE(%s, ''), '[^0-9]', '', 'g'), %s, %s, %s, %s, %s::jsonb, %s
)
ON CONFLICT (platform, account_id, ad_group_id)
DO UPDATE SET
    campaign_id = EXCLUDED.campaign_id,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload,
    payload_hash = EXCLUDED.payload_hash,
    account_id_norm = EXCLUDED.account_id_norm,
    fetched_at = NOW(),
    last_seen_at = NOW()
"""

_AD_UPSERT_SQL = """
INSERT INTO platform_ads (
    platform,
    account_id,
    ad_id,
    ad_group_id,
    campaign_id,
    name,
    status,
    raw_payload,
    payload_hash
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
)
ON CONFLICT (platform, account_id, ad_id)
DO UPDATE SET
    ad_group_id = EXCLUDED.ad_group_id,
    campaign_id = EXCLUDED.campaign_id,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload,
    payload_hash = EXCLUDED.payload_hash,
    fetched_at = NOW(),
    last_seen_at = NOW()
"""

_KEYWORD_UPSERT_SQL = """
INSERT INTO platform_keywords (
    platform,
    account_id,
    keyword_id,
    campaign_id,
    ad_group_id,
    keyword_text,
    match_type,
    status,
    raw_payload,
    payload_hash
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
)
ON CONFLICT (platform, account_id, keyword_id)
DO UPDATE SET
    campaign_id = EXCLUDED.campaign_id,
    ad_group_id = EXCLUDED.ad_group_id,
    keyword_text = EXCLUDED.keyword_text,
    match_type = EXCLUDED.match_type,
    status = EXCLUDED.status,
    raw_payload = EXCLUDED.raw_payload,
    payload_hash = EXCLUDED.payload_hash,
    fetched_at = NOW(),
    last_seen_at = NOW()
"""


def _to_json(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {})


def upsert_platform_campaigns(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("account_id") or ""),
            str(row.get("campaign_id") or ""),
            row.get("name"),
            row.get("status"),
            _to_json(row.get("raw_payload")),
            row.get("payload_hash"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_CAMPAIGN_UPSERT_SQL, params)
    return len(params)


def upsert_platform_ad_groups(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("account_id") or ""),
            str(row.get("ad_group_id") or ""),
            row.get("campaign_id"),
            row.get("name"),
            row.get("status"),
            _to_json(row.get("raw_payload")),
            row.get("payload_hash"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_AD_GROUP_UPSERT_SQL, params)
    return len(params)


def upsert_platform_ads(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("ad_id") or ""),
            row.get("ad_group_id"),
            row.get("campaign_id"),
            row.get("name"),
            row.get("status"),
            _to_json(row.get("raw_payload")),
            row.get("payload_hash"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_AD_UPSERT_SQL, params)
    return len(params)


def upsert_platform_keywords(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    params = [
        (
            str(row.get("platform") or ""),
            str(row.get("account_id") or ""),
            str(row.get("keyword_id") or ""),
            row.get("campaign_id"),
            row.get("ad_group_id"),
            row.get("keyword_text"),
            row.get("match_type"),
            row.get("status"),
            _to_json(row.get("raw_payload")),
            row.get("payload_hash"),
        )
        for row in rows
    ]

    with conn.cursor() as cursor:
        cursor.executemany(_KEYWORD_UPSERT_SQL, params)
    return len(params)
