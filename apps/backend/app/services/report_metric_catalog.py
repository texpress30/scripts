from __future__ import annotations

DERIVED_METRICS_IMPLEMENTED: tuple[str, ...] = (
    "ctr",
    "cpc",
    "cpm",
    "cpa",
    "roas",
    "cost_vs_revenue",
    "lp_view_rate",
    "cp_landing_page_view",
    "cpc_search",
    "cpc_pmax",
    "cpm_search",
    "cpm_pmax",
    "aov",
)

MANUAL_BUSINESS_METRICS_EXCLUDED: tuple[str, ...] = (
    "applicants",
    "approved_applicants",
    "gross_profit",
    "contribution_profit",
    "cogs",
    "taxes",
    "target_revenue",
    "ncac",
    "mer",
)
