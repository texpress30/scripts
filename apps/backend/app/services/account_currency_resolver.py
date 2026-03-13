from __future__ import annotations


def normalize_currency_code(value: object, *, fallback: str = "USD") -> str:
    code = str(value or "").strip().upper()
    if len(code) == 3 and code.isalpha():
        return code
    return fallback


def resolve_effective_attached_account_currency(
    *,
    mapping_account_currency: object,
    platform_account_currency_code: object,
    client_currency: object,
    fallback: str,
) -> tuple[str, str]:
    mapping_code = str(mapping_account_currency or "").strip().upper()
    if len(mapping_code) == 3 and mapping_code.isalpha():
        return mapping_code, "mapping_account_currency"

    platform_code = str(platform_account_currency_code or "").strip().upper()
    if len(platform_code) == 3 and platform_code.isalpha():
        return platform_code, "platform_account_currency"

    client_code = str(client_currency or "").strip().upper()
    if len(client_code) == 3 and client_code.isalpha():
        return client_code, "client_currency"

    return normalize_currency_code(fallback, fallback="USD"), "fallback"


def sql_effective_attached_account_currency_expression(
    *,
    mapping_currency_expr: str,
    platform_currency_expr: str,
    client_currency_expr: str,
    fallback_literal: str,
) -> str:
    return (
        "COALESCE("
        f"NULLIF(TRIM({mapping_currency_expr}), ''), "
        f"NULLIF(TRIM({platform_currency_expr}), ''), "
        f"NULLIF(TRIM({client_currency_expr}), ''), "
        f"'{fallback_literal}'"
        ")"
    )


def resolve_client_reporting_currency(
    *,
    attached_effective_currencies: list[object],
    client_currency: object,
    fallback: str = "USD",
) -> tuple[str, str, bool, list[dict[str, object]]]:
    normalized: list[str] = []
    counts: dict[str, int] = {}
    for value in attached_effective_currencies:
        code = str(value or "").strip().upper()
        if len(code) == 3 and code.isalpha():
            normalized.append(code)
            counts[code] = counts.get(code, 0) + 1

    summary = [
        {"currency": currency, "account_count": counts[currency]}
        for currency in sorted(counts.keys())
    ]
    distinct = sorted(set(normalized))

    if len(distinct) == 1:
        return distinct[0], "single_attached_account_currency", False, summary

    client_code = str(client_currency or "").strip().upper()
    client_valid = len(client_code) == 3 and client_code.isalpha()
    if client_valid:
        if len(distinct) > 1:
            return client_code, "client_default_mixed_attached_currencies", True, summary
        return client_code, "client_default_no_attached_currency", False, summary

    return normalize_currency_code(fallback, fallback="USD"), "safe_fallback", len(distinct) > 1, summary
