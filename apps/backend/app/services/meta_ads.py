from __future__ import annotations

import base64
import json
import secrets
from datetime import date, datetime, timedelta, timezone
import re
from typing import Literal
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.error_observability import safe_body_snippet, sanitize_payload, sanitize_text
from app.services.integration_secrets_store import integration_secrets_store
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

MetaSyncGrain = Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]
_ALLOWED_SYNC_GRAINS: tuple[str, ...] = ("account_daily", "campaign_daily", "ad_group_daily", "ad_daily")
_META_LEAD_ACTION_TYPES: set[str] = {
    "lead",
    "onsite_conversion.lead",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.lead",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.fb_pixel_custom_lead",
    "offsite_conversion.meta_lead",
    "offsite_conversion.meta_pixel_lead",
}


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
    _oauth_state_cache: set[str]

    def __init__(self) -> None:
        self._oauth_state_cache = set()
        self._memory_campaign_daily_rows: list[dict[str, object]] = []
        self._memory_ad_group_daily_rows: list[dict[str, object]] = []
        self._memory_ad_daily_rows: list[dict[str, object]] = []

    def _is_test_mode(self) -> bool:
        settings = load_settings()
        return settings.app_env == "test"

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

    def _http_json(self, *, method: str, url: str) -> dict[str, object]:
        req = request.Request(url=url, method=method.upper())
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

    def _derive_lead_conversions(self, *, actions: object) -> float:
        if not isinstance(actions, list):
            return 0.0
        total = 0.0
        for item in actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip().lower()
            if action_type not in _META_LEAD_ACTION_TYPES:
                continue
            total += self._parse_numeric(item.get("value"))
        return total

    def _derive_conversion_value(self, *, action_values: object) -> float:
        if not isinstance(action_values, list):
            return 0.0
        total = 0.0
        for item in action_values:
            if not isinstance(item, dict):
                continue
            total += self._parse_numeric(item.get("value"))
        return total

    def _base_extra_metrics(self, item: dict[str, object]) -> dict[str, object]:
        return {
            "date_stop": item.get("date_stop"),
            "reach": item.get("reach"),
            "inline_link_clicks": item.get("inline_link_clicks"),
        }

    def _fetch_insights(
        self,
        *,
        account_id: str,
        start_date: date,
        end_date: date,
        access_token: str,
        level: str,
        fields: list[str],
    ) -> list[dict[str, object]]:
        params = {
            "level": level,
            "fields": ",".join(fields),
            "time_range": json.dumps({"since": start_date.isoformat(), "until": end_date.isoformat()}),
            "limit": 500,
        }
        query = parse.urlencode(params)
        base_url = self._build_graph_account_url(account_id=account_id, access_token=access_token, suffix="/insights")
        joiner = "&" if "?" in base_url else "?"
        payload = self._http_json(
            method="GET",
            url=f"{base_url}{joiner}{query}",
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise MetaAdsIntegrationError("Meta API returned invalid data container")
        return [item for item in data if isinstance(item, dict)]

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
        )

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
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_campaign_daily_rows, ("platform", "account_id", "campaign_id", "report_date"), row)
            return len(rows)
        return 0

    def _write_ad_group_daily_rows(self, *, rows: list[dict[str, object]]) -> int:
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_ad_group_daily_rows, ("platform", "account_id", "ad_group_id", "report_date"), row)
            return len(rows)
        return 0

    def _write_ad_daily_rows(self, *, rows: list[dict[str, object]]) -> int:
        if self._is_test_mode():
            for row in rows:
                self._upsert_memory_row(self._memory_ad_daily_rows, ("platform", "account_id", "ad_id", "report_date"), row)
            return len(rows)
        return 0

    def build_oauth_authorize_url(self) -> dict[str, str]:
        settings = load_settings()
        if not self._oauth_configured():
            raise MetaAdsIntegrationError("Meta OAuth is not configured. Set META_APP_ID, META_APP_SECRET, and META_REDIRECT_URI.")

        state = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8").rstrip("=")
        self._oauth_state_cache.add(state)
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
        if state not in self._oauth_state_cache:
            raise MetaAdsIntegrationError("Invalid OAuth state for Meta connect callback")
        self._oauth_state_cache.discard(state)

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

    def import_accounts(self) -> dict[str, object]:
        token, token_source, _ = self._access_token_with_source()
        if token == "":
            raise MetaAdsIntegrationError("Meta account import requires a usable OAuth token. Connect Meta first.")

        return {
            "status": "ok",
            "provider": "meta_ads",
            "token_source": token_source,
            "accounts_discovered": 0,
            "imported": 0,
            "updated": 0,
            "unchanged": 0,
            "message": "Meta account import is enabled and awaiting account discovery implementation.",
        }

    def sync_client(
        self,
        *,
        client_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        grain: MetaSyncGrain | str | None = None,
        account_id: str | None = None,
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

            if resolved_grain == "account_daily":
                insights_rows = self._fetch_account_daily_insights(
                    account_id=account_id,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    access_token=access_token,
                )
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
                    conversions = self._derive_lead_conversions(actions=item.get("actions"))
                    conversion_value = self._derive_conversion_value(action_values=item.get("action_values"))

                    performance_reports_store.write_daily_report(
                        report_date=report_date_value,
                        platform="meta_ads",
                        customer_id=account_id,
                        client_id=int(client_id),
                        spend=spend,
                        impressions=impressions,
                        clicks=clicks,
                        conversions=conversions,
                        conversion_value=conversion_value,
                        extra_metrics={"meta_ads": self._base_extra_metrics(item)},
                    )
                    rows_written += 1
                    account_rows_written += 1
                    account_totals["spend"] += spend
                    account_totals["impressions"] += impressions
                    account_totals["clicks"] += clicks
                    account_totals["conversions"] += conversions
                    account_totals["conversion_value"] += conversion_value
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
                    conversions = self._derive_lead_conversions(actions=item.get("actions"))
                    conversion_value = self._derive_conversion_value(action_values=item.get("action_values"))

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

                account_rows_written = self._write_campaign_daily_rows(rows=campaign_rows)
                rows_written += account_rows_written
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
                    conversions = self._derive_lead_conversions(actions=item.get("actions"))
                    conversion_value = self._derive_conversion_value(action_values=item.get("action_values"))
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
                                    "campaign_id": campaign_id,
                                    "campaign_name": str(item.get("campaign_name") or "").strip() or None,
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

                account_rows_written = self._write_ad_group_daily_rows(rows=ad_group_rows)
                rows_written += account_rows_written
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
                    conversions = self._derive_lead_conversions(actions=item.get("actions"))
                    conversion_value = self._derive_conversion_value(action_values=item.get("action_values"))
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
                                    "adset_id": ad_group_id,
                                    "adset_name": str(item.get("adset_name") or "").strip() or None,
                                    "campaign_id": campaign_id,
                                    "campaign_name": str(item.get("campaign_name") or "").strip() or None,
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

                account_rows_written = self._write_ad_daily_rows(rows=ad_rows)
                rows_written += account_rows_written

            totals["spend"] += account_totals["spend"]
            totals["impressions"] += account_totals["impressions"]
            totals["clicks"] += account_totals["clicks"]
            totals["conversions"] += account_totals["conversions"]
            totals["revenue"] += account_totals["conversion_value"]

            account_summaries.append(
                {
                    "account_id": account_id,
                    "account_path": probe.get("account_path"),
                    "rows_written": account_rows_written,
                    "spend": round(account_totals["spend"], 2),
                    "impressions": account_totals["impressions"],
                    "clicks": account_totals["clicks"],
                    "conversions": round(account_totals["conversions"], 4),
                    "conversion_value": round(account_totals["conversion_value"], 2),
                }
            )

        snapshot = {
            "status": "ok",
            "message": f"Meta Ads {resolved_grain} sync completed.",
            "platform": "meta_ads",
            "grain": resolved_grain,
            "graph_version": self.graph_api_version(),
            "client_id": int(client_id),
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "accounts_processed": len(account_ids),
            "rows_written": rows_written,
            "token_source": token_source,
            "spend": round(totals["spend"], 2),
            "impressions": int(totals["impressions"]),
            "clicks": int(totals["clicks"]),
            "conversions": round(totals["conversions"], 4),
            "revenue": round(totals["revenue"], 2),
            "accounts": account_summaries,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

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

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return meta_snapshot_store.get_snapshot(client_id=client_id)


meta_ads_service = MetaAdsService()
