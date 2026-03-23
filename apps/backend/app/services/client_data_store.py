from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

_SUPPORTED_SOURCES: tuple[tuple[str, str], ...] = (
    ("call_center", "Call Center"),
    ("direct", "Direct"),
    ("google_ads", "Google"),
    ("linkedin_ads", "LinkedIn"),
    ("meta_ads", "Meta"),
    ("organic", "Organic"),
    ("pinterest_ads", "Pinterest"),
    ("quora_ads", "Quora"),
    ("reddit_ads", "Reddit"),
    ("referral", "Referral"),
    ("snapchat_ads", "Snapchat"),
    ("taboola_ads", "Taboola"),
    ("tiktok_ads", "TikTok"),
    ("unknown", "Unknown"),
)

_SOURCE_LABEL_BY_KEY = {key: label for key, label in _SUPPORTED_SOURCES}


def _normalize_source_key(source_key: str | None) -> str:
    return (source_key or "").strip().lower()


def list_supported_sources() -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in _SUPPORTED_SOURCES]


def is_supported_source(source_key: str | None) -> bool:
    normalized = _normalize_source_key(source_key)
    return normalized in _SOURCE_LABEL_BY_KEY


def get_source_label(source_key: str | None) -> str | None:
    normalized = _normalize_source_key(source_key)
    if not normalized:
        return None
    return _SOURCE_LABEL_BY_KEY.get(normalized)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _sum_decimal_values(sale_entries: list[Mapping[str, Any]], key: str) -> Decimal:
    total = Decimal("0")
    for entry in sale_entries:
        total += _to_decimal(entry.get(key))
    return total


def compute_sales_count(sale_entries: list[Mapping[str, Any]]) -> int:
    return len(sale_entries)


def compute_revenue(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return _sum_decimal_values(sale_entries, "sale_price_amount")


def compute_cogs(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return _sum_decimal_values(sale_entries, "actual_price_amount")


def compute_custom_value_4(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return compute_revenue(sale_entries)


def compute_gross_profit(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return compute_revenue(sale_entries) - compute_cogs(sale_entries)
