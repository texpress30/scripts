from __future__ import annotations

from typing import Any


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    num = _to_number(numerator)
    den = _to_number(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def safe_rate(numerator: Any, denominator: Any) -> float | None:
    return safe_divide(numerator, denominator)


def _nested_number(payload: dict[str, object], *path: str) -> float | None:
    current: object = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _to_number(current)


def common_derived_metrics(*, spend: Any, impressions: Any, clicks: Any, conversions: Any, conversion_value: Any) -> dict[str, float | None]:
    spend_v = _to_number(spend)
    impressions_v = _to_number(impressions)
    clicks_v = _to_number(clicks)
    conversions_v = _to_number(conversions)
    conversion_value_v = _to_number(conversion_value)
    cpm = None
    if spend_v is not None and impressions_v is not None:
        cpm = safe_divide(spend_v * 1000.0, impressions_v)

    return {
        "ctr": safe_rate(clicks_v, impressions_v),
        "cpc": safe_divide(spend_v, clicks_v),
        "cpm": cpm,
        "cpa": safe_divide(spend_v, conversions_v),
        "roas": safe_divide(conversion_value_v, spend_v),
        "cost_vs_revenue": safe_divide(spend_v, conversion_value_v),
    }


def google_derived_metrics(extra_metrics: dict[str, object]) -> dict[str, float | None]:
    search_spend = _nested_number(extra_metrics, "google_ads", "search_spend")
    search_clicks = _nested_number(extra_metrics, "google_ads", "search_clicks")
    search_impressions = _nested_number(extra_metrics, "google_ads", "search_impressions")
    pmax_spend = _nested_number(extra_metrics, "google_ads", "pmax_spend")
    pmax_clicks = _nested_number(extra_metrics, "google_ads", "pmax_clicks")
    pmax_impressions = _nested_number(extra_metrics, "google_ads", "pmax_impressions")

    cpm_search = safe_divide(search_spend * 1000.0, search_impressions) if search_spend is not None and search_impressions is not None else None
    cpm_pmax = safe_divide(pmax_spend * 1000.0, pmax_impressions) if pmax_spend is not None and pmax_impressions is not None else None

    return {
        "cpc_search": safe_divide(search_spend, search_clicks),
        "cpc_pmax": safe_divide(pmax_spend, pmax_clicks),
        "cpm_search": cpm_search,
        "cpm_pmax": cpm_pmax,
        "ctr_search": safe_rate(search_clicks, search_impressions),
        "ctr_pmax": safe_rate(pmax_clicks, pmax_impressions),
    }


def meta_derived_metrics(*, spend: Any, extra_metrics: dict[str, object]) -> dict[str, float | None]:
    spend_v = _to_number(spend)
    lpv = _nested_number(extra_metrics, "meta_ads", "landing_page_views")
    outbound_clicks = _nested_number(extra_metrics, "meta_ads", "outbound_clicks")
    link_clicks = _nested_number(extra_metrics, "meta_ads", "link_clicks")
    purchases = _nested_number(extra_metrics, "meta_ads", "purchases")
    purchase_value = _nested_number(extra_metrics, "meta_ads", "purchase_value")

    lp_view_rate = safe_rate(lpv, outbound_clicks)
    if lp_view_rate is None:
        lp_view_rate = safe_rate(lpv, link_clicks)

    return {
        "lp_view_rate": lp_view_rate,
        "cp_landing_page_view": safe_divide(spend_v, lpv),
        "aov": safe_divide(purchase_value, purchases),
    }


def tiktok_derived_metrics(*, spend: Any, extra_metrics: dict[str, object]) -> dict[str, float | None]:
    spend_v = _to_number(spend)
    lpv = _nested_number(extra_metrics, "tiktok_ads", "landing_page_views")
    destination_clicks = _nested_number(extra_metrics, "tiktok_ads", "destination_clicks")
    purchases = _nested_number(extra_metrics, "tiktok_ads", "purchases")
    purchase_value = _nested_number(extra_metrics, "tiktok_ads", "purchase_value")

    return {
        "lp_view_rate": safe_rate(lpv, destination_clicks),
        "cp_landing_page_view": safe_divide(spend_v, lpv),
        "aov": safe_divide(purchase_value, purchases),
    }


def build_derived_metrics(*, platform: str, spend: Any, impressions: Any, clicks: Any, conversions: Any, conversion_value: Any, extra_metrics: dict[str, object] | None) -> dict[str, float | None]:
    extra = extra_metrics if isinstance(extra_metrics, dict) else {}
    derived = common_derived_metrics(
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        conversion_value=conversion_value,
    )

    if platform == "google_ads":
        derived.update(google_derived_metrics(extra))
    elif platform == "meta_ads":
        derived.update(meta_derived_metrics(spend=spend, extra_metrics=extra))
    elif platform == "tiktok_ads":
        derived.update(tiktok_derived_metrics(spend=spend, extra_metrics=extra))

    return derived
