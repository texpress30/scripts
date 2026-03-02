from __future__ import annotations

from datetime import date
from typing import Any
import json

from app.services.client_business_inputs_store import client_business_inputs_store


class ClientBusinessInputValidationError(ValueError):
    pass


def _empty_to_none(value: object) -> object:
    if isinstance(value, str):
        trimmed = value.strip()
        return None if trimmed == "" else trimmed
    return value


def _parse_date(value: object) -> date | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ClientBusinessInputValidationError("invalid date value")


def _parse_int(value: object) -> int | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ClientBusinessInputValidationError("invalid integer value")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value))
    raise ClientBusinessInputValidationError("invalid integer value")


def _parse_float(value: object) -> float | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ClientBusinessInputValidationError("invalid numeric value")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ClientBusinessInputValidationError("invalid numeric value")


def _parse_metadata(value: object) -> dict[str, object]:
    value = _empty_to_none(value)
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {str(k): v for k, v in parsed.items()}
    raise ClientBusinessInputValidationError("invalid metadata value")


def normalize_client_business_input_row(
    raw_row: dict[str, object],
    *,
    default_client_id: int | None = None,
    default_period_grain: str | None = None,
    default_source: str = "manual",
) -> dict[str, object]:
    row = dict(raw_row)

    raw_client_id = _empty_to_none(row.get("client_id"))
    client_id = _parse_int(raw_client_id if raw_client_id is not None else default_client_id)

    raw_grain = _empty_to_none(row.get("period_grain"))
    resolved_grain = str(raw_grain if raw_grain is not None else (default_period_grain or "")).strip().lower()
    resolved_grain = resolved_grain if resolved_grain != "" else None

    period_start = _parse_date(row.get("period_start"))
    period_end = _parse_date(row.get("period_end"))
    if resolved_grain == "day" and period_start is not None and period_end is None:
        period_end = period_start

    source_raw = _empty_to_none(row.get("source"))
    source = str(source_raw if source_raw is not None else default_source).strip() or "manual"

    normalized = {
        "client_id": client_id,
        "period_start": period_start,
        "period_end": period_end,
        "period_grain": resolved_grain,
        "applicants": _parse_int(row.get("applicants")),
        "approved_applicants": _parse_int(row.get("approved_applicants")),
        "actual_revenue": _parse_float(row.get("actual_revenue")),
        "target_revenue": _parse_float(row.get("target_revenue")),
        "cogs": _parse_float(row.get("cogs")),
        "taxes": _parse_float(row.get("taxes")),
        "gross_profit": _parse_float(row.get("gross_profit")),
        "contribution_profit": _parse_float(row.get("contribution_profit")),
        "sales_count": _parse_int(row.get("sales_count")),
        "new_customers": _parse_int(row.get("new_customers")),
        "notes": _empty_to_none(row.get("notes")),
        "source": source,
        "metadata": _parse_metadata(row.get("metadata")),
    }
    return normalized


def validate_client_business_input_row(row: dict[str, object]) -> None:
    client_id = row.get("client_id")
    period_start = row.get("period_start")
    period_end = row.get("period_end")
    period_grain = row.get("period_grain")

    if not isinstance(client_id, int) or client_id <= 0:
        raise ClientBusinessInputValidationError("client_id is required")
    if not isinstance(period_start, date):
        raise ClientBusinessInputValidationError("period_start is required")
    if not isinstance(period_end, date):
        raise ClientBusinessInputValidationError("period_end is required")
    if period_grain not in ("day", "week"):
        raise ClientBusinessInputValidationError("period_grain must be one of: day, week")
    if period_end < period_start:
        raise ClientBusinessInputValidationError("period_end must be greater than or equal to period_start")
    if period_grain == "day" and period_start != period_end:
        raise ClientBusinessInputValidationError("for day period_grain, period_start must be equal to period_end")

    sales_count = row.get("sales_count")
    new_customers = row.get("new_customers")
    if sales_count is not None:
        if not isinstance(sales_count, int) or sales_count < 0:
            raise ClientBusinessInputValidationError("sales_count must be >= 0 when provided")
    if new_customers is not None:
        if not isinstance(new_customers, int) or new_customers < 0:
            raise ClientBusinessInputValidationError("new_customers must be >= 0 when provided")


def import_client_business_inputs(
    rows: list[dict[str, object]],
    *,
    default_client_id: int | None = None,
    default_period_grain: str | None = None,
    default_source: str = "manual",
) -> dict[str, object]:
    processed = 0
    succeeded = 0
    failed = 0
    errors: list[dict[str, object]] = []
    imported_rows: list[dict[str, object]] = []

    for index, raw_row in enumerate(rows):
        processed += 1
        try:
            normalized = normalize_client_business_input_row(
                raw_row,
                default_client_id=default_client_id,
                default_period_grain=default_period_grain,
                default_source=default_source,
            )
            validate_client_business_input_row(normalized)
            saved = client_business_inputs_store.upsert_client_business_input(**normalized)
            if saved is not None:
                imported_rows.append(saved)
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(
                {
                    "row_index": index,
                    "message": str(exc)[:300],
                }
            )

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "rows": imported_rows,
        "errors": errors,
    }


class ClientBusinessInputsImportService:
    def normalize_client_business_input_row(
        self,
        raw_row: dict[str, object],
        *,
        default_client_id: int | None = None,
        default_period_grain: str | None = None,
        default_source: str = "manual",
    ) -> dict[str, object]:
        return normalize_client_business_input_row(
            raw_row,
            default_client_id=default_client_id,
            default_period_grain=default_period_grain,
            default_source=default_source,
        )

    def validate_client_business_input_row(self, row: dict[str, object]) -> None:
        validate_client_business_input_row(row)

    def import_client_business_inputs(
        self,
        rows: list[dict[str, object]],
        *,
        default_client_id: int | None = None,
        default_period_grain: str | None = None,
        default_source: str = "manual",
    ) -> dict[str, object]:
        return import_client_business_inputs(
            rows,
            default_client_id=default_client_id,
            default_period_grain=default_period_grain,
            default_source=default_source,
        )


client_business_inputs_import_service = ClientBusinessInputsImportService()
