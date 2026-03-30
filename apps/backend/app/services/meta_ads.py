from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
import math
import re
from typing import Literal
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.entity_performance_reports import (
    upsert_ad_group_performance_reports,
    upsert_ad_unit_performance_reports,
    upsert_campaign_performance_reports,
)
from app.services.error_observability import safe_body_snippet, sanitize_payload, sanitize_text
from app.services.integration_secrets_store import integration_secrets_store, generate_oauth_state, verify_oauth_state
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

MetaSyncGrain = Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]
_ALLOWED_SYNC_GRAINS: tuple[str, ...] = ("account_daily", "campaign_daily", "ad_group_daily", "ad_daily")
_META_LEAD_ACTION_TYPE_PRIORITY: tuple[str, ...] = (
    "lead",
    "onsite_conversion.lead_grouped",
    "onsite_conversion.lead",
    "offsite_conversion.lead",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.fb_pixel_custom_lead",
    "offsite_conversion.meta_lead",
    "offsite_conversion.meta_pixel_lead",
)
_META_LEAD_ACTION_TYPES: set[str] = set(_META_LEAD_ACTION_TYPE_PRIORITY)
_META_ACCOUNT_DAILY_CHUNK_DAYS = 7
_ENTITY_NUMERIC_ABS_LIMIT = 10_000_000_000.0


logger = logging.getLogger(__name__)


class MetaAdsIntegrationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        http_status: int | None = None,
        provider_error_code: str | None = None,
        provider_error_message: str | None = None,
        body_snippet: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(sanitize_text(message, max_len=400))
        self.endpoint = sanitize_text(endpoint or "", max_len=200) or None
        self.http_status = int(http_status) if http_status is not None else None
        self.provider_error_code = sanitize_text(provider_error_code, max_len=80) if provider_error_code is not None else None
        self.provider_error_message = sanitize_text(provider_error_message, max_len=300) if provider_error_message is not None else None
        self.body_snippet = sanitize_text(body_snippet, max_len=400) if body_snippet is not None else None
        self.retryable = retryable

    def to_details(self) -> dict[str, object]:
        return {
            "error_summary": sanitize_text(str(self), max_len=300),
            "provider_error_code": self.provider_error_code,
            "provider_error_message": self.provider_error_message,
            "http_status": self.http_status,
            "endpoint": self.endpoint,
            "retryable": self.retryable,
            "body_snippet": self.body_snippet,
        }


