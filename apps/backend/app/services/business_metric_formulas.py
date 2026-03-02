from __future__ import annotations

from typing import Any

BUSINESS_DERIVED_METRICS_IMPLEMENTED: tuple[str, ...] = (
    "mer",
    "cost_per_applicant",
    "cost_per_approved_applicant",
    "cost_vs_actual_revenue",
    "gross_profit_margin",
    "contribution_profit_margin",
    "total_cogs_and_taxes",
    "target_attainment",
    "revenue_gap",
    "aov",
    "cost_per_sale",
    "applicants_per_sale",
    "approved_applicants_per_sale",
    "approval_rate",
    "gross_profit_per_sale",
    "contribution_profit_per_sale",
    "ncac",
)

BUSINESS_DERIVED_METRICS_DEFERRED: tuple[str, ...] = (
    "cvr_lpv_to_sale",
    "new_net",
)


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


def safe_add(a: Any, b: Any) -> float | None:
    av = _to_number(a)
    bv = _to_number(b)
    if av is None and bv is None:
        return None
    return float(av or 0.0) + float(bv or 0.0)


def build_business_derived_metrics(
    *,
    total_spend: Any,
    actual_revenue: Any,
    target_revenue: Any,
    applicants: Any,
    approved_applicants: Any,
    cogs: Any,
    taxes: Any,
    gross_profit: Any,
    contribution_profit: Any,
    sales_count: Any,
    new_customers: Any,
) -> dict[str, float | None]:
    spend_v = _to_number(total_spend)
    actual_revenue_v = _to_number(actual_revenue)
    target_revenue_v = _to_number(target_revenue)
    applicants_v = _to_number(applicants)
    approved_applicants_v = _to_number(approved_applicants)
    cogs_v = _to_number(cogs)
    taxes_v = _to_number(taxes)
    gross_profit_v = _to_number(gross_profit)
    contribution_profit_v = _to_number(contribution_profit)
    sales_count_v = _to_number(sales_count)
    new_customers_v = _to_number(new_customers)

    revenue_gap = None
    if target_revenue_v is not None and actual_revenue_v is not None:
        revenue_gap = target_revenue_v - actual_revenue_v

    return {
        "mer": safe_divide(actual_revenue_v, spend_v),
        "cost_per_applicant": safe_divide(spend_v, applicants_v),
        "cost_per_approved_applicant": safe_divide(spend_v, approved_applicants_v),
        "cost_vs_actual_revenue": safe_divide(spend_v, actual_revenue_v),
        "gross_profit_margin": safe_divide(gross_profit_v, actual_revenue_v),
        "contribution_profit_margin": safe_divide(contribution_profit_v, actual_revenue_v),
        "total_cogs_and_taxes": safe_add(cogs_v, taxes_v),
        "target_attainment": safe_divide(actual_revenue_v, target_revenue_v),
        "revenue_gap": revenue_gap,
        "aov": safe_divide(actual_revenue_v, sales_count_v),
        "cost_per_sale": safe_divide(spend_v, sales_count_v),
        "applicants_per_sale": safe_divide(applicants_v, sales_count_v),
        "approved_applicants_per_sale": safe_divide(approved_applicants_v, sales_count_v),
        "approval_rate": safe_divide(approved_applicants_v, applicants_v),
        "gross_profit_per_sale": safe_divide(gross_profit_v, sales_count_v),
        "contribution_profit_per_sale": safe_divide(contribution_profit_v, sales_count_v),
        "ncac": safe_divide(spend_v, new_customers_v),
    }
