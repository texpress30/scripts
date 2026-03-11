from __future__ import annotations

from datetime import date
from decimal import Decimal
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_TEMPLATE_TYPES = {"lead", "ecommerce", "programmatic"}
_DEFAULT_LABELS = {
    "custom_label_1": "Custom Value 1",
    "custom_label_2": "Custom Value 2",
    "custom_label_3": "Custom Value 3",
    "custom_label_4": "Custom Value 4",
    "custom_label_5": "Custom Value 5",
}


class MediaBuyingStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for media buying persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.media_buying_configs')")
                    config_row = cur.fetchone() or (None,)
                    cur.execute("SELECT to_regclass('public.media_buying_lead_daily_manual_values')")
                    manual_row = cur.fetchone() or (None,)
                    if config_row[0] is None or manual_row[0] is None:
                        raise RuntimeError("Database schema for media buying is not ready; run DB migrations")

            self._schema_initialized = True

    def _normalize_template_type(self, value: str | None) -> str:
        normalized = str(value or "lead").strip().lower()
        if normalized not in _TEMPLATE_TYPES:
            raise ValueError("template_type must be one of: lead, ecommerce, programmatic")
        return normalized

    def _normalize_currency(self, value: str | None) -> str:
        normalized = str(value or "RON").strip().upper()
        if len(normalized) != 3:
            raise ValueError("display_currency must be a 3-letter ISO currency code")
        return normalized

    def _normalize_label(self, value: str | None, *, fallback: str) -> str:
        normalized = str(value or fallback).strip()
        if not normalized:
            return fallback
        return normalized[:120]

    def _parse_non_negative_int(self, value: object, *, field_name: str) -> int:
        if value is None:
            return 0
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer >= 0")
        if not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer >= 0")
        if value < 0:
            raise ValueError(f"{field_name} must be an integer >= 0")
        return int(value)

    def _parse_amount(self, value: object, *, field_name: str, allow_negative: bool = False) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            parsed = Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{field_name} must be a valid number") from exc
        if not allow_negative and parsed < 0:
            raise ValueError(f"{field_name} must be >= 0")
        return parsed.quantize(Decimal("0.01"))

    def _config_from_row(self, row: tuple[object, ...] | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "client_id": int(row[0]),
            "template_type": str(row[1]),
            "display_currency": str(row[2]),
            "custom_label_1": str(row[3]),
            "custom_label_2": str(row[4]),
            "custom_label_3": str(row[5]),
            "custom_label_4": str(row[6]),
            "custom_label_5": str(row[7]),
            "enabled": bool(row[8]),
            "created_at": str(row[9]) if row[9] is not None else None,
            "updated_at": str(row[10]) if row[10] is not None else None,
        }

    def _daily_from_row(self, row: tuple[object, ...]) -> dict[str, object]:
        return {
            "client_id": int(row[0]),
            "date": str(row[1]),
            "leads": int(row[2]),
            "phones": int(row[3]),
            "custom_value_1_count": int(row[4]),
            "custom_value_2_count": int(row[5]),
            "custom_value_3_amount_ron": float(row[6]),
            "custom_value_4_amount_ron": float(row[7]),
            "custom_value_5_amount_ron": float(row[8]),
            "sales_count": int(row[9]),
            "created_at": str(row[10]) if row[10] is not None else None,
            "updated_at": str(row[11]) if row[11] is not None else None,
            # TODO(media-buying): `%^` column formula intentionally not implemented in foundation task.
        }

    def get_config(self, *, client_id: int) -> dict[str, object]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        client_id,
                        template_type,
                        display_currency,
                        custom_label_1,
                        custom_label_2,
                        custom_label_3,
                        custom_label_4,
                        custom_label_5,
                        enabled,
                        created_at,
                        updated_at
                    FROM media_buying_configs
                    WHERE client_id = %s
                    """,
                    (int(client_id),),
                )
                row = cur.fetchone()

        payload = self._config_from_row(row)
        if payload is not None:
            return payload

        return {
            "client_id": int(client_id),
            "template_type": "lead",
            "display_currency": "RON",
            "custom_label_1": _DEFAULT_LABELS["custom_label_1"],
            "custom_label_2": _DEFAULT_LABELS["custom_label_2"],
            "custom_label_3": _DEFAULT_LABELS["custom_label_3"],
            "custom_label_4": _DEFAULT_LABELS["custom_label_4"],
            "custom_label_5": _DEFAULT_LABELS["custom_label_5"],
            "enabled": True,
            "created_at": None,
            "updated_at": None,
        }

    def upsert_config(
        self,
        *,
        client_id: int,
        template_type: str | None = None,
        display_currency: str | None = None,
        custom_label_1: str | None = None,
        custom_label_2: str | None = None,
        custom_label_3: str | None = None,
        custom_label_4: str | None = None,
        custom_label_5: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, object]:
        self._ensure_schema()
        current = self.get_config(client_id=int(client_id))

        next_template_type = self._normalize_template_type(template_type or str(current["template_type"]))
        next_currency = self._normalize_currency(display_currency or str(current["display_currency"]))

        # Lead template default display currency is RON when creating first config.
        if current.get("created_at") is None and template_type is None and display_currency is None:
            next_template_type = "lead"
            next_currency = "RON"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO media_buying_configs (
                        client_id,
                        template_type,
                        display_currency,
                        custom_label_1,
                        custom_label_2,
                        custom_label_3,
                        custom_label_4,
                        custom_label_5,
                        enabled
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id)
                    DO UPDATE SET
                        template_type = EXCLUDED.template_type,
                        display_currency = EXCLUDED.display_currency,
                        custom_label_1 = EXCLUDED.custom_label_1,
                        custom_label_2 = EXCLUDED.custom_label_2,
                        custom_label_3 = EXCLUDED.custom_label_3,
                        custom_label_4 = EXCLUDED.custom_label_4,
                        custom_label_5 = EXCLUDED.custom_label_5,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    (
                        int(client_id),
                        next_template_type,
                        next_currency,
                        self._normalize_label(custom_label_1, fallback=str(current["custom_label_1"])),
                        self._normalize_label(custom_label_2, fallback=str(current["custom_label_2"])),
                        self._normalize_label(custom_label_3, fallback=str(current["custom_label_3"])),
                        self._normalize_label(custom_label_4, fallback=str(current["custom_label_4"])),
                        self._normalize_label(custom_label_5, fallback=str(current["custom_label_5"])),
                        bool(current["enabled"]) if enabled is None else bool(enabled),
                    ),
                )
            conn.commit()

        return self.get_config(client_id=int(client_id))

    def list_lead_daily_manual_values(
        self,
        *,
        client_id: int,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        if date_from > date_to:
            raise ValueError("date_from must be less than or equal to date_to")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        client_id,
                        metric_date,
                        leads,
                        phones,
                        custom_value_1_count,
                        custom_value_2_count,
                        custom_value_3_amount_ron,
                        custom_value_4_amount_ron,
                        custom_value_5_amount_ron,
                        sales_count,
                        created_at,
                        updated_at
                    FROM media_buying_lead_daily_manual_values
                    WHERE client_id = %s
                      AND metric_date >= %s
                      AND metric_date <= %s
                    ORDER BY metric_date ASC
                    """,
                    (int(client_id), date_from, date_to),
                )
                rows = cur.fetchall() or []

        return [self._daily_from_row(row) for row in rows]

    def upsert_lead_daily_manual_value(
        self,
        *,
        client_id: int,
        metric_date: date,
        leads: object,
        phones: object,
        custom_value_1_count: object,
        custom_value_2_count: object,
        custom_value_3_amount_ron: object,
        custom_value_4_amount_ron: object,
        custom_value_5_amount_ron: object,
        sales_count: object,
    ) -> dict[str, object]:
        self._ensure_schema()

        parsed_leads = self._parse_non_negative_int(leads, field_name="leads")
        parsed_phones = self._parse_non_negative_int(phones, field_name="phones")
        parsed_cv1 = self._parse_non_negative_int(custom_value_1_count, field_name="custom_value_1_count")
        parsed_cv2 = self._parse_non_negative_int(custom_value_2_count, field_name="custom_value_2_count")
        parsed_cv3 = self._parse_amount(custom_value_3_amount_ron, field_name="custom_value_3_amount_ron")
        parsed_cv4 = self._parse_amount(custom_value_4_amount_ron, field_name="custom_value_4_amount_ron")
        parsed_cv5 = self._parse_amount(custom_value_5_amount_ron, field_name="custom_value_5_amount_ron", allow_negative=True)
        parsed_sales = self._parse_non_negative_int(sales_count, field_name="sales_count")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO media_buying_lead_daily_manual_values (
                        client_id,
                        metric_date,
                        leads,
                        phones,
                        custom_value_1_count,
                        custom_value_2_count,
                        custom_value_3_amount_ron,
                        custom_value_4_amount_ron,
                        custom_value_5_amount_ron,
                        sales_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id, metric_date)
                    DO UPDATE SET
                        leads = EXCLUDED.leads,
                        phones = EXCLUDED.phones,
                        custom_value_1_count = EXCLUDED.custom_value_1_count,
                        custom_value_2_count = EXCLUDED.custom_value_2_count,
                        custom_value_3_amount_ron = EXCLUDED.custom_value_3_amount_ron,
                        custom_value_4_amount_ron = EXCLUDED.custom_value_4_amount_ron,
                        custom_value_5_amount_ron = EXCLUDED.custom_value_5_amount_ron,
                        sales_count = EXCLUDED.sales_count,
                        updated_at = NOW()
                    """,
                    (
                        int(client_id),
                        metric_date,
                        parsed_leads,
                        parsed_phones,
                        parsed_cv1,
                        parsed_cv2,
                        parsed_cv3,
                        parsed_cv4,
                        parsed_cv5,
                        parsed_sales,
                    ),
                )
                cur.execute(
                    """
                    SELECT
                        client_id,
                        metric_date,
                        leads,
                        phones,
                        custom_value_1_count,
                        custom_value_2_count,
                        custom_value_3_amount_ron,
                        custom_value_4_amount_ron,
                        custom_value_5_amount_ron,
                        sales_count,
                        created_at,
                        updated_at
                    FROM media_buying_lead_daily_manual_values
                    WHERE client_id = %s AND metric_date = %s
                    """,
                    (int(client_id), metric_date),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to persist media buying lead daily manual value")
        return self._daily_from_row(row)


media_buying_store = MediaBuyingStore()