class MetaAdsService:
    def __init__(self) -> None:
        self._memory_campaign_daily_rows: list[dict[str, object]] = []
        self._memory_ad_group_daily_rows: list[dict[str, object]] = []
        self._memory_ad_daily_rows: list[dict[str, object]] = []

    def _is_test_mode(self) -> bool:
        settings = load_settings()
        return settings.app_env == "test"

    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _is_placeholder(self, value: str) -> bool:
        normalized = value.strip().lower()
        return normalized == "" or normalized.startswith("your_")

    def _oauth_configured(self) -> bool:
        settings = load_settings()
        return not (
            self._is_placeholder(settings.meta_app_id)
            or self._is_placeholder(settings.meta_app_secret)
            or self._is_placeholder(settings.meta_redirect_uri)
        )

    def _http_json(self, *, method: str, url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
        req = request.Request(url=url, method=method.upper())
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        try:
            with request.urlopen(req, timeout=20) as response:  # noqa: S310
                data = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raw_body = ""
            try:
                raw_body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                raw_body = ""
            provider_code = None
            provider_message = None
            if raw_body:
                try:
                    parsed = json.loads(raw_body)
                    error_payload = parsed.get("error") if isinstance(parsed, dict) else None
                    if isinstance(error_payload, dict):
                        provider_code = error_payload.get("code")
                        provider_message = error_payload.get("message")
                except Exception:  # noqa: BLE001
                    provider_code = None
                    provider_message = None
            raise MetaAdsIntegrationError(
                f"Meta HTTP request failed: status={exc.code}",
                endpoint=url,
                http_status=exc.code,
                provider_error_code=sanitize_text(provider_code, max_len=80) if provider_code is not None else None,
                provider_error_message=sanitize_text(provider_message, max_len=300) if provider_message is not None else None,
                body_snippet=safe_body_snippet(raw_body),
                retryable=exc.code >= 500,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise MetaAdsIntegrationError(
                f"Meta HTTP request failed: {sanitize_text(exc, max_len=200)}",
                endpoint=url,
                retryable=True,
            ) from exc

        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise MetaAdsIntegrationError("Meta API returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise MetaAdsIntegrationError("Meta API response shape is invalid")
        if isinstance(parsed.get("error"), dict):
            err = parsed.get("error") or {}
            raise MetaAdsIntegrationError(
                "Meta API returned error payload",
                endpoint=url,
                provider_error_code=sanitize_text(err.get("code"), max_len=80) if err.get("code") is not None else None,
                provider_error_message=sanitize_text(err.get("message"), max_len=300) if err.get("message") is not None else None,
                body_snippet=safe_body_snippet(json.dumps(sanitize_payload(parsed))),
                retryable=False,
            )
        return parsed

    def _get_secret(self, key: str):
        try:
            return integration_secrets_store.get_secret(provider="meta_ads", secret_key=key)
        except Exception:  # noqa: BLE001
            return None

    def _access_token_with_source(self) -> tuple[str, str, str | None]:
        token_secret = self._get_secret("access_token")
        if token_secret is not None and token_secret.value.strip() != "":
            updated_at = token_secret.updated_at.isoformat() if token_secret.updated_at is not None else None
            return token_secret.value.strip(), "database", updated_at

        settings = load_settings()
        env_token = settings.meta_access_token.strip()
        if env_token != "" and not env_token.lower().startswith("your_"):
            return env_token, "env_fallback", None
        return "", "missing", None

    def _resolve_active_access_token_with_source(self) -> tuple[str, str, str | None, str | None]:
        token, source, updated_at = self._access_token_with_source()
        if token == "":
            return "", source, updated_at, "Meta Ads token is missing or placeholder."
        return token, source, updated_at, None

    def graph_api_version(self) -> str:
        settings = load_settings()
        configured = str(settings.meta_api_version or "").strip()
        if configured.lower() == "v20.0" or configured == "":
            return "v24.0"
        return configured

    def _normalize_sync_grain(self, grain: str | None) -> MetaSyncGrain:
        resolved = str(grain or "account_daily").strip().lower()
        if resolved == "":
            resolved = "account_daily"
        if resolved not in _ALLOWED_SYNC_GRAINS:
            raise MetaAdsIntegrationError(f"grain invalid: {resolved}")
        return resolved  # type: ignore[return-value]

    def normalize_meta_account_id(self, raw: str | None) -> str:
        value = str(raw or "").strip()
        if value == "":
            return ""
        lowered = value.lower()
        suffix = value[4:] if lowered.startswith("act_") else value
        suffix = suffix.strip()
        if suffix == "":
            return ""
        if re.fullmatch(r"\d+", suffix):
            return f"act_{suffix}"
        return f"act_{suffix}" if lowered.startswith("act_") else suffix

    def meta_account_numeric_id(self, raw: str | None) -> str:
        normalized = self.normalize_meta_account_id(raw)
        if normalized.startswith("act_"):
            return normalized[4:]
        return normalized

    def meta_graph_account_path(self, raw: str | None) -> str:
        normalized = self.normalize_meta_account_id(raw)
        if normalized == "":
            return ""
        if normalized.startswith("act_"):
            return normalized
        if re.fullmatch(r"\d+", normalized):
            return f"act_{normalized}"
        return normalized

    def _build_graph_account_url(self, *, account_id: str, access_token: str, suffix: str = "") -> str:
        query = parse.urlencode({"access_token": access_token})
        path = self.meta_graph_account_path(account_id)
        normalized_suffix = suffix if suffix.startswith("/") or suffix == "" else f"/{suffix}"
        return f"https://graph.facebook.com/{self.graph_api_version()}/{path}{normalized_suffix}?{query}"

    def meta_account_ids_match(self, left: str | None, right: str | None) -> bool:
        left_numeric = self.meta_account_numeric_id(left)
        right_numeric = self.meta_account_numeric_id(right)
        if re.fullmatch(r"\d+", left_numeric) and re.fullmatch(r"\d+", right_numeric):
            return left_numeric == right_numeric
        return self.normalize_meta_account_id(left).lower() == self.normalize_meta_account_id(right).lower()

    def _resolve_sync_window(self, *, start_date: date | None, end_date: date | None) -> tuple[date, date]:
        if start_date is None and end_date is None:
            utc_today = datetime.now(timezone.utc).date()
            resolved_end = utc_today - timedelta(days=1)
            resolved_start = resolved_end - timedelta(days=6)
            return resolved_start, resolved_end
        if start_date is None or end_date is None:
            raise MetaAdsIntegrationError("start_date and end_date must be provided together")
        if start_date > end_date:
            raise MetaAdsIntegrationError("start_date cannot be after end_date")
        return start_date, end_date

    def _list_client_meta_account_ids(self, *, client_id: int) -> list[str]:
        accounts = client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=int(client_id))
        ids: list[str] = []
        for item in accounts:
            account_id = self.normalize_meta_account_id(str(item.get("id") or item.get("account_id") or ""))
            if account_id == "":
                continue
            if not any(self.meta_account_ids_match(account_id, existing) for existing in ids):
                ids.append(account_id)
        return ids

    def _resolve_target_account_ids(self, *, client_id: int, account_id: str | None = None) -> list[str]:
        account_ids = self._list_client_meta_account_ids(client_id=int(client_id))
        if len(account_ids) <= 0:
            raise MetaAdsIntegrationError("No Meta Ads accounts attached to this client.")
        selected = str(account_id or "").strip()
        if selected == "":
            return account_ids
        matched = [candidate for candidate in account_ids if self.meta_account_ids_match(candidate, selected)]
        if len(matched) <= 0:
            raise MetaAdsIntegrationError("Selected account_id is not attached to this client.")
        return [matched[0]]

    def _resolve_attached_account_currency(self, *, client_id: int, account_id: str) -> str | None:
        accounts = client_registry_service.list_platform_accounts(platform="meta_ads")
        for account in accounts:
            attached_client_id = account.get("attached_client_id")
            if attached_client_id is None or int(attached_client_id) != int(client_id):
                continue
            candidate_id = str(account.get("account_id") or account.get("id") or "").strip()
            if candidate_id == "":
                continue
            if not self.meta_account_ids_match(candidate_id, account_id):
                continue
            currency = str(account.get("currency") or "").strip().upper()
            if len(currency) == 3 and currency.isalpha():
                return currency
        return None

    def _parse_numeric(self, value: object) -> float:
        try:
            return float(value or 0)
        except Exception:  # noqa: BLE001
            return 0.0

    def _parse_int(self, value: object) -> int:
        try:
            return int(float(value or 0))
        except Exception:  # noqa: BLE001
            return 0

    def _derive_lead_conversion_details(self, *, actions: object) -> dict[str, object]:
        if not isinstance(actions, list):
            return {
                "conversions": 0.0,
                "lead_action_types_found": [],
                "lead_action_type_selected": None,
                "lead_action_values_found": {},
            }

        lead_action_values: dict[str, float] = {}
        for item in actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip().lower()
            if action_type not in _META_LEAD_ACTION_TYPES:
                continue
            lead_action_values[action_type] = lead_action_values.get(action_type, 0.0) + self._parse_numeric(item.get("value"))

        selected_action_type: str | None = None
        for candidate in _META_LEAD_ACTION_TYPE_PRIORITY:
            if candidate in lead_action_values:
                selected_action_type = candidate
                break

        return {
            "conversions": float(lead_action_values.get(selected_action_type or "", 0.0)),
            "lead_action_types_found": [action_type for action_type in _META_LEAD_ACTION_TYPE_PRIORITY if action_type in lead_action_values],
            "lead_action_type_selected": selected_action_type,
            "lead_action_values_found": {action_type: round(value, 4) for action_type, value in lead_action_values.items()},
        }

    def _derive_lead_conversions(self, *, actions: object) -> float:
        details = self._derive_lead_conversion_details(actions=actions)
        return float(details.get("conversions") or 0.0)

    def _lead_conversion_observability(self, *, details: dict[str, object]) -> dict[str, object]:
        return {
            "lead_action_types_found": details.get("lead_action_types_found") if isinstance(details.get("lead_action_types_found"), list) else [],
            "lead_action_type_selected": details.get("lead_action_type_selected"),
            "lead_action_values_found": details.get("lead_action_values_found") if isinstance(details.get("lead_action_values_found"), dict) else {},
        }

    def _derive_conversion_value(self, *, action_values: object, selected_action_type: str | None = None) -> float:
        if not isinstance(action_values, list):
            return 0.0
        if selected_action_type:
            selected = str(selected_action_type).strip().lower()
            if selected != "":
                for item in action_values:
                    if not isinstance(item, dict):
                        continue
                    action_type = str(item.get("action_type") or "").strip().lower()
                    if action_type != selected:
                        continue
                    return self._parse_numeric(item.get("value"))
        total = 0.0
        for item in action_values:
            if not isinstance(item, dict):
                continue
            total += self._parse_numeric(item.get("value"))
        return total

    def _entity_row_identity(self, *, row: dict[str, object], grain: str) -> dict[str, object]:
        identity: dict[str, object] = {
            "grain": grain,
            "platform": str(row.get("platform") or ""),
            "account_id": str(row.get("account_id") or ""),
            "report_date": str(row.get("report_date") or ""),
        }
        if grain == "campaign_daily":
            identity["campaign_id"] = str(row.get("campaign_id") or "")
        elif grain == "ad_group_daily":
            identity["campaign_id"] = str(row.get("campaign_id") or "")
            identity["ad_group_id"] = str(row.get("ad_group_id") or "")
        elif grain == "ad_daily":
            identity["campaign_id"] = str(row.get("campaign_id") or "")
            identity["ad_group_id"] = str(row.get("ad_group_id") or "")
            identity["ad_id"] = str(row.get("ad_id") or "")
        return identity

    def _validate_entity_row_numeric_fields(self, *, row: dict[str, object], grain: str) -> tuple[bool, str | None, float | None]:
        for field in ("spend", "conversions", "conversion_value"):
            raw_value = row.get(field)
            value = self._parse_numeric(raw_value)
            if not math.isfinite(value):
                return False, field, value
            if abs(value) >= _ENTITY_NUMERIC_ABS_LIMIT:
                return False, field, value
        return True, None, None

    def _persist_entity_rows_with_row_level_resilience(self, *, grain: str, rows: list[dict[str, object]]) -> dict[str, object]:
        if len(rows) == 0:
            return {"rows_written": 0, "rows_skipped": 0, "skip_reasons": {}, "skipped_rows": []}

        skip_reasons: dict[str, int] = {}
        skipped_rows: list[dict[str, object]] = []
        valid_rows: list[dict[str, object]] = []

        for row in rows:
            is_valid, field, value = self._validate_entity_row_numeric_fields(row=row, grain=grain)
            if is_valid:
                valid_rows.append(row)
                continue
            reason_key = f"numeric_overflow_candidate:{field or 'unknown'}"
            skip_reasons[reason_key] = skip_reasons.get(reason_key, 0) + 1
            detail = {
                **self._entity_row_identity(row=row, grain=grain),
                "reason": reason_key,
                "field": field,
                "value": value,
            }
            skipped_rows.append(detail)
            logger.warning("Meta entity row skipped before upsert due to numeric overflow candidate: %s", sanitize_payload(detail))

        if len(valid_rows) == 0:
            return {
                "rows_written": 0,
                "rows_skipped": len(skipped_rows),
                "skip_reasons": skip_reasons,
                "skipped_rows": skipped_rows,
            }

        write_method = (
            self._write_campaign_daily_rows
            if grain == "campaign_daily"
            else self._write_ad_group_daily_rows
            if grain == "ad_group_daily"
            else self._write_ad_daily_rows
        )
        try:
            written = int(write_method(rows=valid_rows) or 0)
            return {
                "rows_written": written,
                "rows_skipped": len(skipped_rows),
                "skip_reasons": skip_reasons,
                "skipped_rows": skipped_rows,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Meta %s batch upsert failed; retrying row-by-row for isolation. error=%s",
                grain,
                sanitize_text(str(exc), max_len=300),
            )

        written = 0
        for row in valid_rows:
            try:
                written += int(write_method(rows=[row]) or 0)
            except Exception as exc:  # noqa: BLE001
                reason_key = "row_persist_error"
                skip_reasons[reason_key] = skip_reasons.get(reason_key, 0) + 1
                detail = {
                    **self._entity_row_identity(row=row, grain=grain),
                    "reason": reason_key,
                    "error": sanitize_text(str(exc), max_len=300),
                }
                skipped_rows.append(detail)
                logger.warning("Meta entity row skipped after row-level persist error: %s", sanitize_payload(detail))

        return {
            "rows_written": written,
            "rows_skipped": len(skipped_rows),
            "skip_reasons": skip_reasons,
            "skipped_rows": skipped_rows,
        }

    def _base_extra_metrics(self, item: dict[str, object]) -> dict[str, object]:
        return {
            "date_stop": item.get("date_stop"),
            "reach": item.get("reach"),
            "inline_link_clicks": item.get("inline_link_clicks"),
        }

    def _is_retryable_meta_error(self, exc: MetaAdsIntegrationError) -> bool:
        if exc.retryable is True:
            return True
        status = exc.http_status
        return isinstance(status, int) and status >= 500

    def _fetch_insights(
        self,
        *,
        account_id: str,
        start_date: date,
        end_date: date,
        access_token: str,
        level: str,
        fields: list[str],
        time_increment: int | None = None,
    ) -> list[dict[str, object]]:
        params = {
            "level": level,
            "fields": ",".join(fields),
            "time_range": json.dumps({"since": start_date.isoformat(), "until": end_date.isoformat()}),
            "limit": 500,
        }
        if time_increment is not None:
            params["time_increment"] = max(1, int(time_increment))
        query = parse.urlencode(params)
        base_url = self._build_graph_account_url(account_id=account_id, access_token=access_token, suffix="/insights")
        joiner = "&" if "?" in base_url else "?"
        next_url: str | None = f"{base_url}{joiner}{query}"
        items: list[dict[str, object]] = []

        while next_url:
            payload: dict[str, object] | None = None
            for attempt in range(3):
                try:
                    payload = self._http_json(method="GET", url=next_url)
                    break
                except MetaAdsIntegrationError as exc:
                    if attempt >= 2 or not self._is_retryable_meta_error(exc):
                        raise
            if payload is None:
                break

            data = payload.get("data")
            if not isinstance(data, list):
                raise MetaAdsIntegrationError("Meta API returned invalid data container")
            items.extend(item for item in data if isinstance(item, dict))

            paging = payload.get("paging")
            next_value = paging.get("next") if isinstance(paging, dict) else None
            candidate = str(next_value or "").strip()
            next_url = candidate or None

        return items

    def _probe_account_access(self, *, account_id: str, access_token: str, token_source: str) -> dict[str, object]:
        url = self._build_graph_account_url(account_id=account_id, access_token=access_token)
        payload = self._http_json(method="GET", url=url)
        account_id_payload = str(payload.get("account_id") or "").strip()
        id_payload = str(payload.get("id") or "").strip()
        if account_id_payload == "" or id_payload == "" or not id_payload.startswith("act_"):
            raise MetaAdsIntegrationError(
                "Meta account probe returned invalid response shape",
                endpoint=url,
                provider_error_message=sanitize_text({"graph_version": self.graph_api_version(), "account_path": self.meta_graph_account_path(account_id), "token_source": token_source, "payload": payload}, max_len=250),
            )
        if not self.meta_account_ids_match(id_payload, account_id):
            raise MetaAdsIntegrationError(
                "Meta account probe response does not match requested account",
                endpoint=url,
                provider_error_message=f"graph_version={self.graph_api_version()} token_source={token_source} requested={self.meta_graph_account_path(account_id)} response={id_payload}",
            )
        return {
            "account_id": account_id_payload,
            "id": id_payload,
            "account_path": self.meta_graph_account_path(account_id),
            "graph_version": self.graph_api_version(),
            "token_source": token_source,
        }

    def _fetch_account_daily_insights(self, *, account_id: str, start_date: date, end_date: date, access_token: str) -> list[dict[str, object]]:
        return self._fetch_insights(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            access_token=access_token,
            level="account",
            fields=["date_start", "date_stop", "spend", "impressions", "clicks", "actions", "action_values", "reach", "inline_link_clicks"],
            time_increment=1,
        )

    def _build_sync_chunks(self, *, start_date: date, end_date: date, chunk_days: int) -> list[tuple[date, date]]:
        if start_date > end_date:
            return []
        cursor = start_date
        ranges: list[tuple[date, date]] = []
        window = max(1, int(chunk_days))
        while cursor <= end_date:
            chunk_end = min(end_date, cursor + timedelta(days=window - 1))
            ranges.append((cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)
        return ranges

    def _classify_account_daily_coverage_status(self, *, total_chunk_count: int, successful_chunk_count: int, rows_written_count: int) -> str:
        if total_chunk_count <= 0:
            return "empty_success"
        if successful_chunk_count == total_chunk_count:
            return "empty_success" if int(rows_written_count) <= 0 else "full_request_coverage"
        if successful_chunk_count <= 0:
            return "failed_request_coverage"
        return "partial_request_coverage"

    def _fetch_campaign_daily_insights(self, *, account_id: str, start_date: date, end_date: date, access_token: str) -> list[dict[str, object]]:
        return self._fetch_insights(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            access_token=access_token,
            level="campaign",
            fields=["campaign_id", "campaign_name", "date_start", "date_stop", "spend", "impressions", "clicks", "actions", "action_values", "reach", "inline_link_clicks"],
        )

    def _fetch_ad_group_daily_insights(self, *, account_id: str, start_date: date, end_date: date, access_token: str) -> list[dict[str, object]]:
        return self._fetch_insights(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            access_token=access_token,
            level="adset",
            fields=["campaign_id", "campaign_name", "adset_id", "adset_name", "date_start", "date_stop", "spend", "impressions", "clicks", "actions", "action_values", "reach", "inline_link_clicks"],
        )

    def _fetch_ad_daily_insights(self, *, account_id: str, start_date: date, end_date: date, access_token: str) -> list[dict[str, object]]:
        return self._fetch_insights(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            access_token=access_token,
            level="ad",
            fields=["campaign_id", "campaign_name", "adset_id", "adset_name", "ad_id", "ad_name", "date_start", "date_stop", "spend", "impressions", "clicks", "actions", "action_values", "reach", "inline_link_clicks"],
        )

    def _upsert_memory_row(self, target: list[dict[str, object]], key_fields: tuple[str, ...], row: dict[str, object]) -> None:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        for index, existing in enumerate(target):
            existing_key = tuple(str(existing.get(field) or "") for field in key_fields)
            if existing_key == key:
                target[index] = dict(row)
                return
        target.append(dict(row))

    def _write_campaign_daily_rows(self, *, rows: list[dict[str, object]]) -> int:
        if len(rows) == 0:
            return 0
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_campaign_daily_rows, ("platform", "account_id", "campaign_id", "report_date"), row)
            return len(rows)
        with self._connect() as conn:
            written = int(upsert_campaign_performance_reports(conn, rows) or 0)
            conn.commit()
            return written

    def _write_ad_group_daily_rows(self, *, rows: list[dict[str, object]]) -> int:
        if len(rows) == 0:
            return 0
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_ad_group_daily_rows, ("platform", "account_id", "ad_group_id", "report_date"), row)
            return len(rows)
        with self._connect() as conn:
            written = int(upsert_ad_group_performance_reports(conn, rows) or 0)
            conn.commit()
            return written

    def _write_ad_daily_rows(self, *, rows: list[dict[str, object]]) -> int:
        if len(rows) == 0:
            return 0
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_ad_daily_rows, ("platform", "account_id", "ad_id", "report_date"), row)
            return len(rows)
        with self._connect() as conn:
            written = int(upsert_ad_unit_performance_reports(conn, rows) or 0)
            conn.commit()
            return written

    def build_oauth_authorize_url(self) -> dict[str, str]:
        settings = load_settings()
        if not self._oauth_configured():
            raise MetaAdsIntegrationError("Meta OAuth is not configured. Set META_APP_ID, META_APP_SECRET, and META_REDIRECT_URI.")

        state = generate_oauth_state("meta_ads")
        params = {
            "client_id": settings.meta_app_id,
            "redirect_uri": settings.meta_redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": "ads_read,business_management",
        }
        return {
            "authorize_url": f"https://www.facebook.com/{settings.meta_api_version.strip('/')}/dialog/oauth?{parse.urlencode(params)}",
            "state": state,
        }

    def exchange_oauth_code(self, *, code: str, state: str) -> dict[str, object]:
        settings = load_settings()
        if not self._oauth_configured():
            raise MetaAdsIntegrationError("Meta OAuth is not configured. Set META_APP_ID, META_APP_SECRET, and META_REDIRECT_URI.")
        if not verify_oauth_state("meta_ads", state):
            raise MetaAdsIntegrationError("Invalid OAuth state for Meta connect callback")

        query = parse.urlencode(
            {
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            }
        )
        token_payload = self._http_json(
            method="GET",
            url=f"https://graph.facebook.com/{settings.meta_api_version.strip('/')}/oauth/access_token?{query}",
        )
        access_token = str(token_payload.get("access_token") or "").strip()
        if access_token == "":
            raise MetaAdsIntegrationError("Meta OAuth callback did not return an access token")

        integration_secrets_store.upsert_secret(provider="meta_ads", secret_key="access_token", value=access_token)
        _, token_source, token_updated_at = self._access_token_with_source()
        return {
            "status": "connected",
            "provider": "meta_ads",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "has_usable_token": True,
            "message": "Meta OAuth connected. Access token stored securely in application database.",
        }

    def integration_status(self) -> dict[str, object]:
        oauth_configured = self._oauth_configured()
        token, token_source, token_updated_at = self._access_token_with_source()
        has_usable_token = token != ""

        if not oauth_configured:
            return {
                "provider": "meta_ads",
                "status": "pending",
                "message": "Meta OAuth configuration is incomplete. Set app id/secret/redirect URI.",
                "token_source": token_source,
                "token_updated_at": token_updated_at,
                "oauth_configured": False,
                "has_usable_token": has_usable_token,
                "ad_accounts_count": 0,
                "business_count": 0,
            }

        if has_usable_token:
            return {
                "provider": "meta_ads",
                "status": "connected",
                "message": "Meta OAuth token is available.",
                "token_source": token_source,
                "token_updated_at": token_updated_at,
                "oauth_configured": True,
                "has_usable_token": True,
                "ad_accounts_count": 0,
                "business_count": 0,
            }

        return {
            "provider": "meta_ads",
            "status": "pending",
            "message": "Meta OAuth is configured but no usable token is stored yet.",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "oauth_configured": True,
            "has_usable_token": False,
            "ad_accounts_count": 0,
            "business_count": 0,
        }

    def run_diagnostics(self) -> dict[str, object]:
        settings = load_settings()
        oauth_configured = self._oauth_configured()
        token, token_source, token_updated_at = self._access_token_with_source()
        has_usable_token = token != ""
        api_version = self.graph_api_version()

        oauth_ok = False
        ad_accounts_count = 0
        accessible_ad_accounts: list[dict[str, object]] = []
        last_error: str | None = None
        warnings: list[str] = []

        if not oauth_configured:
            warnings.append("Meta OAuth is not configured. Set META_APP_ID, META_APP_SECRET, and META_REDIRECT_URI.")

        if has_usable_token:
            try:
                accessible_ad_accounts = self.list_accessible_ad_accounts()
                ad_accounts_count = len(accessible_ad_accounts)
                oauth_ok = True
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                warnings.append(f"Failed to list ad accounts: {str(exc)[:200]}")
        else:
            warnings.append("No usable access token available.")

        db_diag = self._db_diagnostics_last_30_days()

        return {
            "oauth_ok": oauth_ok,
            "oauth_configured": oauth_configured,
            "api_version": api_version,
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "has_usable_token": has_usable_token,
            "ad_accounts_count": ad_accounts_count,
            "sample_ad_accounts": [
                {"id": str(a.get("id", "")), "name": str(a.get("name", "")), "status": a.get("account_status")}
                for a in accessible_ad_accounts[:10]
            ],
            "db_rows_last_30_days": db_diag.get("db_rows_last_30_days", 0),
            "last_sync_at": db_diag.get("last_sync_at"),
            "warnings": warnings,
            "last_error": last_error or db_diag.get("db_error"),
        }

    def _db_diagnostics_last_30_days(self) -> dict[str, object]:
        try:
            import psycopg as _psycopg  # noqa: F811
        except Exception:  # noqa: BLE001
            return {"db_rows_last_30_days": 0, "last_sync_at": None, "db_error": "psycopg not available"}
        try:
            from app.db.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.ad_performance_reports')")
                    table_exists = (cur.fetchone() or [None])[0] is not None
                    if not table_exists:
                        return {"db_rows_last_30_days": 0, "last_sync_at": None, "db_error": "Table ad_performance_reports missing"}
                    cur.execute(
                        """
                        SELECT COALESCE(COUNT(*), 0), MAX(synced_at)
                        FROM ad_performance_reports
                        WHERE platform = %s
                          AND synced_at >= NOW() - INTERVAL '30 days'
                        """,
                        ("meta_ads",),
                    )
                    row = cur.fetchone() or (0, None)
                    return {
                        "db_rows_last_30_days": int(row[0] or 0),
                        "last_sync_at": row[1].isoformat() if row[1] is not None else None,
                    }
        except Exception as exc:  # noqa: BLE001
            return {"db_rows_last_30_days": 0, "last_sync_at": None, "db_error": str(exc)[:200]}

    def _active_access_token(self) -> str:
        token, _, _ = self._access_token_with_source()
        return token

    def list_accessible_ad_accounts(self) -> list[dict[str, object]]:
        resolved_token = self._active_access_token()
        if resolved_token == "":
            raise MetaAdsIntegrationError("Meta account discovery requires a usable OAuth token.")

        api_version = self.graph_api_version()
        accounts: list[dict[str, object]] = []
        fields = "id,account_id,name,account_status,currency,timezone_name"
        url: str | None = f"https://graph.facebook.com/{api_version}/me/adaccounts?fields={parse.quote(fields)}&limit=200"

        max_pages = 50
        page = 0
        while url and page < max_pages:
            page += 1
            raw = self._http_json(
                method="GET",
                url=url,
                headers={"Authorization": f"Bearer {resolved_token}"},
            )
            data_list = raw.get("data")
            if isinstance(data_list, list):
                for item in data_list:
                    if not isinstance(item, dict):
                        continue
                    raw_id = str(item.get("id") or "").strip()
                    numeric_id = str(item.get("account_id") or "").strip()
                    if not raw_id and not numeric_id:
                        continue
                    if raw_id.startswith("act_"):
                        account_id = raw_id
                    elif numeric_id:
                        account_id = f"act_{numeric_id}"
                    else:
                        account_id = f"act_{raw_id}"
                    accounts.append({
                        "id": account_id,
                        "name": str(item.get("name") or account_id),
                        "account_status": item.get("account_status"),
                        "currency_code": str(item.get("currency") or "").strip().upper() or None,
                        "account_timezone": str(item.get("timezone_name") or "").strip() or None,
                    })

            paging = raw.get("paging")
            if isinstance(paging, dict):
                next_url = str(paging.get("next") or "").strip()
                if next_url:
                    url = next_url
                else:
                    cursors = paging.get("cursors")
                    if isinstance(cursors, dict):
                        after = str(cursors.get("after") or "").strip()
                        if after:
                            url = f"https://graph.facebook.com/{api_version}/me/adaccounts?fields={parse.quote(fields)}&limit=200&after={parse.quote(after)}"
                        else:
                            url = None
                    else:
                        url = None
            else:
                url = None

        return accounts

    def import_accounts(self) -> dict[str, object]:
        _, token_source, _ = self._access_token_with_source()

        discovered_accounts = self.list_accessible_ad_accounts()
        existing_accounts = client_registry_service.list_platform_accounts(platform="meta_ads")
        existing_by_id: dict[str, dict[str, object]] = {
            str(item.get("account_id") or item.get("id") or "").strip(): item
            for item in existing_accounts if isinstance(item, dict)
        }

        if len(discovered_accounts) > 0:
            client_registry_service.upsert_platform_accounts(
                platform="meta_ads",
                accounts=[{"id": str(item["id"]), "name": str(item["name"])} for item in discovered_accounts],
            )

        imported = 0
        updated = 0
        unchanged = 0
        for account in discovered_accounts:
            account_id = str(account["id"])
            account_name = str(account["name"])
            status_raw = account.get("account_status")
            status = str(status_raw) if status_raw is not None else None
            currency_code = account.get("currency_code")
            account_timezone = account.get("account_timezone")

            existing = existing_by_id.get(account_id)
            if existing is None:
                imported += 1
                client_registry_service.update_platform_account_operational_metadata(
                    platform="meta_ads",
                    account_id=account_id,
                    status=status,
                    currency_code=str(currency_code) if currency_code else None,
                    account_timezone=str(account_timezone) if account_timezone else None,
                )
                continue

            existing_name = str(existing.get("name") or "").strip()
            existing_status = str(existing.get("status") or "").strip() or None
            existing_currency = str(existing.get("currency") or "").strip().upper() or None
            existing_timezone = str(existing.get("timezone") or "").strip() or None

            changed = (
                existing_name != account_name
                or existing_status != status
                or existing_currency != (str(currency_code) if currency_code else None)
                or existing_timezone != (str(account_timezone) if account_timezone else None)
            )
            if changed:
                updated += 1
                client_registry_service.update_platform_account_operational_metadata(
                    platform="meta_ads",
                    account_id=account_id,
                    status=status,
                    currency_code=str(currency_code) if currency_code else None,
                    account_timezone=str(account_timezone) if account_timezone else None,
                )
            else:
                unchanged += 1

        return {
            "status": "ok",
            "provider": "meta_ads",
            "platform": "meta_ads",
            "token_source": token_source,
            "accounts_discovered": len(discovered_accounts),
            "imported": imported,
            "updated": updated,
            "unchanged": unchanged,
            "message": f"Meta account import completed: discovered={len(discovered_accounts)}, imported={imported}, updated={updated}, unchanged={unchanged}.",
        }

    def sync_client(
        self,
        *,
        client_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        grain: MetaSyncGrain | str | None = None,
        account_id: str | None = None,
        update_snapshot: bool = True,
    ) -> dict[str, float | int | str]:
        if int(client_id) <= 0:
            raise MetaAdsIntegrationError("Client id must be a positive integer.")

        resolved_grain = self._normalize_sync_grain(grain)
        resolved_start, resolved_end = self._resolve_sync_window(start_date=start_date, end_date=end_date)

        access_token, token_source, _, token_error = self._resolve_active_access_token_with_source()
        if token_error:
            raise MetaAdsIntegrationError(token_error)

        account_ids = self._resolve_target_account_ids(client_id=int(client_id), account_id=account_id)

        rows_written = 0
        rows_skipped = 0
        aggregate_skip_reasons: dict[str, int] = {}
        aggregate_skipped_rows: list[dict[str, object]] = []
        totals = {
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0.0,
            "revenue": 0.0,
        }
        account_summaries: list[dict[str, object]] = []

        for account_id in account_ids:
            probe = {"account_path": self.meta_graph_account_path(account_id), "graph_version": self.graph_api_version(), "token_source": token_source}
            if not self._is_test_mode():
                probe = self._probe_account_access(account_id=account_id, access_token=access_token, token_source=token_source)
            account_rows_written = 0
            account_totals = {
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0.0,
                "conversion_value": 0.0,
            }
            resolved_account_currency = self._resolve_attached_account_currency(client_id=int(client_id), account_id=account_id)

            if resolved_grain == "account_daily":
                chunk_windows = self._build_sync_chunks(start_date=resolved_start, end_date=resolved_end, chunk_days=_META_ACCOUNT_DAILY_CHUNK_DAYS)
                total_chunk_count = len(chunk_windows)
                successful_chunk_count = 0
                retry_attempted = False
                retry_recovered_chunk_count = 0
                failed_chunk_windows: list[tuple[date, date]] = []
                last_error_summary: str | None = None
                last_error_details: dict[str, object] | None = None
                first_persisted_date: str | None = None
                last_persisted_date: str | None = None

                def _persist_insights_rows(insights_rows: list[dict[str, object]]) -> int:
                    nonlocal rows_written, account_rows_written, first_persisted_date, last_persisted_date
                    batch_payloads: list[dict] = []
                    for item in insights_rows:
                        report_date_raw = str(item.get("date_start") or "").strip()
                        if report_date_raw == "":
                            continue
                        try:
                            report_date_value = date.fromisoformat(report_date_raw)
                        except ValueError:
                            continue

                        spend = self._parse_numeric(item.get("spend"))
                        impressions = self._parse_int(item.get("impressions"))
                        clicks = self._parse_int(item.get("clicks"))
                        lead_conversion_details = self._derive_lead_conversion_details(actions=item.get("actions"))
                        conversions = float(lead_conversion_details.get("conversions") or 0.0)
                        conversion_value = self._derive_conversion_value(
                            action_values=item.get("action_values"),
                            selected_action_type=str(lead_conversion_details.get("lead_action_type_selected") or ""),
                        )

                        batch_payloads.append({
                            "report_date": report_date_value,
                            "platform": "meta_ads",
                            "customer_id": account_id,
                            "client_id": int(client_id),
                            "spend": spend,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "conversion_value": conversion_value,
                            "extra_metrics": {"meta_ads": {**self._base_extra_metrics(item), "account_currency": resolved_account_currency, **self._lead_conversion_observability(details=lead_conversion_details), "grain": "account_daily"}},
                        })
                        iso_day = report_date_value.isoformat()
                        first_persisted_date = iso_day if first_persisted_date is None or iso_day < first_persisted_date else first_persisted_date
                        last_persisted_date = iso_day if last_persisted_date is None or iso_day > last_persisted_date else last_persisted_date
                        account_totals["spend"] += spend
                        account_totals["impressions"] += impressions
                        account_totals["clicks"] += clicks
                        account_totals["conversions"] += conversions
                        account_totals["conversion_value"] += conversion_value

                    if batch_payloads:
                        performance_reports_store.write_daily_reports_batch(batch_payloads)
                    persisted = len(batch_payloads)
                    rows_written += persisted
                    account_rows_written += persisted
                    return persisted

                for chunk_start, chunk_end in chunk_windows:
                    try:
                        insights_rows = self._fetch_account_daily_insights(
                            account_id=account_id,
                            start_date=chunk_start,
                            end_date=chunk_end,
                            access_token=access_token,
                        )
                        _persist_insights_rows(insights_rows)
                        successful_chunk_count += 1
                    except MetaAdsIntegrationError as exc:
                        failed_chunk_windows.append((chunk_start, chunk_end))
                        last_error_summary = str(exc)
                        last_error_details = sanitize_payload(exc.to_details()) if hasattr(exc, "to_details") else {"error_summary": str(exc)}
                    except Exception as exc:  # noqa: BLE001
                        failed_chunk_windows.append((chunk_start, chunk_end))
                        last_error_summary = sanitize_text(str(exc), max_len=300)
                        last_error_details = {"error_summary": sanitize_text(str(exc), max_len=300)}

                if len(failed_chunk_windows) > 0:
                    retry_attempted = True
                    initial_failed = list(failed_chunk_windows)
                    failed_chunk_windows = []
                    for chunk_start, chunk_end in initial_failed:
                        try:
                            insights_rows = self._fetch_account_daily_insights(
                                account_id=account_id,
                                start_date=chunk_start,
                                end_date=chunk_end,
                                access_token=access_token,
                            )
                            _persist_insights_rows(insights_rows)
                            successful_chunk_count += 1
                            retry_recovered_chunk_count += 1
                        except MetaAdsIntegrationError as exc:
                            failed_chunk_windows.append((chunk_start, chunk_end))
                            last_error_summary = str(exc)
                            last_error_details = sanitize_payload(exc.to_details()) if hasattr(exc, "to_details") else {"error_summary": str(exc)}
                        except Exception as exc:  # noqa: BLE001
                            failed_chunk_windows.append((chunk_start, chunk_end))
                            last_error_summary = sanitize_text(str(exc), max_len=300)
                            last_error_details = {"error_summary": sanitize_text(str(exc), max_len=300)}

                coverage_status = self._classify_account_daily_coverage_status(
                    total_chunk_count=total_chunk_count,
                    successful_chunk_count=successful_chunk_count,
                    rows_written_count=account_rows_written,
                )
                account_summaries.append(
                    {
                        "account_id": account_id,
                        "account_path": probe.get("account_path"),
                        "rows_written": account_rows_written,
                        "rows_written_count": account_rows_written,
                        "spend": round(account_totals["spend"], 2),
                        "impressions": account_totals["impressions"],
                        "clicks": account_totals["clicks"],
                        "conversions": round(account_totals["conversions"], 4),
                        "conversion_value": round(account_totals["conversion_value"], 2),
                        "sync_health_status": coverage_status,
                        "coverage_status": coverage_status,
                        "requested_start_date": resolved_start.isoformat(),
                        "requested_end_date": resolved_end.isoformat(),
                        "total_chunk_count": total_chunk_count,
                        "successful_chunk_count": successful_chunk_count,
                        "failed_chunk_count": max(0, total_chunk_count - successful_chunk_count),
                        "retry_attempted": retry_attempted,
                        "retry_recovered_chunk_count": retry_recovered_chunk_count,
                        "first_persisted_date": first_persisted_date,
                        "last_persisted_date": last_persisted_date,
                        "last_error": last_error_summary if coverage_status in {"partial_request_coverage", "failed_request_coverage"} else None,
                        "last_error_summary": last_error_summary if coverage_status in {"partial_request_coverage", "failed_request_coverage"} else None,
                        "last_error_details": last_error_details if coverage_status in {"partial_request_coverage", "failed_request_coverage"} else None,
                    }
                )
            elif resolved_grain == "campaign_daily":
                insights_rows = self._fetch_campaign_daily_insights(
                    account_id=account_id,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    access_token=access_token,
                )
                campaign_rows: list[dict[str, object]] = []
                for item in insights_rows:
                    report_date_raw = str(item.get("date_start") or "").strip()
                    campaign_id = str(item.get("campaign_id") or "").strip()
                    if report_date_raw == "" or campaign_id == "":
                        continue
                    try:
                        report_date_value = date.fromisoformat(report_date_raw)
                    except ValueError:
                        continue

                    spend = self._parse_numeric(item.get("spend"))
                    impressions = self._parse_int(item.get("impressions"))
                    clicks = self._parse_int(item.get("clicks"))
                    lead_conversion_details = self._derive_lead_conversion_details(actions=item.get("actions"))
                    conversions = float(lead_conversion_details.get("conversions") or 0.0)
                    conversion_value = self._derive_conversion_value(
                        action_values=item.get("action_values"),
                        selected_action_type=str(lead_conversion_details.get("lead_action_type_selected") or ""),
                    )

                    campaign_rows.append(
                        {
                            "platform": "meta_ads",
                            "account_id": account_id,
                            "campaign_id": campaign_id,
                            "report_date": report_date_value,
                            "spend": spend,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "conversion_value": conversion_value,
                            "extra_metrics": {
                                "meta_ads": {
                                    **self._base_extra_metrics(item),
                                    "campaign_name": str(item.get("campaign_name") or "").strip() or None,
                                    "campaign_id": campaign_id,
                                    "campaign_status": str(item.get("campaign_status") or item.get("effective_status") or item.get("status") or "").strip() or None,
                                    "account_currency": resolved_account_currency,
                                    "grain": "campaign_daily",
                                    **self._lead_conversion_observability(details=lead_conversion_details),
                                }
                            },
                            "source_window_start": resolved_start,
                            "source_window_end": resolved_end,
                            "source_job_id": None,
                        }
                    )
                    account_totals["spend"] += spend
                    account_totals["impressions"] += impressions
                    account_totals["clicks"] += clicks
                    account_totals["conversions"] += conversions
                    account_totals["conversion_value"] += conversion_value

                persist_result = self._persist_entity_rows_with_row_level_resilience(grain="campaign_daily", rows=campaign_rows)
                account_rows_written = int(persist_result.get("rows_written") or 0)
                account_rows_skipped = int(persist_result.get("rows_skipped") or 0)
                account_skip_reasons = persist_result.get("skip_reasons") if isinstance(persist_result.get("skip_reasons"), dict) else {}
                account_skipped_rows = persist_result.get("skipped_rows") if isinstance(persist_result.get("skipped_rows"), list) else []
                rows_written += account_rows_written
                rows_skipped += account_rows_skipped
                for key, count in account_skip_reasons.items():
                    reason = str(key or "").strip()
                    if reason == "":
                        continue
                    aggregate_skip_reasons[reason] = aggregate_skip_reasons.get(reason, 0) + int(count or 0)
                aggregate_skipped_rows.extend([item for item in account_skipped_rows if isinstance(item, dict)])
            elif resolved_grain == "ad_group_daily":
                insights_rows = self._fetch_ad_group_daily_insights(
                    account_id=account_id,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    access_token=access_token,
                )
                ad_group_rows: list[dict[str, object]] = []
                for item in insights_rows:
                    report_date_raw = str(item.get("date_start") or "").strip()
                    ad_group_id = str(item.get("adset_id") or "").strip()
                    if report_date_raw == "" or ad_group_id == "":
                        continue
                    try:
                        report_date_value = date.fromisoformat(report_date_raw)
                    except ValueError:
                        continue

                    spend = self._parse_numeric(item.get("spend"))
                    impressions = self._parse_int(item.get("impressions"))
                    clicks = self._parse_int(item.get("clicks"))
                    lead_conversion_details = self._derive_lead_conversion_details(actions=item.get("actions"))
                    conversions = float(lead_conversion_details.get("conversions") or 0.0)
                    conversion_value = self._derive_conversion_value(
                        action_values=item.get("action_values"),
                        selected_action_type=str(lead_conversion_details.get("lead_action_type_selected") or ""),
                    )
                    campaign_id = str(item.get("campaign_id") or "").strip() or None

                    ad_group_rows.append(
                        {
                            "platform": "meta_ads",
                            "account_id": account_id,
                            "ad_group_id": ad_group_id,
                            "campaign_id": campaign_id,
                            "report_date": report_date_value,
                            "spend": spend,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "conversion_value": conversion_value,
                            "extra_metrics": {
                                "meta_ads": {
                                    **self._base_extra_metrics(item),
                                    "adset_id": ad_group_id,
                                    "adset_name": str(item.get("adset_name") or "").strip() or None,
                                    "adset_status": str(item.get("adset_status") or item.get("effective_status") or item.get("status") or "").strip() or None,
                                    "campaign_id": campaign_id,
                                    "campaign_name": str(item.get("campaign_name") or "").strip() or None,
                                    "campaign_status": str(item.get("campaign_status") or "").strip() or None,
                                    "account_currency": resolved_account_currency,
                                    "grain": "ad_group_daily",
                                    **self._lead_conversion_observability(details=lead_conversion_details),
                                }
                            },
                            "source_window_start": resolved_start,
                            "source_window_end": resolved_end,
                            "source_job_id": None,
                        }
                    )
                    account_totals["spend"] += spend
                    account_totals["impressions"] += impressions
                    account_totals["clicks"] += clicks
                    account_totals["conversions"] += conversions
                    account_totals["conversion_value"] += conversion_value

                persist_result = self._persist_entity_rows_with_row_level_resilience(grain="ad_group_daily", rows=ad_group_rows)
                account_rows_written = int(persist_result.get("rows_written") or 0)
                account_rows_skipped = int(persist_result.get("rows_skipped") or 0)
                account_skip_reasons = persist_result.get("skip_reasons") if isinstance(persist_result.get("skip_reasons"), dict) else {}
                account_skipped_rows = persist_result.get("skipped_rows") if isinstance(persist_result.get("skipped_rows"), list) else []
                rows_written += account_rows_written
                rows_skipped += account_rows_skipped
                for key, count in account_skip_reasons.items():
                    reason = str(key or "").strip()
                    if reason == "":
                        continue
                    aggregate_skip_reasons[reason] = aggregate_skip_reasons.get(reason, 0) + int(count or 0)
                aggregate_skipped_rows.extend([item for item in account_skipped_rows if isinstance(item, dict)])
            else:
                insights_rows = self._fetch_ad_daily_insights(
                    account_id=account_id,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    access_token=access_token,
                )
                ad_rows: list[dict[str, object]] = []
                for item in insights_rows:
                    report_date_raw = str(item.get("date_start") or "").strip()
                    ad_id = str(item.get("ad_id") or "").strip()
                    if report_date_raw == "" or ad_id == "":
                        continue
                    try:
                        report_date_value = date.fromisoformat(report_date_raw)
                    except ValueError:
                        continue

                    spend = self._parse_numeric(item.get("spend"))
                    impressions = self._parse_int(item.get("impressions"))
                    clicks = self._parse_int(item.get("clicks"))
                    lead_conversion_details = self._derive_lead_conversion_details(actions=item.get("actions"))
                    conversions = float(lead_conversion_details.get("conversions") or 0.0)
                    conversion_value = self._derive_conversion_value(
                        action_values=item.get("action_values"),
                        selected_action_type=str(lead_conversion_details.get("lead_action_type_selected") or ""),
                    )
                    campaign_id = str(item.get("campaign_id") or "").strip() or None
                    ad_group_id = str(item.get("adset_id") or "").strip() or None

                    ad_rows.append(
                        {
                            "platform": "meta_ads",
                            "account_id": account_id,
                            "ad_id": ad_id,
                            "campaign_id": campaign_id,
                            "ad_group_id": ad_group_id,
                            "report_date": report_date_value,
                            "spend": spend,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "conversion_value": conversion_value,
                            "extra_metrics": {
                                "meta_ads": {
                                    **self._base_extra_metrics(item),
                                    "ad_id": ad_id,
                                    "ad_name": str(item.get("ad_name") or "").strip() or None,
                                    "ad_status": str(item.get("ad_status") or item.get("effective_status") or item.get("status") or "").strip() or None,
                                    "adset_id": ad_group_id,
                                    "adset_name": str(item.get("adset_name") or "").strip() or None,
                                    "adset_status": str(item.get("adset_status") or "").strip() or None,
                                    "campaign_id": campaign_id,
                                    "campaign_name": str(item.get("campaign_name") or "").strip() or None,
                                    "campaign_status": str(item.get("campaign_status") or "").strip() or None,
                                    "account_currency": resolved_account_currency,
                                    "grain": "ad_daily",
                                    **self._lead_conversion_observability(details=lead_conversion_details),
                                }
                            },
                            "source_window_start": resolved_start,
                            "source_window_end": resolved_end,
                            "source_job_id": None,
                        }
                    )
                    account_totals["spend"] += spend
                    account_totals["impressions"] += impressions
                    account_totals["clicks"] += clicks
                    account_totals["conversions"] += conversions
                    account_totals["conversion_value"] += conversion_value

                persist_result = self._persist_entity_rows_with_row_level_resilience(grain="ad_daily", rows=ad_rows)
                account_rows_written = int(persist_result.get("rows_written") or 0)
                account_rows_skipped = int(persist_result.get("rows_skipped") or 0)
                account_skip_reasons = persist_result.get("skip_reasons") if isinstance(persist_result.get("skip_reasons"), dict) else {}
                account_skipped_rows = persist_result.get("skipped_rows") if isinstance(persist_result.get("skipped_rows"), list) else []
                rows_written += account_rows_written
                rows_skipped += account_rows_skipped
                for key, count in account_skip_reasons.items():
                    reason = str(key or "").strip()
                    if reason == "":
                        continue
                    aggregate_skip_reasons[reason] = aggregate_skip_reasons.get(reason, 0) + int(count or 0)
                aggregate_skipped_rows.extend([item for item in account_skipped_rows if isinstance(item, dict)])

            totals["spend"] += account_totals["spend"]
            totals["impressions"] += account_totals["impressions"]
            totals["clicks"] += account_totals["clicks"]
            totals["conversions"] += account_totals["conversions"]
            totals["revenue"] += account_totals["conversion_value"]

            if resolved_grain != "account_daily":
                account_summaries.append(
                    {
                        "account_id": account_id,
                        "account_path": probe.get("account_path"),
                        "rows_written": account_rows_written,
                        "rows_skipped": account_rows_skipped,
                        "skip_reasons": account_skip_reasons,
                        "spend": round(account_totals["spend"], 2),
                        "impressions": account_totals["impressions"],
                        "clicks": account_totals["clicks"],
                        "conversions": round(account_totals["conversions"], 4),
                        "conversion_value": round(account_totals["conversion_value"], 2),
                    }
                )

        account_daily_coverages = [str(item.get("coverage_status") or "") for item in account_summaries if isinstance(item, dict) and str(item.get("coverage_status") or "") != ""]
        if len(account_daily_coverages) > 0:
            if any(value == "failed_request_coverage" for value in account_daily_coverages):
                sync_health_status = "failed_request_coverage"
            elif any(value == "partial_request_coverage" for value in account_daily_coverages):
                sync_health_status = "partial_request_coverage"
            elif all(value == "empty_success" for value in account_daily_coverages):
                sync_health_status = "empty_success"
            else:
                sync_health_status = "full_request_coverage"
        else:
            sync_health_status = "full_request_coverage"
        if rows_skipped > 0 and sync_health_status == "full_request_coverage":
            sync_health_status = "partial_request_coverage"

        snapshot = {
            "status": "error" if sync_health_status in {"partial_request_coverage", "failed_request_coverage"} else "ok",
            "message": f"Meta Ads {resolved_grain} sync completed.",
            "platform": "meta_ads",
            "grain": resolved_grain,
            "graph_version": self.graph_api_version(),
            "client_id": int(client_id),
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "accounts_processed": len(account_ids),
            "rows_written": rows_written,
            "rows_skipped": rows_skipped,
            "skip_reasons": aggregate_skip_reasons,
            "skipped_rows_sample": aggregate_skipped_rows[:20],
            "token_source": token_source,
            "spend": round(totals["spend"], 2),
            "impressions": int(totals["impressions"]),
            "clicks": int(totals["clicks"]),
            "conversions": round(totals["conversions"], 4),
            "revenue": round(totals["revenue"], 2),
            "accounts": account_summaries,
            "sync_health_status": sync_health_status,
            "coverage_status": sync_health_status,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        if resolved_grain == "account_daily":
            failing_accounts = [item for item in account_summaries if str(item.get("coverage_status") or "") in {"partial_request_coverage", "failed_request_coverage"}]
            if len(failing_accounts) > 0:
                first = failing_accounts[0]
                snapshot["last_error"] = first.get("last_error")
                snapshot["last_error_summary"] = first.get("last_error_summary")
                snapshot["last_error_details"] = first.get("last_error_details")

        if resolved_grain == "account_daily" and bool(update_snapshot):
            meta_snapshot_store.upsert_snapshot(
                payload={
                    "client_id": int(client_id),
                    "spend": float(snapshot["spend"]),
                    "impressions": int(snapshot["impressions"]),
                    "clicks": int(snapshot["clicks"]),
                    "conversions": int(round(float(snapshot["conversions"]))),
                    "revenue": float(snapshot["revenue"]),
                    "synced_at": str(snapshot["synced_at"]),
                }
            )
        return snapshot

    def rebuild_snapshot_from_account_daily(
        self,
        *,
        client_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        account_id: str | None = None,
    ) -> dict[str, float | int | str]:
        if int(client_id) <= 0:
            raise MetaAdsIntegrationError("Client id must be a positive integer.")

        account_filter = str(account_id or "").strip()
        resolved_start = start_date
        resolved_end = end_date

        spend = 0.0
        impressions = 0
        clicks = 0
        conversions = 0.0
        revenue = 0.0

        if self._is_test_mode():
            for row in performance_reports_store._memory_rows:
                if str(row.get("platform") or "") != "meta_ads":
                    continue
                if int(row.get("client_id") or 0) != int(client_id):
                    continue
                report_date_raw = str(row.get("report_date") or "").strip()
                if report_date_raw == "":
                    continue
                try:
                    report_date_value = date.fromisoformat(report_date_raw)
                except ValueError:
                    continue
                if resolved_start is not None and report_date_value < resolved_start:
                    continue
                if resolved_end is not None and report_date_value > resolved_end:
                    continue
                customer = str(row.get("customer_id") or "").strip()
                if account_filter != "" and not self.meta_account_ids_match(customer, account_filter):
                    continue

                spend += self._parse_numeric(row.get("spend"))
                impressions += self._parse_int(row.get("impressions"))
                clicks += self._parse_int(row.get("clicks"))
                conversions += self._parse_numeric(row.get("conversions"))
                revenue += self._parse_numeric(row.get("conversion_value"))
        else:
            performance_reports_store.initialize_schema()
            where_parts = ["platform = %s", "client_id = %s"]
            params: list[object] = ["meta_ads", int(client_id)]
            if resolved_start is not None:
                where_parts.append("report_date >= %s")
                params.append(resolved_start)
            if resolved_end is not None:
                where_parts.append("report_date <= %s")
                params.append(resolved_end)
            if account_filter != "":
                where_parts.append("(customer_id = %s OR regexp_replace(customer_id, '[^0-9]', '', 'g') = regexp_replace(%s, '[^0-9]', '', 'g'))")
                params.extend([account_filter, account_filter])

            with performance_reports_store._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT
                            COALESCE(SUM(spend), 0),
                            COALESCE(SUM(impressions), 0),
                            COALESCE(SUM(clicks), 0),
                            COALESCE(SUM(conversions), 0),
                            COALESCE(SUM(conversion_value), 0)
                        FROM ad_performance_reports
                        WHERE {' AND '.join(where_parts)}
                        """,
                        tuple(params),
                    )
                    row = cur.fetchone() or (0, 0, 0, 0, 0)
            spend = self._parse_numeric(row[0])
            impressions = self._parse_int(row[1])
            clicks = self._parse_int(row[2])
            conversions = self._parse_numeric(row[3])
            revenue = self._parse_numeric(row[4])

        snapshot = {
            "client_id": int(client_id),
            "spend": round(spend, 2),
            "impressions": int(impressions),
            "clicks": int(clicks),
            "conversions": int(round(conversions)),
            "revenue": round(revenue, 2),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return meta_snapshot_store.get_snapshot(client_id=client_id)


meta_ads_service = MetaAdsService()
