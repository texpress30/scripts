from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.error_observability import safe_body_snippet, sanitize_payload, sanitize_text
from app.services.entity_performance_reports import (
    upsert_ad_group_performance_reports,
    upsert_ad_unit_performance_reports,
    upsert_campaign_performance_reports,
)
from app.services.integration_secrets_store import integration_secrets_store
from app.services.performance_reports import performance_reports_store
from app.services.platform_entity_store import upsert_platform_ad_groups, upsert_platform_campaigns
from app.services.tiktok_account_daily_identity_resolver import resolve_tiktok_account_daily_persistence_identity
from app.services.tiktok_store import tiktok_snapshot_store

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


logger = logging.getLogger(__name__)


def _sanitize_endpoint(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if raw == "":
        return None
    try:
        parsed_url = parse.urlsplit(raw)
        query_pairs = parse.parse_qsl(parsed_url.query, keep_blank_values=True)
        sanitized_pairs: list[tuple[str, str]] = []
        for key, item in query_pairs:
            normalized_key = str(key or "").strip().lower()
            if any(part in normalized_key for part in ("token", "secret", "password", "authorization", "api_key", "apikey", "refresh_token")):
                sanitized_pairs.append((key, "***"))
            else:
                sanitized_pairs.append((key, sanitize_text(item, max_len=120)))
        sanitized_query = parse.urlencode(sanitized_pairs)
        rebuilt = parse.urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, sanitized_query, parsed_url.fragment))
        return sanitize_text(rebuilt, max_len=200)
    except Exception:
        return sanitize_text(raw, max_len=200)


class TikTokAdsIntegrationError(RuntimeError):
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
        error_category: str | None = None,
        token_source: str | None = None,
        advertiser_id: str | None = None,
    ) -> None:
        super().__init__(sanitize_text(message, max_len=400))
        self.endpoint = _sanitize_endpoint(endpoint)
        self.http_status = int(http_status) if http_status is not None else None
        self.provider_error_code = sanitize_text(provider_error_code, max_len=80) if provider_error_code is not None else None
        self.provider_error_message = sanitize_text(provider_error_message, max_len=300) if provider_error_message is not None else None
        self.body_snippet = sanitize_text(body_snippet, max_len=400) if body_snippet is not None else None
        self.retryable = retryable
        self.error_category = str(error_category).strip()[:80] if error_category is not None else None
        self.token_source = str(token_source).strip()[:80] if token_source is not None else None
        self.advertiser_id = sanitize_text(advertiser_id, max_len=120) if advertiser_id is not None else None

    def to_details(self) -> dict[str, object]:
        return {
            "error_summary": sanitize_text(str(self), max_len=300),
            "provider_error_code": self.provider_error_code,
            "provider_error_message": self.provider_error_message,
            "http_status": self.http_status,
            "endpoint": self.endpoint,
            "retryable": self.retryable,
            "body_snippet": self.body_snippet,
            "error_category": self.error_category,
            "token_source": self.token_source,
            "advertiser_id": self.advertiser_id,
        }


TikTokSyncGrain = Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]


@dataclass(frozen=True)
class TikTokReportingSchema:
    data_level: str
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class TikTokDailyMetric:
    report_date: date
    account_id: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokCampaignDailyMetric:
    report_date: date
    account_id: str
    campaign_id: str
    campaign_name: str | None
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]

@dataclass(frozen=True)
class TikTokAdGroupDailyMetric:
    report_date: date
    account_id: str
    ad_group_id: str
    ad_group_name: str | None
    adgroup_name: str | None
    campaign_id: str | None
    campaign_name: str | None
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokAdDailyMetric:
    report_date: date
    account_id: str
    ad_id: str
    ad_name: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


TikTokSyncGrain = Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]


@dataclass(frozen=True)
class TikTokDailyMetric:
    report_date: date
    account_id: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokCampaignDailyMetric:
    report_date: date
    account_id: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]

@dataclass(frozen=True)
class TikTokAdGroupDailyMetric:
    report_date: date
    account_id: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokAdDailyMetric:
    report_date: date
    account_id: str
    ad_id: str
    ad_name: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


TikTokSyncGrain = Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]


@dataclass(frozen=True)
class TikTokDailyMetric:
    report_date: date
    account_id: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokCampaignDailyMetric:
    report_date: date
    account_id: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]

@dataclass(frozen=True)
class TikTokAdGroupDailyMetric:
    report_date: date
    account_id: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


@dataclass(frozen=True)
class TikTokAdDailyMetric:
    report_date: date
    account_id: str
    ad_id: str
    ad_name: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    extra_metrics: dict[str, object]


class TikTokAdsService:
    _oauth_state_cache: set[str]

    def __init__(self) -> None:
        self._oauth_state_cache = set()
        self._memory_campaign_rows: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self._memory_ad_group_rows: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self._memory_ad_rows: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self._last_reporting_fetch_observability: dict[tuple[str, str], dict[str, object]] = {}

    def _is_test_mode(self) -> bool:
        settings = load_settings()
        return settings.app_env == "test"

    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _http_json(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        body = None
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, method=method.upper(), headers=request_headers)
        try:
            with request.urlopen(req, timeout=30) as response:  # noqa: S310
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
                    if isinstance(parsed, dict):
                        provider_code = parsed.get("code")
                        provider_message = parsed.get("message") or parsed.get("msg")
                except Exception:  # noqa: BLE001
                    provider_code = None
                    provider_message = None

            normalized_provider_code = sanitize_text(provider_code, max_len=80) if provider_code is not None else None
            normalized_provider_message = sanitize_text(provider_message, max_len=300) if provider_message is not None else None
            raise TikTokAdsIntegrationError(
                f"TikTok HTTP request failed: status={exc.code}",
                endpoint=url,
                http_status=exc.code,
                provider_error_code=normalized_provider_code,
                provider_error_message=normalized_provider_message,
                body_snippet=safe_body_snippet(raw_body),
                retryable=exc.code >= 500,
                error_category=self._map_tiktok_provider_error(
                    http_status=exc.code,
                    provider_error_code=normalized_provider_code,
                    provider_error_message=normalized_provider_message,
                ),
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise TikTokAdsIntegrationError(
                f"TikTok HTTP request failed: {sanitize_text(exc, max_len=200)}",
                endpoint=url,
                retryable=True,
            ) from exc

        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise TikTokAdsIntegrationError("TikTok API returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise TikTokAdsIntegrationError("TikTok API response shape is invalid")
        if isinstance(parsed.get("code"), int) and int(parsed.get("code") or 0) != 0:
            provider_error_code = sanitize_text(parsed.get("code"), max_len=80)
            provider_error_message = sanitize_text(parsed.get("message") or parsed.get("msg"), max_len=300)
            raise TikTokAdsIntegrationError(
                "TikTok API returned error payload",
                endpoint=url,
                provider_error_code=provider_error_code,
                provider_error_message=provider_error_message,
                body_snippet=safe_body_snippet(json.dumps(sanitize_payload(parsed))),
                retryable=False,
                error_category=self._map_tiktok_provider_error(
                    http_status=None,
                    provider_error_code=provider_error_code,
                    provider_error_message=provider_error_message,
                ),
            )
        return parsed

    def _map_tiktok_provider_error(
        self,
        *,
        http_status: int | None,
        provider_error_code: str | None,
        provider_error_message: str | None,
    ) -> str:
        message = str(provider_error_message or "").strip().lower()
        code = str(provider_error_code or "").strip().lower()
        if http_status == 401:
            return "token_missing_or_invalid"
        if http_status == 403:
            return "provider_access_denied"
        if "access token" in message or "access_token" in message or "token" in message and "invalid" in message:
            return "token_missing_or_invalid"
        if code in {"40100", "40101", "40102", "40103"}:
            return "token_missing_or_invalid"
        if "permission" in message or "no permission" in message or "access denied" in message or "forbidden" in message:
            return "provider_access_denied"
        return "provider_http_error_generic"

    def _advertiser_get_endpoint(self, *, query: str | None = None) -> str:
        settings = load_settings()
        base = f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/oauth2/advertiser/get/"
        if query:
            return f"{base}?{query}"
        return base

    def _probe_selected_advertiser_access(self, *, account_id: str, access_token: str, token_source: str) -> dict[str, object]:
        advertiser_id = self._normalize_account_id(account_id)
        endpoint = self._advertiser_get_endpoint()
        if advertiser_id == "":
            raise TikTokAdsIntegrationError(
                "TikTok advertiser id is required for access probe.",
                error_category="local_attachment_error",
                token_source=token_source,
                advertiser_id=advertiser_id,
            )

        try:
            accessible_accounts, _ = self._discover_accessible_advertiser_accounts(access_token=access_token)
        except TikTokAdsIntegrationError as exc:
            mapped_category = self._map_tiktok_provider_error(
                http_status=exc.http_status,
                provider_error_code=exc.provider_error_code,
                provider_error_message=exc.provider_error_message,
            )
            if str(mapped_category or "").strip() == "":
                if exc.http_status == 401:
                    mapped_category = "token_missing_or_invalid"
                elif exc.http_status == 403:
                    mapped_category = "provider_access_denied"
                else:
                    mapped_category = exc.error_category or "provider_http_error_generic"
            raise TikTokAdsIntegrationError(
                f"TikTok advertiser access probe failed for advertiser {advertiser_id}.",
                endpoint=exc.endpoint,
                http_status=exc.http_status,
                provider_error_code=exc.provider_error_code,
                provider_error_message=exc.provider_error_message,
                body_snippet=exc.body_snippet,
                retryable=exc.retryable,
                error_category=mapped_category,
                token_source=token_source,
                advertiser_id=advertiser_id,
            ) from exc

        accessible = any(
            self._normalize_account_id((item or {}).get("account_id")) == advertiser_id
            for item in accessible_accounts
            if isinstance(item, dict)
        )
        if not accessible:
            raise TikTokAdsIntegrationError(
                f"TikTok advertiser access denied for advertiser {advertiser_id}.",
                endpoint=endpoint,
                provider_error_message="Advertiser access denied: advertiser not returned by TikTok advertiser discovery.",
                retryable=False,
                error_category="provider_access_denied",
                token_source=token_source,
                advertiser_id=advertiser_id,
            )

        return {
            "status": "ok",
            "endpoint": endpoint,
            "advertiser_id": advertiser_id,
            "token_source": token_source,
        }

    def _is_placeholder(self, value: str) -> bool:
        normalized = value.strip().lower()
        return normalized == "" or normalized.startswith("your_")

    def _oauth_configured(self) -> bool:
        settings = load_settings()
        return not (
            self._is_placeholder(settings.tiktok_app_id)
            or self._is_placeholder(settings.tiktok_app_secret)
            or self._is_placeholder(settings.tiktok_redirect_uri)
        )

    def _get_secret(self, key: str):
        try:
            return integration_secrets_store.get_secret(provider="tiktok_ads", secret_key=key)
        except Exception:  # noqa: BLE001
            return None

    def _access_token_with_source(self) -> tuple[str, str, str | None]:
        token_secret = self._get_secret("access_token")
        if token_secret is None or token_secret.value.strip() == "":
            return "", "missing", None
        updated_at = token_secret.updated_at.isoformat() if token_secret.updated_at is not None else None
        return token_secret.value.strip(), "database", updated_at

    def _token_expires_at(self) -> str | None:
        expires_secret = self._get_secret("token_expires_at")
        if expires_secret is None:
            return None
        value = expires_secret.value.strip()
        return value if value != "" else None

    def build_oauth_authorize_url(self) -> dict[str, str]:
        settings = load_settings()
        if not self._oauth_configured():
            raise TikTokAdsIntegrationError("TikTok OAuth is not configured. Set TIKTOK_APP_ID, TIKTOK_APP_SECRET, and TIKTOK_REDIRECT_URI.")

        state = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8").rstrip("=")
        self._oauth_state_cache.add(state)
        params = {
            "app_id": settings.tiktok_app_id,
            "redirect_uri": settings.tiktok_redirect_uri,
            "state": state,
        }
        return {
            "authorize_url": f"https://business-api.tiktok.com/portal/auth?{parse.urlencode(params)}",
            "state": state,
        }

    def exchange_oauth_code(self, *, code: str, state: str) -> dict[str, object]:
        settings = load_settings()
        if not self._oauth_configured():
            raise TikTokAdsIntegrationError("TikTok OAuth is not configured. Set TIKTOK_APP_ID, TIKTOK_APP_SECRET, and TIKTOK_REDIRECT_URI.")
        if state not in self._oauth_state_cache:
            raise TikTokAdsIntegrationError("Invalid OAuth state for TikTok connect callback")
        self._oauth_state_cache.discard(state)

        token_payload = self._http_json(
            method="POST",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/oauth2/access_token/",
            payload={
                "app_id": settings.tiktok_app_id,
                "secret": settings.tiktok_app_secret,
                "auth_code": code,
                "grant_type": "authorized_code",
            },
        )

        container = token_payload.get("data") if isinstance(token_payload.get("data"), dict) else token_payload
        if not isinstance(container, dict):
            raise TikTokAdsIntegrationError("TikTok OAuth response is missing token container")

        access_token = str(container.get("access_token") or "").strip()
        if access_token == "":
            raise TikTokAdsIntegrationError("TikTok OAuth callback did not return an access token")

        integration_secrets_store.upsert_secret(provider="tiktok_ads", secret_key="access_token", value=access_token)

        refresh_token = str(container.get("refresh_token") or "").strip()
        if refresh_token:
            integration_secrets_store.upsert_secret(provider="tiktok_ads", secret_key="refresh_token", value=refresh_token)

        expires_in_raw = container.get("expires_in")
        token_expires_at: str | None = None
        if isinstance(expires_in_raw, (int, float)):
            expires_at = datetime.now(timezone.utc).timestamp() + float(expires_in_raw)
            token_expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
            integration_secrets_store.upsert_secret(provider="tiktok_ads", secret_key="token_expires_at", value=token_expires_at)

        _, token_source, token_updated_at = self._access_token_with_source()
        return {
            "status": "connected",
            "provider": "tiktok_ads",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "token_expires_at": token_expires_at,
            "has_usable_token": True,
            "message": "TikTok OAuth connected. Access token stored securely in application database.",
        }

    def integration_status(self) -> dict[str, object]:
        oauth_configured = self._oauth_configured()

        token, token_source, token_updated_at = self._access_token_with_source()
        token_expires_at = self._token_expires_at()
        has_usable_token = token != ""

        if not oauth_configured:
            return {
                "provider": "tiktok_ads",
                "status": "pending",
                "message": "TikTok Business OAuth configuration is incomplete. Set app id/secret/redirect URI.",
                "token_source": token_source,
                "token_updated_at": token_updated_at,
                "token_expires_at": token_expires_at,
                "oauth_configured": False,
                "has_usable_token": has_usable_token,
            }

        if has_usable_token:
            return {
                "provider": "tiktok_ads",
                "status": "connected",
                "message": "TikTok Business OAuth token is available.",
                "token_source": token_source,
                "token_updated_at": token_updated_at,
                "token_expires_at": token_expires_at,
                "oauth_configured": True,
                "has_usable_token": True,
            }

        return {
            "provider": "tiktok_ads",
            "status": "pending",
            "message": "TikTok Business OAuth is configured but no usable token is stored yet.",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "token_expires_at": token_expires_at,
            "oauth_configured": True,
            "has_usable_token": False,
        }

    def import_accounts(self) -> dict[str, object]:
        token, token_source, _ = self._access_token_with_source()
        if token == "":
            raise TikTokAdsIntegrationError("TikTok import requires a usable Business OAuth token. Connect TikTok first.")

        discovered_accounts, diagnostics = self._discover_accessible_advertiser_accounts(access_token=token)
        existing_accounts = client_registry_service.list_platform_accounts(platform="tiktok_ads")
        existing_by_id: dict[str, dict[str, object]] = {
            str(item.get("id") or "").strip(): item for item in existing_accounts if isinstance(item, dict)
        }

        if len(discovered_accounts) > 0:
            client_registry_service.upsert_platform_accounts(
                platform="tiktok_ads",
                accounts=[{"id": str(item["account_id"]), "name": str(item["account_name"])} for item in discovered_accounts],
            )

        imported = 0
        updated = 0
        unchanged = 0
        for account in discovered_accounts:
            account_id = str(account["account_id"])
            account_name = str(account["account_name"])
            status = str(account.get("status") or "").strip() or None
            currency_code = str(account.get("currency_code") or "").strip().upper() or None
            account_timezone = str(account.get("account_timezone") or "").strip() or None

            existing = existing_by_id.get(account_id)
            if existing is None:
                imported += 1
                client_registry_service.update_platform_account_operational_metadata(
                    platform="tiktok_ads",
                    account_id=account_id,
                    status=status,
                    currency_code=currency_code,
                    account_timezone=account_timezone,
                )
                continue

            existing_name = str(existing.get("name") or "").strip()
            existing_status = str(existing.get("status") or "").strip() or None
            existing_currency = str(existing.get("currency") or "").strip().upper() or None
            existing_timezone = str(existing.get("timezone") or "").strip() or None

            changed = (
                existing_name != account_name
                or existing_status != status
                or existing_currency != currency_code
                or existing_timezone != account_timezone
            )
            if changed:
                updated += 1
                client_registry_service.update_platform_account_operational_metadata(
                    platform="tiktok_ads",
                    account_id=account_id,
                    status=status,
                    currency_code=currency_code,
                    account_timezone=account_timezone,
                )
            else:
                unchanged += 1

        response: dict[str, object] = {
            "status": "ok",
            "provider": "tiktok_ads",
            "platform": "tiktok_ads",
            "token_source": token_source,
            "accounts_discovered": len(discovered_accounts),
            "imported": imported,
            "updated": updated,
            "unchanged": unchanged,
            "message": f"TikTok advertiser import completed: discovered={len(discovered_accounts)}, imported={imported}, updated={updated}, unchanged={unchanged}.",
        }
        if len(discovered_accounts) == 0:
            response["message"] = "TikTok advertiser discovery returned zero accounts. The token is valid, but no advertiser accounts appear to have granted access to this app."
            response["api_code"] = diagnostics.get("last_api_code")
            response["api_message"] = diagnostics.get("last_api_message")
            response["page_count_checked"] = diagnostics.get("page_count_checked")
            response["row_container_used"] = diagnostics.get("row_container_used")
        return response

    def list_accessible_advertiser_accounts(self, *, access_token: str | None = None) -> list[dict[str, object]]:
        rows, _ = self._discover_accessible_advertiser_accounts(access_token=access_token)
        return rows

    def _discover_accessible_advertiser_accounts(self, *, access_token: str | None = None) -> tuple[list[dict[str, object]], dict[str, object]]:
        resolved_access_token = str(access_token or "").strip()
        if resolved_access_token == "":
            token, _, _ = self._access_token_with_source()
            resolved_access_token = token
        if resolved_access_token == "":
            raise TikTokAdsIntegrationError("TikTok advertiser discovery requires a usable Business OAuth token.")

        settings = load_settings()
        app_id = str(settings.tiktok_app_id or "").strip()
        secret = str(settings.tiktok_app_secret or "").strip()
        if self._is_placeholder(app_id) or self._is_placeholder(secret):
            raise TikTokAdsIntegrationError("TikTok advertiser discovery requires configured TIKTOK_APP_ID and TIKTOK_APP_SECRET.")

        accounts: list[dict[str, object]] = []
        page = 1
        page_size = 100
        max_pages = 1000
        page_count_checked = 0
        row_container_used = "none"
        last_api_code: int | None = None
        last_api_message: str | None = None
        while page <= max_pages:
            page_count_checked += 1
            query = parse.urlencode({"app_id": app_id, "secret": secret, "page": page, "page_size": page_size})
            raw = self._http_json(
                method="GET",
                url=self._advertiser_get_endpoint(query=query),
                headers={"Access-Token": resolved_access_token},
            )
            api_code = raw.get("code")
            last_api_code = int(api_code) if isinstance(api_code, int) else None
            raw_message = raw.get("message")
            last_api_message = str(raw_message) if raw_message is not None else None
            if isinstance(api_code, int) and api_code != 0:
                raise TikTokAdsIntegrationError(f"TikTok advertiser discovery failed: code={api_code}, message={raw.get('message')}")

            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            rows = data.get("list")
            if not isinstance(rows, list):
                rows = data.get("advertisers") if isinstance(data.get("advertisers"), list) else []
                if isinstance(rows, list) and len(rows) > 0:
                    row_container_used = "data.advertisers"
            else:
                if len(rows) > 0:
                    row_container_used = "data.list"

            if not isinstance(rows, list) or len(rows) == 0:
                fallback_rows = data.get("accounts") if isinstance(data.get("accounts"), list) else None
                if isinstance(fallback_rows, list):
                    rows = fallback_rows
                    if len(rows) > 0:
                        row_container_used = "data.accounts"

            if not isinstance(rows, list) or len(rows) == 0:
                fallback_rows = data.get("rows") if isinstance(data.get("rows"), list) else None
                if isinstance(fallback_rows, list):
                    rows = fallback_rows
                    if len(rows) > 0:
                        row_container_used = "data.rows"

            if not isinstance(rows, list):
                rows = []

            for row in rows:
                if not isinstance(row, dict):
                    continue
                advertiser_id = str(row.get("advertiser_id") or row.get("id") or "").strip()
                if advertiser_id == "":
                    continue
                advertiser_name = str(row.get("advertiser_name") or row.get("name") or "").strip() or f"TikTok Advertiser {advertiser_id}"
                status = str(row.get("status") or row.get("advertiser_status") or "").strip() or None
                currency_code = str(row.get("currency_code") or row.get("currency") or "").strip().upper() or None
                account_timezone = str(row.get("account_timezone") or row.get("timezone") or "").strip() or None
                accounts.append(
                    {
                        "account_id": advertiser_id,
                        "account_name": advertiser_name,
                        "status": status,
                        "currency_code": currency_code,
                        "account_timezone": account_timezone,
                    }
                )

            page_info = data.get("page_info") if isinstance(data.get("page_info"), dict) else {}
            has_next_page = bool(page_info.get("has_next_page"))
            total_page_raw = page_info.get("total_page")
            total_page = int(total_page_raw) if isinstance(total_page_raw, (int, float)) else None
            current_page_raw = page_info.get("page")
            current_page = int(current_page_raw) if isinstance(current_page_raw, (int, float)) else page

            if has_next_page:
                page = current_page + 1
                continue
            if total_page is not None and current_page < total_page:
                page = current_page + 1
                continue
            break

        deduped: dict[str, dict[str, object]] = {}
        for item in accounts:
            deduped[str(item["account_id"])] = item
        deduped_rows = [deduped[key] for key in sorted(deduped.keys())]
        diagnostics: dict[str, object] = {
            "page_count_checked": page_count_checked,
            "row_container_used": row_container_used,
            "last_api_code": last_api_code,
            "last_api_message": last_api_message,
            "rows_before_dedupe": len(accounts),
            "rows_after_dedupe": len(deduped_rows),
        }
        logger.info(
            "tiktok_advertiser_discovery_summary",
            extra={
                "page_count_checked": page_count_checked,
                "row_container_used": row_container_used,
                "rows_before_dedupe": len(accounts),
                "rows_after_dedupe": len(deduped_rows),
                "api_code": last_api_code,
                "api_message": last_api_message,
            },
        )
        return deduped_rows, diagnostics

    def _resolve_sync_window(self, *, start_date: date | None, end_date: date | None) -> tuple[date, date]:
        if start_date is not None and end_date is not None:
            if start_date > end_date:
                raise TikTokAdsIntegrationError("start_date cannot be after end_date")
            return start_date, end_date

        today = datetime.now(timezone.utc).date()
        default_end = today - timedelta(days=1)
        default_start = default_end - timedelta(days=6)
        return default_start, default_end

    def _to_float(self, value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if raw == "":
                return 0.0
            try:
                return float(raw)
            except ValueError:
                return 0.0
        return 0.0

    def _to_int(self, value: object) -> int:
        return int(round(self._to_float(value)))

    def _extract_conversions(self, metrics: dict[str, object]) -> float:
        for key in ("conversion", "conversions", "complete_payment", "purchase"):
            if key in metrics:
                return self._to_float(metrics.get(key))
        return 0.0

    def _extract_conversion_value(self, metrics: dict[str, object]) -> float:
        for key in (
            "conversion_value",
            "total_purchase_value",
            "total_sales_lead_value",
            "real_time_conversion_value",
            "skan_total_purchase_value",
        ):
            if key in metrics:
                return self._to_float(metrics.get(key))
        return 0.0



    def _normalize_nested_map(self, value: object) -> dict[str, object]:
        if isinstance(value, dict):
            normalized: dict[str, object] = {}
            for key, item in value.items():
                key_text = str(key or "").strip()
                if key_text == "":
                    continue
                normalized[key_text] = item
            return normalized
        if not isinstance(value, list):
            return {}

        normalized: dict[str, object] = {}
        for entry in value:
            if isinstance(entry, dict):
                key_text = str(entry.get("key") or entry.get("name") or entry.get("field") or entry.get("dimension") or entry.get("metric") or "").strip()
                resolved_value: object | None = None
                if "value" in entry:
                    resolved_value = entry.get("value")
                elif "val" in entry:
                    resolved_value = entry.get("val")
                elif "data" in entry:
                    resolved_value = entry.get("data")
                elif len(entry) == 1:
                    only_key, only_value = next(iter(entry.items()))
                    key_text = str(only_key or "").strip()
                    resolved_value = only_value
                else:
                    for candidate_key, candidate_value in entry.items():
                        candidate_text = str(candidate_key or "").strip().lower()
                        if candidate_text in {"key", "name", "field", "dimension", "metric"}:
                            continue
                        resolved_value = candidate_value
                        break
                if key_text != "" and resolved_value is not None:
                    normalized[key_text] = resolved_value
                continue
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                key_text = str(entry[0] or "").strip()
                if key_text != "":
                    normalized[key_text] = entry[1]
        return normalized

    def _parse_tiktok_report_date(self, *, row: dict[str, object], dimensions_map: dict[str, object]) -> tuple[date | None, str, str | None]:
        candidates: list[tuple[str, object]] = [
            ("dimensions.stat_time_day", dimensions_map.get("stat_time_day")),
            ("row.stat_time_day", row.get("stat_time_day")),
            ("row.date", row.get("date")),
            ("dimensions.date", dimensions_map.get("date")),
        ]
        raw_value = None
        source = ""
        for candidate_source, candidate_value in candidates:
            if candidate_value is None:
                continue
            candidate_text = str(candidate_value).strip()
            if candidate_text == "":
                continue
            source = candidate_source
            raw_value = candidate_value
            break

        if raw_value is None:
            return None, source, "missing_stat_time_day"
        if isinstance(raw_value, datetime):
            return raw_value.date(), source, None
        if isinstance(raw_value, date):
            return raw_value, source, None

        value = str(raw_value).strip()
        if value == "":
            return None, source, "missing_stat_time_day"

        normalized = value.replace("/", "-")
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            if len(normalized) == 8 and normalized.isdigit():
                return datetime.strptime(normalized, "%Y%m%d").date(), source, None
            if "T" in normalized:
                return datetime.fromisoformat(normalized).date(), source, None
            if " " in normalized and ":" in normalized:
                return datetime.fromisoformat(normalized.replace(" ", "T", 1)).date(), source, None
            return date.fromisoformat(normalized), source, None
        except Exception:
            return None, source, "invalid_stat_time_day"

    def _dimensions_metrics_for_row(self, *, row: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        dimensions_map = self._normalize_nested_map(row.get("dimensions"))
        metrics_map = self._normalize_nested_map(row.get("metrics"))

        if len(dimensions_map) <= 0:
            for key in ("stat_time_day", "campaign_id", "campaign_name", "adgroup_id", "adgroup_name", "ad_id", "ad_name"):
                if key in row:
                    dimensions_map[key] = row.get(key)

        if len(metrics_map) <= 0:
            for key in (
                "spend",
                "impressions",
                "clicks",
                "conversion",
                "conversions",
                "total_purchase_value",
                "conversion_value",
                "total_sales_lead_value",
                "real_time_conversion_value",
                "skan_total_purchase_value",
            ):
                if key in row:
                    metrics_map[key] = row.get(key)

        return dimensions_map, metrics_map

    def _report_schema_for_grain(self, grain: TikTokSyncGrain) -> TikTokReportingSchema:
        if grain == "account_daily":
            return TikTokReportingSchema(
                data_level="AUCTION_ADVERTISER",
                dimensions=("stat_time_day",),
                metrics=("spend", "impressions", "clicks", "conversion", "total_purchase_value"),
            )
        if grain == "campaign_daily":
            return TikTokReportingSchema(
                data_level="AUCTION_CAMPAIGN",
                dimensions=("stat_time_day", "campaign_id"),
                metrics=("spend", "impressions", "clicks", "conversion", "total_purchase_value", "campaign_name"),
            )
        if grain == "ad_group_daily":
            return TikTokReportingSchema(
                data_level="AUCTION_ADGROUP",
                dimensions=("stat_time_day", "adgroup_id"),
                metrics=("spend", "impressions", "clicks", "conversion", "total_purchase_value", "adgroup_name", "campaign_id", "campaign_name", "adgroup_name"),
            )
        return TikTokReportingSchema(
            data_level="AUCTION_AD",
            dimensions=("stat_time_day", "ad_id"),
            metrics=("spend", "impressions", "clicks", "conversion", "total_purchase_value", "campaign_id", "campaign_name", "adgroup_id", "adgroup_name", "ad_name"),
        )

    def _record_reporting_fetch_observability(
        self,
        *,
        grain: TikTokSyncGrain,
        account_id: str,
        request_params: dict[str, object],
        endpoint: str,
        raw_response: dict[str, object],
        data: dict[str, object],
        provider_row_count: int,
        rows_mapped: int,
        skipped_non_dict: int,
        skipped_missing_required: int,
        skipped_invalid_date: int,
        missing_required_breakdown: dict[str, int] | None = None,
        sample_dimension_keys: list[str] | None = None,
        sample_metric_keys: list[str] | None = None,
        date_source_used: str | None = None,
        skip_reason_counts: dict[str, int] | None = None,
    ) -> None:
        list_value = data.get("list")
        sample_row_keys: list[str] = []
        if isinstance(list_value, list):
            for candidate in list_value:
                if isinstance(candidate, dict):
                    sample_row_keys = sorted([str(key) for key in candidate.keys()][:12])
                    break

        marker: str | None = None
        if provider_row_count == 0:
            marker = "provider_returned_empty_list"
        elif rows_mapped == 0:
            marker = "response_parsed_but_zero_rows_mapped"

        self._last_reporting_fetch_observability[(str(grain), str(account_id))] = {
            "grain": str(grain),
            "account_id": str(account_id),
            "endpoint": _sanitize_endpoint(endpoint),
            "report_type": str(request_params.get("report_type") or ""),
            "service_type": str(request_params.get("service_type") or ""),
            "query_mode": str(request_params.get("query_mode") or ""),
            "data_level": str(request_params.get("data_level") or ""),
            "dimensions": list(request_params.get("dimensions") or []),
            "metrics": list(request_params.get("metrics") or []),
            "advertiser_id": str(request_params.get("advertiser_id") or ""),
            "start_date": str(request_params.get("start_date") or ""),
            "end_date": str(request_params.get("end_date") or ""),
            "provider_row_count": int(provider_row_count),
            "rows_downloaded": int(provider_row_count),
            "rows_mapped": int(rows_mapped),
            "zero_row_marker": marker,
            "response_top_level_keys": sorted([str(key) for key in raw_response.keys()][:20]),
            "data_container_keys": sorted([str(key) for key in data.keys()][:20]),
            "sample_row_keys": sample_row_keys,
            "sample_dimension_keys": list(sample_dimension_keys or []),
            "sample_metric_keys": list(sample_metric_keys or []),
            "date_source_used": str(date_source_used or ""),
            "skipped_non_dict": int(skipped_non_dict),
            "skipped_missing_required": int(skipped_missing_required),
            "skipped_invalid_date": int(skipped_invalid_date),
            "missing_required_breakdown": dict(missing_required_breakdown or {}),
            "skip_reason_counts": dict(skip_reason_counts or {}),
        }

    def _consume_reporting_fetch_observability(self, *, grain: TikTokSyncGrain, account_id: str, rows_mapped: int) -> dict[str, object]:
        key = (str(grain), str(account_id))
        existing = self._last_reporting_fetch_observability.pop(key, None)
        if isinstance(existing, dict):
            return dict(existing)
        provider_rows = int(rows_mapped)
        return {
            "grain": str(grain),
            "account_id": str(account_id),
            "endpoint": None,
            "report_type": "BASIC",
            "service_type": "AUCTION",
            "query_mode": "REGULAR",
            "data_level": "",
            "dimensions": [],
            "metrics": [],
            "advertiser_id": str(account_id),
            "start_date": "",
            "end_date": "",
            "provider_row_count": provider_rows,
            "rows_downloaded": provider_rows,
            "rows_mapped": int(rows_mapped),
            "zero_row_marker": "provider_returned_empty_list" if provider_rows == 0 else None,
            "response_top_level_keys": [],
            "data_container_keys": [],
            "sample_row_keys": [],
            "sample_dimension_keys": [],
            "sample_metric_keys": [],
            "date_source_used": "",
            "skipped_non_dict": 0,
            "skipped_missing_required": 0,
            "skipped_invalid_date": 0,
            "missing_required_breakdown": {},
            "skip_reason_counts": {},
        }

    def _report_integrated_endpoint(self, *, query: str | None = None) -> str:
        settings = load_settings()
        base = f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/"
        if query:
            return f"{base}?{query}"
        return base

    def _campaign_get_endpoint(self) -> str:
        settings = load_settings()
        return f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/campaign/get/"

    def _adgroup_get_endpoint(self) -> str:
        settings = load_settings()
        return f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/adgroup/get/"

    def _fetch_campaign_metadata_by_ids(self, *, account_id: str, access_token: str, campaign_ids: list[str]) -> dict[str, dict[str, object]]:
        normalized_ids = [str(item or "").strip() for item in campaign_ids if str(item or "").strip() != ""]
        if len(normalized_ids) == 0:
            return {}
        filter_campaign_ids: list[object] = [int(item) if item.isdigit() else item for item in normalized_ids]

        campaign_metadata: dict[str, dict[str, object]] = {}
        page = 1
        page_size = 100
        endpoint = self._campaign_get_endpoint()
        while True:
            payload = self._http_json(
                method="POST",
                url=endpoint,
                payload={
                    "advertiser_id": str(account_id),
                    "filtering": {"campaign_ids": filter_campaign_ids},
                    "page": page,
                    "page_size": page_size,
                },
                headers={"Access-Token": access_token},
            )
            container = payload.get("data")
            if not isinstance(container, dict):
                break
            rows = container.get("list")
            if not isinstance(rows, list):
                break
            for item in rows:
                if not isinstance(item, dict):
                    continue
                campaign_id = str(item.get("campaign_id") or "").strip()
                if campaign_id == "":
                    continue
                campaign_name = str(item.get("campaign_name") or item.get("name") or "").strip()
                campaign_status = str(item.get("status") or item.get("operation_status") or item.get("secondary_status") or "").strip()
                raw_payload = dict(item)
                payload_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                campaign_metadata[campaign_id] = {
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "campaign_status": campaign_status,
                    "raw_payload": raw_payload,
                    "payload_hash": payload_hash,
                }

            page_info = container.get("page_info") if isinstance(container.get("page_info"), dict) else {}
            total_pages = int(page_info.get("total_page") or 1)
            if page >= total_pages:
                break
            page += 1

        return campaign_metadata

    def _campaign_entity_rows_for_upsert(self, *, account_id: str, metadata_by_id: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        rows_to_upsert: list[dict[str, object]] = []
        for campaign_id, payload in metadata_by_id.items():
            normalized_campaign_id = str(campaign_id or payload.get("campaign_id") or "").strip()
            if normalized_campaign_id == "":
                continue
            campaign_name = str(payload.get("campaign_name") or "").strip() or None
            campaign_status = str(payload.get("campaign_status") or "").strip() or None
            raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else {}
            if campaign_name is None and campaign_status is None and len(raw_payload) == 0:
                continue
            rows_to_upsert.append(
                {
                    "platform": "tiktok_ads",
                    "account_id": account_id,
                    "campaign_id": normalized_campaign_id,
                    "name": campaign_name,
                    "status": campaign_status,
                    "raw_payload": raw_payload,
                    "payload_hash": payload.get("payload_hash")
                    or hashlib.sha256(
                        json.dumps(
                            {
                                "campaign_id": normalized_campaign_id,
                                "campaign_name": campaign_name,
                                "campaign_status": campaign_status,
                                "raw_payload": raw_payload,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            )
        return rows_to_upsert

    def _ad_group_entity_rows_for_upsert(self, *, account_id: str, metadata_by_id: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        rows_to_upsert: list[dict[str, object]] = []
        for ad_group_id, payload in metadata_by_id.items():
            normalized_ad_group_id = str(ad_group_id or payload.get("ad_group_id") or "").strip()
            raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else {}
            campaign_id = str(
                payload.get("campaign_id")
                or payload.get("campaignId")
                or raw_payload.get("campaign_id")
                or raw_payload.get("campaignId")
                or ""
            ).strip()
            if normalized_ad_group_id == "" or campaign_id == "":
                continue
            ad_group_name = str(
                payload.get("ad_group_name")
                or payload.get("adgroup_name")
                or raw_payload.get("ad_group_name")
                or raw_payload.get("adgroup_name")
                or ""
            ).strip() or None
            ad_group_status = str(payload.get("ad_group_status") or "").strip() or None
            if ad_group_name is None and ad_group_status is None and len(raw_payload) == 0:
                continue
            rows_to_upsert.append(
                {
                    "platform": "tiktok_ads",
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "ad_group_id": normalized_ad_group_id,
                    "name": ad_group_name,
                    "status": ad_group_status,
                    "raw_payload": raw_payload,
                    "payload_hash": payload.get("payload_hash")
                    or hashlib.sha256(
                        json.dumps(
                            {
                                "ad_group_id": normalized_ad_group_id,
                                "campaign_id": campaign_id,
                                "ad_group_name": ad_group_name,
                                "ad_group_status": ad_group_status,
                                "raw_payload": raw_payload,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            )
        return rows_to_upsert

    def _resolve_and_persist_campaign_metadata(
        self,
        *,
        account_id: str,
        access_token: str,
        campaign_ids: list[str],
        report_campaign_name_by_id: dict[str, str],
    ) -> dict[str, dict[str, object]]:
        normalized_ids = sorted({str(item or "").strip() for item in campaign_ids if str(item or "").strip() != ""})
        if len(normalized_ids) == 0:
            return {}

        metadata_by_id: dict[str, dict[str, object]] = {
            campaign_id: {
                "campaign_id": campaign_id,
                "campaign_name": str(report_campaign_name_by_id.get(campaign_id) or "").strip(),
                "campaign_status": "",
                "raw_payload": {},
                "payload_hash": None,
            }
            for campaign_id in normalized_ids
        }

        try:
            fetched = self._fetch_campaign_metadata_by_ids(account_id=account_id, access_token=access_token, campaign_ids=normalized_ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TikTok campaign metadata fetch failed; continuing with report-level campaign names. account_id=%s error=%s",
                account_id,
                sanitize_text(str(exc), max_len=300),
            )
            fetched = {}

        for campaign_id, payload in fetched.items():
            base = metadata_by_id.setdefault(
                campaign_id,
                {"campaign_id": campaign_id, "campaign_name": "", "campaign_status": "", "raw_payload": {}, "payload_hash": None},
            )
            raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else {}
            fetched_name = str(
                payload.get("campaign_name")
                or raw_payload.get("campaign_name")
                or raw_payload.get("name")
                or ""
            ).strip()
            if fetched_name != "":
                base["campaign_name"] = fetched_name
            fetched_status = str(payload.get("campaign_status") or "").strip()
            if fetched_status != "":
                base["campaign_status"] = fetched_status
            if isinstance(raw_payload, dict):
                base["raw_payload"] = raw_payload
            if payload.get("payload_hash") is not None:
                base["payload_hash"] = payload.get("payload_hash")

        rows_to_upsert = self._campaign_entity_rows_for_upsert(account_id=account_id, metadata_by_id=metadata_by_id)

        if len(rows_to_upsert) > 0 and not self._is_test_mode():
            try:
                with self._connect() as conn:
                    upsert_platform_campaigns(conn, rows_to_upsert)
                    conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TikTok campaign metadata persistence failed; continuing with fact persistence. account_id=%s error=%s",
                    account_id,
                    sanitize_text(str(exc), max_len=300),
                )

        return metadata_by_id

    def _resolve_and_persist_campaign_metadata_safe(
        self,
        *,
        account_id: str,
        access_token: str,
        campaign_ids: list[str],
        report_campaign_name_by_id: dict[str, str],
    ) -> dict[str, dict[str, object]]:
        try:
            return self._resolve_and_persist_campaign_metadata(
                account_id=account_id,
                access_token=access_token,
                campaign_ids=campaign_ids,
                report_campaign_name_by_id=report_campaign_name_by_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TikTok campaign metadata resolve/persist failed; continuing with report-level campaign names. account_id=%s error=%s",
                account_id,
                sanitize_text(str(exc), max_len=300),
            )
            fallback_ids = {str(item or "").strip() for item in campaign_ids if str(item or "").strip() != ""}
            return {
                campaign_id: {
                    "campaign_id": campaign_id,
                    "campaign_name": str(report_campaign_name_by_id.get(campaign_id) or "").strip(),
                    "campaign_status": "",
                    "raw_payload": {},
                    "payload_hash": None,
                }
                for campaign_id in sorted(fallback_ids)
            }

    def _fetch_adgroup_metadata_by_ids(self, *, account_id: str, access_token: str, adgroup_ids: list[str]) -> dict[str, dict[str, object]]:
        normalized_ids = [str(item or "").strip() for item in adgroup_ids if str(item or "").strip() != ""]
        if len(normalized_ids) == 0:
            return {}
        filter_ad_group_ids: list[object] = [int(item) if item.isdigit() else item for item in normalized_ids]

        ad_group_metadata: dict[str, dict[str, object]] = {}
        page = 1
        page_size = 100
        endpoint = self._adgroup_get_endpoint()
        while True:
            payload = self._http_json(
                method="POST",
                url=endpoint,
                payload={
                    "advertiser_id": str(account_id),
                    "filtering": {"adgroup_ids": filter_ad_group_ids},
                    "page": page,
                    "page_size": page_size,
                },
                headers={"Access-Token": access_token},
            )
            container = payload.get("data")
            if not isinstance(container, dict):
                break
            rows = container.get("list")
            if not isinstance(rows, list):
                break
            for item in rows:
                if not isinstance(item, dict):
                    continue
                ad_group_id = str(item.get("adgroup_id") or item.get("ad_group_id") or "").strip()
                if ad_group_id == "":
                    continue
                ad_group_name = str(item.get("adgroup_name") or item.get("ad_group_name") or item.get("name") or "").strip()
                campaign_id = str(item.get("campaign_id") or item.get("campaignId") or "").strip()
                campaign_name = str(item.get("campaign_name") or item.get("campaignName") or "").strip()
                ad_group_status = str(item.get("status") or item.get("operation_status") or item.get("secondary_status") or "").strip()
                raw_payload = dict(item)
                payload_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                ad_group_metadata[ad_group_id] = {
                    "ad_group_id": ad_group_id,
                    "ad_group_name": ad_group_name,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "ad_group_status": ad_group_status,
                    "raw_payload": raw_payload,
                    "payload_hash": payload_hash,
                }

            page_info = container.get("page_info") if isinstance(container.get("page_info"), dict) else {}
            total_pages = int(page_info.get("total_page") or 1)
            if page >= total_pages:
                break
            page += 1
        return ad_group_metadata

    def _fetch_ad_group_metadata_by_ids(self, *, account_id: str, access_token: str, ad_group_ids: list[str]) -> dict[str, dict[str, object]]:
        return self._fetch_adgroup_metadata_by_ids(
            account_id=account_id,
            access_token=access_token,
            adgroup_ids=ad_group_ids,
        )

    def _resolve_and_persist_ad_group_metadata(
        self,
        *,
        account_id: str,
        access_token: str,
        ad_group_ids: list[str],
        report_ad_group_name_by_id: dict[str, str],
    ) -> dict[str, dict[str, object]]:
        normalized_ids = sorted({str(item or "").strip() for item in ad_group_ids if str(item or "").strip() != ""})
        if len(normalized_ids) == 0:
            return {}

        metadata_by_id: dict[str, dict[str, object]] = {
            ad_group_id: {
                "ad_group_id": ad_group_id,
                "ad_group_name": str(report_ad_group_name_by_id.get(ad_group_id) or "").strip(),
                "campaign_id": "",
                "campaign_name": "",
                "ad_group_status": "",
                "raw_payload": {},
                "payload_hash": None,
            }
            for ad_group_id in normalized_ids
        }
        try:
            fetched = self._fetch_ad_group_metadata_by_ids(account_id=account_id, access_token=access_token, ad_group_ids=normalized_ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TikTok ad group metadata fetch failed; continuing with report-level ad group fields. account_id=%s error=%s",
                account_id,
                sanitize_text(str(exc), max_len=300),
            )
            fetched = {}

        for ad_group_id, payload in fetched.items():
            base = metadata_by_id.setdefault(
                ad_group_id,
                {
                    "ad_group_id": ad_group_id,
                    "ad_group_name": "",
                    "campaign_id": "",
                    "campaign_name": "",
                    "ad_group_status": "",
                    "raw_payload": {},
                    "payload_hash": None,
                },
            )
            raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else {}
            fetched_name = str(payload.get("ad_group_name") or raw_payload.get("adgroup_name") or raw_payload.get("ad_group_name") or "").strip()
            fetched_campaign_id = str(payload.get("campaign_id") or raw_payload.get("campaign_id") or raw_payload.get("campaignId") or "").strip()
            fetched_campaign_name = str(payload.get("campaign_name") or raw_payload.get("campaign_name") or raw_payload.get("campaignName") or "").strip()
            fetched_status = str(payload.get("ad_group_status") or raw_payload.get("operation_status") or raw_payload.get("status") or "").strip()
            if fetched_name != "":
                base["ad_group_name"] = fetched_name
            if fetched_campaign_id != "":
                base["campaign_id"] = fetched_campaign_id
            if fetched_campaign_name != "":
                base["campaign_name"] = fetched_campaign_name
            if fetched_status != "":
                base["ad_group_status"] = fetched_status
            if isinstance(raw_payload, dict):
                base["raw_payload"] = raw_payload
            if payload.get("payload_hash") is not None:
                base["payload_hash"] = payload.get("payload_hash")

        rows_to_upsert = self._ad_group_entity_rows_for_upsert(account_id=account_id, metadata_by_id=metadata_by_id)

        if len(rows_to_upsert) > 0 and not self._is_test_mode():
            try:
                with self._connect() as conn:
                    upsert_platform_ad_groups(conn, rows_to_upsert)
                    conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TikTok ad group metadata persistence failed; continuing with fact persistence. account_id=%s error=%s",
                    account_id,
                    sanitize_text(str(exc), max_len=300),
                )

        return metadata_by_id

    def _resolve_and_persist_ad_group_metadata_safe(
        self,
        *,
        account_id: str,
        access_token: str,
        ad_group_ids: list[str],
        report_ad_group_name_by_id: dict[str, str],
    ) -> dict[str, dict[str, object]]:
        try:
            return self._resolve_and_persist_ad_group_metadata(
                account_id=account_id,
                access_token=access_token,
                ad_group_ids=ad_group_ids,
                report_ad_group_name_by_id=report_ad_group_name_by_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TikTok ad group metadata resolve/persist failed; continuing with report-level ad group fields. account_id=%s error=%s",
                account_id,
                sanitize_text(str(exc), max_len=300),
            )
            fallback_ids = {str(item or "").strip() for item in ad_group_ids if str(item or "").strip() != ""}
            return {
                ad_group_id: {
                    "ad_group_id": ad_group_id,
                    "ad_group_name": str(report_ad_group_name_by_id.get(ad_group_id) or "").strip(),
                    "campaign_id": "",
                    "campaign_name": "",
                    "ad_group_status": "",
                    "raw_payload": {},
                    "payload_hash": None,
                }
                for ad_group_id in sorted(fallback_ids)
            }

    def _build_report_integrated_query_params(
        self,
        *,
        account_id: str,
        report_type: str,
        service_type: str,
        query_mode: str,
        data_level: str,
        dimensions: list[str],
        metrics: list[str],
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict[str, object]:
        normalized_dimensions = [str(item).strip() for item in dimensions if str(item).strip() != ""]
        if str(data_level).strip().upper() == "AUCTION_CAMPAIGN" and "campaign_name" in normalized_dimensions:
            normalized_dimensions = [item for item in normalized_dimensions if item != "campaign_name"]
            logger.warning(
                "tiktok_reporting_removed_unsupported_dimension data_level=%s removed_dimension=campaign_name advertiser_id=%s",
                data_level,
                str(account_id),
            )
        return {
            "advertiser_id": str(account_id),
            "report_type": str(report_type or "BASIC"),
            "service_type": str(service_type or "AUCTION"),
            "query_mode": str(query_mode or "REGULAR"),
            "data_level": str(data_level),
            "dimensions": normalized_dimensions,
            "metrics": list(metrics),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": int(page),
            "page_size": int(page_size),
        }

    def _report_integrated_get(
        self,
        *,
        account_id: str,
        access_token: str,
        report_type: str,
        service_type: str,
        query_mode: str,
        data_level: str,
        dimensions: list[str],
        metrics: list[str],
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict[str, object]:
        params = self._build_report_integrated_query_params(
            account_id=account_id,
            report_type=report_type,
            service_type=service_type,
            query_mode=query_mode,
            data_level=data_level,
            dimensions=dimensions,
            metrics=metrics,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
        query = parse.urlencode(
            {
                "advertiser_id": params["advertiser_id"],
                "report_type": params["report_type"],
                "service_type": params["service_type"],
                "query_mode": params["query_mode"],
                "data_level": params["data_level"],
                "dimensions": json.dumps(params["dimensions"], separators=(",", ":")),
                "metrics": json.dumps(params["metrics"], separators=(",", ":")),
                "start_date": params["start_date"],
                "end_date": params["end_date"],
                "page": params["page"],
                "page_size": params["page_size"],
            }
        )
        return self._http_json(
            method="GET",
            url=self._report_integrated_endpoint(query=query),
            headers={"Access-Token": access_token},
        )

    def _fetch_account_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokDailyMetric]:
        schema = self._report_schema_for_grain("account_daily")
        request_params = self._build_report_integrated_query_params(
            account_id=account_id,
            report_type="BASIC",
            service_type="AUCTION",
            query_mode="REGULAR",
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )
        query = parse.urlencode(
            {
                "advertiser_id": request_params["advertiser_id"],
                "report_type": request_params["report_type"],
                "service_type": request_params["service_type"],
                "query_mode": request_params["query_mode"],
                "data_level": request_params["data_level"],
                "dimensions": json.dumps(request_params["dimensions"], separators=(",", ":")),
                "metrics": json.dumps(request_params["metrics"], separators=(",", ":")),
                "start_date": request_params["start_date"],
                "end_date": request_params["end_date"],
                "page": request_params["page"],
                "page_size": request_params["page_size"],
            }
        )
        report_endpoint = self._report_integrated_endpoint(query=query)
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type=str(request_params["report_type"]),
            service_type=str(request_params["service_type"]),
            query_mode=str(request_params["query_mode"]),
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )

        api_code = raw.get("code")
        if isinstance(api_code, int) and api_code != 0:
            raise TikTokAdsIntegrationError(f"TikTok reporting API failed for account {account_id}: code={api_code}, message={raw.get('message')}")

        data = raw.get("data")
        if not isinstance(data, dict):
            raise TikTokAdsIntegrationError(f"TikTok reporting API returned invalid data container for account {account_id}")

        rows_raw = data.get("list")
        if not isinstance(rows_raw, list):
            self._record_reporting_fetch_observability(
                grain="account_daily",
                account_id=account_id,
                request_params=request_params,
                endpoint=report_endpoint,
                raw_response=raw,
                provider_row_count=0,
                rows_mapped=0,
                data=data,
                skipped_non_dict=0,
                skipped_missing_required=0,
                skipped_invalid_date=0,
                missing_required_breakdown={},
                sample_dimension_keys=[],
                sample_metric_keys=[],
                date_source_used="",
                skip_reason_counts={},
            )
            return []

        rows: list[TikTokDailyMetric] = []
        skipped_non_dict = 0
        skipped_missing_required = 0
        skipped_invalid_date = 0
        missing_required_breakdown: dict[str, int] = {}
        skip_reason_counts: dict[str, int] = {}
        sample_dimension_keys: list[str] = []
        sample_metric_keys: list[str] = []
        date_source_used = ""
        for item in rows_raw:
            if not isinstance(item, dict):
                skipped_non_dict += 1
                continue
            dimensions, metrics = self._dimensions_metrics_for_row(row=item)
            if len(sample_dimension_keys) <= 0:
                sample_dimension_keys = sorted([str(key) for key in dimensions.keys()][:20])
            if len(sample_metric_keys) <= 0:
                sample_metric_keys = sorted([str(key) for key in metrics.keys()][:20])

            report_day, resolved_date_source, date_error = self._parse_tiktok_report_date(row=item, dimensions_map=dimensions)
            if date_error is not None:
                if date_error == "missing_stat_time_day":
                    skipped_missing_required += 1
                    missing_required_breakdown["stat_time_day"] = int(missing_required_breakdown.get("stat_time_day") or 0) + 1
                else:
                    skipped_invalid_date += 1
                skip_reason_counts[date_error] = int(skip_reason_counts.get(date_error) or 0) + 1
                continue
            if report_day is None:
                skipped_invalid_date += 1
                skip_reason_counts["invalid_stat_time_day"] = int(skip_reason_counts.get("invalid_stat_time_day") or 0) + 1
                continue
            if date_source_used == "" and resolved_date_source != "":
                date_source_used = resolved_date_source

            spend = self._to_float(metrics.get("spend"))
            impressions = self._to_int(metrics.get("impressions"))
            clicks = self._to_int(metrics.get("clicks"))
            conversions = self._extract_conversions(metrics)
            conversion_value = self._extract_conversion_value(metrics)

            rows.append(
                TikTokDailyMetric(
                    report_date=report_day,
                    account_id=account_id,
                    spend=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversion_value=conversion_value,
                    extra_metrics={
                        "tiktok_ads": {
                            "dimensions": dimensions,
                            "metrics": metrics,
                            "provider_identity_candidates": [
                                str(value).strip()
                                for value in (
                                    account_id,
                                    dimensions.get("advertiser_id"),
                                    dimensions.get("customer_id"),
                                    dimensions.get("account_id"),
                                    item.get("advertiser_id"),
                                    item.get("customer_id"),
                                    item.get("account_id"),
                                )
                                if str(value or "").strip() != ""
                            ],
                            "source": "report.integrated.get",
                            "grain": "account_daily",
                        }
                    },
                )
            )

        self._record_reporting_fetch_observability(
            grain="account_daily",
            account_id=account_id,
            request_params=request_params,
            endpoint=report_endpoint,
            raw_response=raw,
            provider_row_count=len(rows_raw),
            rows_mapped=len(rows),
            data=data,
            skipped_non_dict=skipped_non_dict,
            skipped_missing_required=skipped_missing_required,
            skipped_invalid_date=skipped_invalid_date,
            missing_required_breakdown=missing_required_breakdown,
            sample_dimension_keys=sample_dimension_keys,
            sample_metric_keys=sample_metric_keys,
            date_source_used=date_source_used,
            skip_reason_counts=skip_reason_counts,
        )

        return rows

    def _fetch_campaign_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokCampaignDailyMetric]:
        schema = self._report_schema_for_grain("campaign_daily")
        request_params = self._build_report_integrated_query_params(
            account_id=account_id,
            report_type="BASIC",
            service_type="AUCTION",
            query_mode="REGULAR",
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )
        query = parse.urlencode(
            {
                "advertiser_id": request_params["advertiser_id"],
                "report_type": request_params["report_type"],
                "service_type": request_params["service_type"],
                "query_mode": request_params["query_mode"],
                "data_level": request_params["data_level"],
                "dimensions": json.dumps(request_params["dimensions"], separators=(",", ":")),
                "metrics": json.dumps(request_params["metrics"], separators=(",", ":")),
                "start_date": request_params["start_date"],
                "end_date": request_params["end_date"],
                "page": request_params["page"],
                "page_size": request_params["page_size"],
            }
        )
        report_endpoint = self._report_integrated_endpoint(query=query)
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type=str(request_params["report_type"]),
            service_type=str(request_params["service_type"]),
            query_mode=str(request_params["query_mode"]),
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )

        api_code = raw.get("code")
        if isinstance(api_code, int) and api_code != 0:
            raise TikTokAdsIntegrationError(f"TikTok reporting API failed for account {account_id}: code={api_code}, message={raw.get('message')}")

        data = raw.get("data")
        if not isinstance(data, dict):
            raise TikTokAdsIntegrationError(f"TikTok reporting API returned invalid data container for account {account_id}")

        rows_raw = data.get("list")
        if not isinstance(rows_raw, list):
            self._record_reporting_fetch_observability(
                grain="campaign_daily",
                account_id=account_id,
                request_params=request_params,
                endpoint=report_endpoint,
                raw_response=raw,
                provider_row_count=0,
                rows_mapped=0,
                data=data,
                skipped_non_dict=0,
                skipped_missing_required=0,
                skipped_invalid_date=0,
                missing_required_breakdown={},
                sample_dimension_keys=[],
                sample_metric_keys=[],
                date_source_used="",
                skip_reason_counts={},
            )
            return []

        rows: list[TikTokCampaignDailyMetric] = []
        skipped_non_dict = 0
        skipped_missing_required = 0
        skipped_invalid_date = 0
        missing_required_breakdown: dict[str, int] = {}
        skip_reason_counts: dict[str, int] = {}
        sample_dimension_keys: list[str] = []
        sample_metric_keys: list[str] = []
        date_source_used = ""
        for item in rows_raw:
            if not isinstance(item, dict):
                skipped_non_dict += 1
                continue
            dimensions, metrics = self._dimensions_metrics_for_row(row=item)
            if len(sample_dimension_keys) <= 0:
                sample_dimension_keys = sorted([str(key) for key in dimensions.keys()][:20])
            if len(sample_metric_keys) <= 0:
                sample_metric_keys = sorted([str(key) for key in metrics.keys()][:20])

            report_day, resolved_date_source, date_error = self._parse_tiktok_report_date(row=item, dimensions_map=dimensions)
            campaign_id = str(dimensions.get("campaign_id") or metrics.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or metrics.get("campaign_name") or item.get("campaign_name") or "").strip()
            if date_error is not None or campaign_id == "":
                skipped_missing_required += 1
                if date_error == "missing_stat_time_day":
                    missing_required_breakdown["stat_time_day"] = int(missing_required_breakdown.get("stat_time_day") or 0) + 1
                elif date_error == "invalid_stat_time_day":
                    skipped_missing_required -= 1
                    skipped_invalid_date += 1
                if campaign_id == "":
                    missing_required_breakdown["campaign_id"] = int(missing_required_breakdown.get("campaign_id") or 0) + 1
                reason = date_error or "missing_campaign_id"
                if campaign_id == "" and date_error is not None:
                    reason = f"{reason}+missing_campaign_id"
                skip_reason_counts[reason] = int(skip_reason_counts.get(reason) or 0) + 1
                continue
            if report_day is None:
                skipped_invalid_date += 1
                skip_reason_counts["invalid_stat_time_day"] = int(skip_reason_counts.get("invalid_stat_time_day") or 0) + 1
                continue
            if date_source_used == "" and resolved_date_source != "":
                date_source_used = resolved_date_source

            spend = self._to_float(metrics.get("spend"))
            impressions = self._to_int(metrics.get("impressions"))
            clicks = self._to_int(metrics.get("clicks"))
            conversions = self._extract_conversions(metrics)
            conversion_value = self._extract_conversion_value(metrics)

            rows.append(
                TikTokCampaignDailyMetric(
                    report_date=report_day,
                    account_id=account_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    spend=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversion_value=conversion_value,
                    extra_metrics={
                        "tiktok_ads": {
                            "dimensions": dimensions,
                            "metrics": metrics,
                            "campaign_name": campaign_name,
                            "source": "report.integrated.get",
                            "grain": "campaign_daily",
                        }
                    },
                )
            )

        if len(rows) > 0:
            report_campaign_name_by_id = {
                str(row.campaign_id or "").strip(): str(row.campaign_name or "").strip()
                for row in rows
                if str(row.campaign_id or "").strip() != "" and str(row.campaign_name or "").strip() != ""
            }
            try:
                campaign_metadata_by_id = self._fetch_campaign_metadata_by_ids(
                    account_id=account_id,
                    access_token=access_token,
                    campaign_ids=[row.campaign_id for row in rows],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TikTok campaign metadata enrichment failed after reporting fetch; keeping report-level names. account_id=%s error=%s",
                    account_id,
                    sanitize_text(str(exc), max_len=300),
                )
                campaign_metadata_by_id = {}
            if len(campaign_metadata_by_id) > 0:
                enriched_rows: list[TikTokCampaignDailyMetric] = []
                for row in rows:
                    payload = campaign_metadata_by_id.get(str(row.campaign_id or "").strip(), {})
                    resolved_name = str(payload.get("campaign_name") or report_campaign_name_by_id.get(row.campaign_id) or row.campaign_name or "").strip()
                    enriched_rows.append(
                        TikTokCampaignDailyMetric(
                            report_date=row.report_date,
                            account_id=row.account_id,
                            campaign_id=row.campaign_id,
                            campaign_name=resolved_name,
                            spend=row.spend,
                            impressions=row.impressions,
                            clicks=row.clicks,
                            conversions=row.conversions,
                            conversion_value=row.conversion_value,
                            extra_metrics={
                                **row.extra_metrics,
                                "tiktok_ads": {
                                    **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                                    "campaign_name": resolved_name,
                                },
                            },
                        )
                    )
                rows = enriched_rows

        self._record_reporting_fetch_observability(
            grain="campaign_daily",
            account_id=account_id,
            request_params=request_params,
            endpoint=report_endpoint,
            raw_response=raw,
            provider_row_count=len(rows_raw),
            rows_mapped=len(rows),
            data=data,
            skipped_non_dict=skipped_non_dict,
            skipped_missing_required=skipped_missing_required,
            skipped_invalid_date=skipped_invalid_date,
            missing_required_breakdown=missing_required_breakdown,
            sample_dimension_keys=sample_dimension_keys,
            sample_metric_keys=sample_metric_keys,
            date_source_used=date_source_used,
            skip_reason_counts=skip_reason_counts,
        )

        return rows

    def _fetch_ad_group_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokAdGroupDailyMetric]:
        schema = self._report_schema_for_grain("ad_group_daily")
        request_params = self._build_report_integrated_query_params(
            account_id=account_id,
            report_type="BASIC",
            service_type="AUCTION",
            query_mode="REGULAR",
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )
        query = parse.urlencode(
            {
                "advertiser_id": request_params["advertiser_id"],
                "report_type": request_params["report_type"],
                "service_type": request_params["service_type"],
                "query_mode": request_params["query_mode"],
                "data_level": request_params["data_level"],
                "dimensions": json.dumps(request_params["dimensions"], separators=(",", ":")),
                "metrics": json.dumps(request_params["metrics"], separators=(",", ":")),
                "start_date": request_params["start_date"],
                "end_date": request_params["end_date"],
                "page": request_params["page"],
                "page_size": request_params["page_size"],
            }
        )
        report_endpoint = self._report_integrated_endpoint(query=query)
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type=str(request_params["report_type"]),
            service_type=str(request_params["service_type"]),
            query_mode=str(request_params["query_mode"]),
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )

        api_code = raw.get("code")
        if isinstance(api_code, int) and api_code != 0:
            raise TikTokAdsIntegrationError(f"TikTok reporting API failed for account {account_id}: code={api_code}, message={raw.get('message')}")

        data = raw.get("data")
        if not isinstance(data, dict):
            raise TikTokAdsIntegrationError(f"TikTok reporting API returned invalid data container for account {account_id}")

        rows_raw = data.get("list")
        if not isinstance(rows_raw, list):
            self._record_reporting_fetch_observability(
                grain="ad_group_daily",
                account_id=account_id,
                request_params=request_params,
                endpoint=report_endpoint,
                raw_response=raw,
                provider_row_count=0,
                rows_mapped=0,
                data=data,
                skipped_non_dict=0,
                skipped_missing_required=0,
                skipped_invalid_date=0,
                missing_required_breakdown={},
                sample_dimension_keys=[],
                sample_metric_keys=[],
                date_source_used="",
                skip_reason_counts={},
            )
            return []

        rows: list[TikTokAdGroupDailyMetric] = []
        skipped_non_dict = 0
        skipped_missing_required = 0
        skipped_invalid_date = 0
        missing_required_breakdown: dict[str, int] = {}
        skip_reason_counts: dict[str, int] = {}
        sample_dimension_keys: list[str] = []
        sample_metric_keys: list[str] = []
        date_source_used = ""
        for item in rows_raw:
            if not isinstance(item, dict):
                skipped_non_dict += 1
                continue
            dimensions, metrics = self._dimensions_metrics_for_row(row=item)
            if len(sample_dimension_keys) <= 0:
                sample_dimension_keys = sorted([str(key) for key in dimensions.keys()][:20])
            if len(sample_metric_keys) <= 0:
                sample_metric_keys = sorted([str(key) for key in metrics.keys()][:20])

            report_day, resolved_date_source, date_error = self._parse_tiktok_report_date(row=item, dimensions_map=dimensions)
            ad_group_id = str(
                dimensions.get("ad_group_id")
                or dimensions.get("adgroup_id")
                or metrics.get("adgroup_id")
                or item.get("ad_group_id")
                or item.get("adgroup_id")
                or ""
            ).strip()
            ad_group_name = str(dimensions.get("adgroup_name") or metrics.get("adgroup_name") or item.get("adgroup_name") or "").strip()
            campaign_id = str(dimensions.get("campaign_id") or metrics.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or metrics.get("campaign_name") or item.get("campaign_name") or "").strip()
            if date_error is not None or ad_group_id == "":
                skipped_missing_required += 1
                if date_error == "missing_stat_time_day":
                    missing_required_breakdown["stat_time_day"] = int(missing_required_breakdown.get("stat_time_day") or 0) + 1
                elif date_error == "invalid_stat_time_day":
                    skipped_missing_required -= 1
                    skipped_invalid_date += 1
                if ad_group_id == "":
                    missing_required_breakdown["adgroup_id"] = int(missing_required_breakdown.get("adgroup_id") or 0) + 1
                reason = date_error or "missing_adgroup_id"
                if ad_group_id == "" and date_error is not None:
                    reason = f"{reason}+missing_adgroup_id"
                skip_reason_counts[reason] = int(skip_reason_counts.get(reason) or 0) + 1
                continue
            if report_day is None:
                skipped_invalid_date += 1
                skip_reason_counts["invalid_stat_time_day"] = int(skip_reason_counts.get("invalid_stat_time_day") or 0) + 1
                continue
            if date_source_used == "" and resolved_date_source != "":
                date_source_used = resolved_date_source

            spend = self._to_float(metrics.get("spend"))
            impressions = self._to_int(metrics.get("impressions"))
            clicks = self._to_int(metrics.get("clicks"))
            conversions = self._extract_conversions(metrics)
            conversion_value = self._extract_conversion_value(metrics)

            rows.append(
                TikTokAdGroupDailyMetric(
                    report_date=report_day,
                    account_id=account_id,
                    ad_group_id=ad_group_id,
                    ad_group_name=ad_group_name,
                    adgroup_name=ad_group_name,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    spend=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversion_value=conversion_value,
                    extra_metrics={
                        "tiktok_ads": {
                            "dimensions": dimensions,
                            "metrics": metrics,
                            "adgroup_name": ad_group_name,
                            "ad_group_name": ad_group_name,
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "source": "report.integrated.get",
                            "grain": "ad_group_daily",
                        }
                    },
                )
            )

        if len(rows) > 0:
            report_ad_group_name_by_id = {
                str(row.ad_group_id or "").strip(): str(row.ad_group_name or "").strip()
                for row in rows
                if str(row.ad_group_id or "").strip() != "" and str(row.ad_group_name or "").strip() != ""
            }
            report_campaign_name_by_id = {
                str(row.campaign_id or "").strip(): str(row.campaign_name or "").strip()
                for row in rows
                if str(row.campaign_id or "").strip() != "" and str(row.campaign_name or "").strip() != ""
            }
            try:
                ad_group_metadata_by_id = self._fetch_adgroup_metadata_by_ids(
                    account_id=account_id,
                    access_token=access_token,
                    adgroup_ids=[row.ad_group_id for row in rows],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TikTok ad group metadata enrichment failed after reporting fetch; keeping report-level ad group fields. account_id=%s error=%s",
                    account_id,
                    sanitize_text(str(exc), max_len=300),
                )
                ad_group_metadata_by_id = {}

            resolved_campaign_ids = {
                str((ad_group_metadata_by_id.get(str(row.ad_group_id or "").strip()) or {}).get("campaign_id") or row.campaign_id or "").strip()
                for row in rows
                if str((ad_group_metadata_by_id.get(str(row.ad_group_id or "").strip()) or {}).get("campaign_id") or row.campaign_id or "").strip() != ""
            }
            if len(resolved_campaign_ids) > 0:
                try:
                    campaign_metadata_by_id = self._fetch_campaign_metadata_by_ids(
                        account_id=account_id,
                        access_token=access_token,
                        campaign_ids=sorted(resolved_campaign_ids),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "TikTok campaign metadata enrichment failed for ad groups; keeping fallback campaign names. account_id=%s error=%s",
                        account_id,
                        sanitize_text(str(exc), max_len=300),
                    )
                    campaign_metadata_by_id = {}
            else:
                campaign_metadata_by_id = {}

            enriched_rows: list[TikTokAdGroupDailyMetric] = []
            for row in rows:
                ad_group_metadata = ad_group_metadata_by_id.get(str(row.ad_group_id or "").strip(), {})
                resolved_campaign_id = str(ad_group_metadata.get("campaign_id") or row.campaign_id or "").strip()
                campaign_metadata = campaign_metadata_by_id.get(resolved_campaign_id, {})
                resolved_ad_group_name = str(
                    ad_group_metadata.get("ad_group_name")
                    or ad_group_metadata.get("adgroup_name")
                    or report_ad_group_name_by_id.get(row.ad_group_id)
                    or row.ad_group_name
                    or row.adgroup_name
                    or ""
                ).strip()
                resolved_campaign_name = str(
                    campaign_metadata.get("campaign_name")
                    or ad_group_metadata.get("campaign_name")
                    or report_campaign_name_by_id.get(resolved_campaign_id)
                    or row.campaign_name
                    or ""
                ).strip()
                enriched_rows.append(
                    TikTokAdGroupDailyMetric(
                        report_date=row.report_date,
                        account_id=row.account_id,
                        ad_group_id=row.ad_group_id,
                        ad_group_name=resolved_ad_group_name,
                        adgroup_name=resolved_ad_group_name,
                        campaign_id=resolved_campaign_id,
                        campaign_name=resolved_campaign_name,
                        spend=row.spend,
                        impressions=row.impressions,
                        clicks=row.clicks,
                        conversions=row.conversions,
                        conversion_value=row.conversion_value,
                        extra_metrics={
                            **row.extra_metrics,
                            "tiktok_ads": {
                                **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                                "campaign_id": resolved_campaign_id or None,
                                "campaign_name": resolved_campaign_name,
                                "adgroup_name": resolved_ad_group_name or None,
                                "ad_group_name": resolved_ad_group_name or None,
                            },
                        },
                    )
                )
            rows = enriched_rows

        self._record_reporting_fetch_observability(
            grain="ad_group_daily",
            account_id=account_id,
            request_params=request_params,
            endpoint=report_endpoint,
            raw_response=raw,
            provider_row_count=len(rows_raw),
            rows_mapped=len(rows),
            data=data,
            skipped_non_dict=skipped_non_dict,
            skipped_missing_required=skipped_missing_required,
            skipped_invalid_date=skipped_invalid_date,
            missing_required_breakdown=missing_required_breakdown,
            sample_dimension_keys=sample_dimension_keys,
            sample_metric_keys=sample_metric_keys,
            date_source_used=date_source_used,
            skip_reason_counts=skip_reason_counts,
        )

        return rows

    def _fetch_ad_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokAdDailyMetric]:
        schema = self._report_schema_for_grain("ad_daily")
        request_params = self._build_report_integrated_query_params(
            account_id=account_id,
            report_type="BASIC",
            service_type="AUCTION",
            query_mode="REGULAR",
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )
        query = parse.urlencode(
            {
                "advertiser_id": request_params["advertiser_id"],
                "report_type": request_params["report_type"],
                "service_type": request_params["service_type"],
                "query_mode": request_params["query_mode"],
                "data_level": request_params["data_level"],
                "dimensions": json.dumps(request_params["dimensions"], separators=(",", ":")),
                "metrics": json.dumps(request_params["metrics"], separators=(",", ":")),
                "start_date": request_params["start_date"],
                "end_date": request_params["end_date"],
                "page": request_params["page"],
                "page_size": request_params["page_size"],
            }
        )
        report_endpoint = self._report_integrated_endpoint(query=query)
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type=str(request_params["report_type"]),
            service_type=str(request_params["service_type"]),
            query_mode=str(request_params["query_mode"]),
            data_level=schema.data_level,
            dimensions=list(schema.dimensions),
            metrics=list(schema.metrics),
            start_date=start_date,
            end_date=end_date,
        )

        api_code = raw.get("code")
        if isinstance(api_code, int) and api_code != 0:
            raise TikTokAdsIntegrationError(f"TikTok reporting API failed for account {account_id}: code={api_code}, message={raw.get('message')}")

        data = raw.get("data")
        if not isinstance(data, dict):
            raise TikTokAdsIntegrationError(f"TikTok reporting API returned invalid data container for account {account_id}")

        rows_raw = data.get("list")
        if not isinstance(rows_raw, list):
            self._record_reporting_fetch_observability(
                grain="ad_daily",
                account_id=account_id,
                request_params=request_params,
                endpoint=report_endpoint,
                raw_response=raw,
                provider_row_count=0,
                rows_mapped=0,
                data=data,
                skipped_non_dict=0,
                skipped_missing_required=0,
                skipped_invalid_date=0,
                missing_required_breakdown={},
                sample_dimension_keys=[],
                sample_metric_keys=[],
                date_source_used="",
                skip_reason_counts={},
            )
            return []

        rows: list[TikTokAdDailyMetric] = []
        skipped_non_dict = 0
        skipped_missing_required = 0
        skipped_invalid_date = 0
        missing_required_breakdown: dict[str, int] = {}
        skip_reason_counts: dict[str, int] = {}
        sample_dimension_keys: list[str] = []
        sample_metric_keys: list[str] = []
        date_source_used = ""
        for item in rows_raw:
            if not isinstance(item, dict):
                skipped_non_dict += 1
                continue
            dimensions, metrics = self._dimensions_metrics_for_row(row=item)
            if len(sample_dimension_keys) <= 0:
                sample_dimension_keys = sorted([str(key) for key in dimensions.keys()][:20])
            if len(sample_metric_keys) <= 0:
                sample_metric_keys = sorted([str(key) for key in metrics.keys()][:20])

            report_day, resolved_date_source, date_error = self._parse_tiktok_report_date(row=item, dimensions_map=dimensions)
            ad_id = str(dimensions.get("ad_id") or item.get("ad_id") or "").strip()
            ad_name = str(dimensions.get("ad_name") or metrics.get("ad_name") or item.get("ad_name") or "").strip()
            ad_group_id = str(
                dimensions.get("ad_group_id")
                or dimensions.get("adgroup_id")
                or metrics.get("adgroup_id")
                or item.get("ad_group_id")
                or item.get("adgroup_id")
                or ""
            ).strip()
            ad_group_name = str(dimensions.get("adgroup_name") or metrics.get("adgroup_name") or item.get("adgroup_name") or "").strip()
            campaign_id = str(dimensions.get("campaign_id") or metrics.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or metrics.get("campaign_name") or item.get("campaign_name") or "").strip()
            if date_error is not None or ad_id == "":
                skipped_missing_required += 1
                if date_error == "missing_stat_time_day":
                    missing_required_breakdown["stat_time_day"] = int(missing_required_breakdown.get("stat_time_day") or 0) + 1
                elif date_error == "invalid_stat_time_day":
                    skipped_missing_required -= 1
                    skipped_invalid_date += 1
                if ad_id == "":
                    missing_required_breakdown["ad_id"] = int(missing_required_breakdown.get("ad_id") or 0) + 1
                reason = date_error or "missing_ad_id"
                if ad_id == "" and date_error is not None:
                    reason = f"{reason}+missing_ad_id"
                skip_reason_counts[reason] = int(skip_reason_counts.get(reason) or 0) + 1
                continue
            if report_day is None:
                skipped_invalid_date += 1
                skip_reason_counts["invalid_stat_time_day"] = int(skip_reason_counts.get("invalid_stat_time_day") or 0) + 1
                continue
            if date_source_used == "" and resolved_date_source != "":
                date_source_used = resolved_date_source

            spend = self._to_float(metrics.get("spend"))
            impressions = self._to_int(metrics.get("impressions"))
            clicks = self._to_int(metrics.get("clicks"))
            conversions = self._extract_conversions(metrics)
            conversion_value = self._extract_conversion_value(metrics)

            rows.append(
                TikTokAdDailyMetric(
                    report_date=report_day,
                    account_id=account_id,
                    ad_id=ad_id,
                    ad_name=ad_name,
                    ad_group_id=ad_group_id,
                    ad_group_name=ad_group_name,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    spend=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversion_value=conversion_value,
                    extra_metrics={
                        "tiktok_ads": {
                            "dimensions": dimensions,
                            "metrics": metrics,
                            "ad_name": ad_name,
                            "ad_group_id": ad_group_id,
                            "ad_group_name": ad_group_name,
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "source": "report.integrated.get",
                            "grain": "ad_daily",
                        }
                    },
                )
            )

        self._record_reporting_fetch_observability(
            grain="ad_daily",
            account_id=account_id,
            request_params=request_params,
            endpoint=report_endpoint,
            raw_response=raw,
            provider_row_count=len(rows_raw),
            rows_mapped=len(rows),
            data=data,
            skipped_non_dict=skipped_non_dict,
            skipped_missing_required=skipped_missing_required,
            skipped_invalid_date=skipped_invalid_date,
            missing_required_breakdown=missing_required_breakdown,
            sample_dimension_keys=sample_dimension_keys,
            sample_metric_keys=sample_metric_keys,
            date_source_used=date_source_used,
            skip_reason_counts=skip_reason_counts,
        )

        return rows

    def _upsert_ad_group_rows(
        self,
        rows: list[TikTokAdGroupDailyMetric],
        *,
        source_window_start: date,
        source_window_end: date,
        access_token: str | None = None,
    ) -> int:
        if len(rows) == 0:
            return 0

        if self._is_test_mode():
            for row in rows:
                resolved_campaign_id = str(row.campaign_id or "").strip()
                tiktok_meta = row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics, dict) else {}
                if resolved_campaign_id == "" and isinstance(tiktok_meta, dict):
                    resolved_campaign_id = str(tiktok_meta.get("campaign_id") or "").strip()
                key = ("tiktok_ads", row.account_id, row.ad_group_id, row.report_date.isoformat())
                self._memory_ad_group_rows[key] = {
                    "platform": "tiktok_ads",
                    "account_id": row.account_id,
                    "campaign_id": row.campaign_id,
                    "ad_group_id": row.ad_group_id,
                    "ad_group_name": row.ad_group_name,
                    "adgroup_name": row.adgroup_name or row.ad_group_name,
                    "campaign_id": resolved_campaign_id or None,
                    "campaign_name": row.campaign_name,
                    "report_date": row.report_date.isoformat(),
                    "spend": row.spend,
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "conversions": row.conversions,
                    "conversion_value": row.conversion_value,
                    "extra_metrics": row.extra_metrics,
                    "source_window_start": source_window_start.isoformat(),
                    "source_window_end": source_window_end.isoformat(),
                }
            return len(rows)

        payload_rows = []
        for row in rows:
            resolved_campaign_id = str(row.campaign_id or "").strip()
            tiktok_meta = row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics, dict) else {}
            if resolved_campaign_id == "" and isinstance(tiktok_meta, dict):
                resolved_campaign_id = str(tiktok_meta.get("campaign_id") or "").strip()
            payload_rows.append(
                {
                "platform": "tiktok_ads",
                "account_id": row.account_id,
                "campaign_id": row.campaign_id,
                "ad_group_id": row.ad_group_id,
                "campaign_id": resolved_campaign_id or None,
                "report_date": row.report_date,
                "spend": row.spend,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "conversions": row.conversions,
                "conversion_value": row.conversion_value,
                "extra_metrics": {
                    **(row.extra_metrics if isinstance(row.extra_metrics, dict) else {}),
                    "tiktok_ads": {
                        **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics, dict) and isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                        "adgroup_name": row.adgroup_name or row.ad_group_name,
                        "ad_group_name": row.ad_group_name or row.adgroup_name,
                        "campaign_name": row.campaign_name,
                        "campaign_id": resolved_campaign_id or None,
                    },
                },
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            }
            )
        with self._connect() as conn:
            normalized_account_ids = sorted({str(row.account_id or "").strip() for row in rows if str(row.account_id or "").strip() != ""})
            if access_token is None:
                logger.warning(
                    "TikTok ad group metadata fetch skipped during upsert because access_token is missing. account_ids=%s",
                    ",".join(normalized_account_ids),
                )
            else:
                for normalized_account_id in normalized_account_ids:
                    account_rows = [row for row in rows if str(row.account_id or "").strip() == normalized_account_id]
                    ad_group_ids = sorted({str(row.ad_group_id or "").strip() for row in account_rows if str(row.ad_group_id or "").strip() != ""})
                    report_ad_group_name_by_id = {
                        str(row.ad_group_id or "").strip(): str(row.ad_group_name or "").strip()
                        for row in account_rows
                        if str(row.ad_group_id or "").strip() != "" and str(row.ad_group_name or "").strip() != ""
                    }
                    if len(ad_group_ids) == 0:
                        continue
                    try:
                        ad_group_metadata_by_id = self._resolve_and_persist_ad_group_metadata(
                            account_id=normalized_account_id,
                            access_token=access_token,
                            ad_group_ids=ad_group_ids,
                            report_ad_group_name_by_id=report_ad_group_name_by_id,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "TikTok ad group metadata resolve failed during upsert; continuing with fact persistence. account_id=%s error=%s",
                            normalized_account_id,
                            sanitize_text(str(exc), max_len=300),
                        )
                        ad_group_metadata_by_id = {}
                    if len(ad_group_metadata_by_id) > 0:
                        rows_to_upsert = self._ad_group_entity_rows_for_upsert(
                            account_id=normalized_account_id,
                            metadata_by_id=ad_group_metadata_by_id,
                        )
                        if len(rows_to_upsert) > 0:
                            upsert_platform_ad_groups(conn, rows_to_upsert)
            written = int(upsert_ad_group_performance_reports(conn, payload_rows) or 0)
            conn.commit()
            return written

    def _upsert_campaign_rows(
        self,
        rows: list[TikTokCampaignDailyMetric],
        *,
        source_window_start: date,
        source_window_end: date,
        access_token: str | None = None,
    ) -> int:
        if len(rows) == 0:
            return 0

        if self._is_test_mode():
            for row in rows:
                campaign_extra_metrics = row.extra_metrics if isinstance(row.extra_metrics, dict) else {}
                key = ("tiktok_ads", row.account_id, row.campaign_id, row.report_date.isoformat())
                self._memory_campaign_rows[key] = {
                    "platform": "tiktok_ads",
                    "account_id": row.account_id,
                    "campaign_id": row.campaign_id,
                    "campaign_name": row.campaign_name,
                    "report_date": row.report_date.isoformat(),
                    "spend": row.spend,
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "conversions": row.conversions,
                    "conversion_value": row.conversion_value,
                    "extra_metrics": {
                        **campaign_extra_metrics,
                        "tiktok_ads": {
                            **(campaign_extra_metrics.get("tiktok_ads") if isinstance(campaign_extra_metrics.get("tiktok_ads"), dict) else {}),
                            "campaign_name": row.campaign_name,
                        },
                    },
                    "source_window_start": source_window_start.isoformat(),
                    "source_window_end": source_window_end.isoformat(),
                }
            return len(rows)

        payload_rows = [
            {
                "platform": "tiktok_ads",
                "account_id": row.account_id,
                "campaign_id": row.campaign_id,
                "report_date": row.report_date,
                "spend": row.spend,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "conversions": row.conversions,
                "conversion_value": row.conversion_value,
                "extra_metrics": {
                    **(row.extra_metrics if isinstance(row.extra_metrics, dict) else {}),
                    "tiktok_ads": {
                        **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics, dict) and isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                        "campaign_name": row.campaign_name,
                    },
                },
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            }
            for row in rows
        ]
        with self._connect() as conn:
            normalized_account_ids = sorted({str(row.account_id or "").strip() for row in rows if str(row.account_id or "").strip() != ""})
            if access_token is None:
                logger.warning(
                    "TikTok campaign metadata fetch skipped during upsert because access_token is missing. account_ids=%s",
                    ",".join(normalized_account_ids),
                )
            else:
                for normalized_account_id in normalized_account_ids:
                    account_rows = [row for row in rows if str(row.account_id or "").strip() == normalized_account_id]
                    campaign_ids = sorted({str(row.campaign_id or "").strip() for row in account_rows if str(row.campaign_id or "").strip() != ""})
                    report_campaign_name_by_id = {
                        str(row.campaign_id or "").strip(): str(row.campaign_name or "").strip()
                        for row in account_rows
                        if str(row.campaign_id or "").strip() != "" and str(row.campaign_name or "").strip() != ""
                    }
                    if len(campaign_ids) == 0:
                        continue
                    try:
                        campaign_metadata_by_id = self._resolve_and_persist_campaign_metadata(
                            account_id=normalized_account_id,
                            access_token=access_token,
                            campaign_ids=campaign_ids,
                            report_campaign_name_by_id=report_campaign_name_by_id,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "TikTok campaign metadata resolve failed during upsert; continuing with fact persistence. account_id=%s error=%s",
                            normalized_account_id,
                            sanitize_text(str(exc), max_len=300),
                        )
                        campaign_metadata_by_id = {}
                    if len(campaign_metadata_by_id) > 0:
                        rows_to_upsert = self._campaign_entity_rows_for_upsert(
                            account_id=normalized_account_id,
                            metadata_by_id=campaign_metadata_by_id,
                        )
                        if len(rows_to_upsert) > 0:
                            upsert_platform_campaigns(conn, rows_to_upsert)
            written = int(upsert_campaign_performance_reports(conn, payload_rows) or 0)
            conn.commit()
            return written

    def _upsert_ad_rows(self, rows: list[TikTokAdDailyMetric], *, source_window_start: date, source_window_end: date) -> int:
        if len(rows) == 0:
            return 0

        if self._is_test_mode():
            for row in rows:
                key = ("tiktok_ads", row.account_id, row.ad_id, row.report_date.isoformat())
                self._memory_ad_rows[key] = {
                    "platform": "tiktok_ads",
                    "account_id": row.account_id,
                    "ad_id": row.ad_id,
                    "ad_name": row.ad_name,
                    "ad_group_id": row.ad_group_id,
                    "ad_group_name": row.ad_group_name,
                    "campaign_id": row.campaign_id,
                    "campaign_name": row.campaign_name,
                    "report_date": row.report_date.isoformat(),
                    "spend": row.spend,
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "conversions": row.conversions,
                    "conversion_value": row.conversion_value,
                    "extra_metrics": row.extra_metrics,
                    "source_window_start": source_window_start.isoformat(),
                    "source_window_end": source_window_end.isoformat(),
                }
            return len(rows)

        payload_rows = [
            {
                "platform": "tiktok_ads",
                "account_id": row.account_id,
                "ad_id": row.ad_id,
                "campaign_id": row.campaign_id or None,
                "ad_group_id": row.ad_group_id or None,
                "report_date": row.report_date,
                "spend": row.spend,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "conversions": row.conversions,
                "conversion_value": row.conversion_value,
                "extra_metrics": {
                    **row.extra_metrics,
                    "tiktok_ads": {
                        **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                        "ad_name": row.ad_name,
                        "ad_group_name": row.ad_group_name,
                        "campaign_name": row.campaign_name,
                    },
                },
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            }
            for row in rows
        ]
        with self._connect() as conn:
            written = int(upsert_ad_unit_performance_reports(conn, payload_rows) or 0)
            conn.commit()
            return written

    def _normalize_account_id(self, value: object) -> str:
        return str(value or "").strip()

    def _collapse_account_daily_rows_for_persistence(
        self,
        *,
        rows: list[TikTokDailyMetric],
        canonical_persistence_customer_id: str,
    ) -> tuple[list[TikTokDailyMetric], int]:
        # Deterministic last-write-wins collapse within a single write batch for the
        # same logical natural key: (platform=tiktok_ads, grain=account_daily,
        # report_date, canonical_persistence_customer_id).
        by_natural_key: dict[tuple[str, str], tuple[int, TikTokDailyMetric]] = {}
        duplicate_candidates = 0
        for index, row in enumerate(rows):
            natural_key = (row.report_date.isoformat(), canonical_persistence_customer_id)
            if natural_key in by_natural_key:
                duplicate_candidates += 1
            by_natural_key[natural_key] = (index, row)

        ordered_keys = sorted(by_natural_key.keys(), key=lambda key: key[0])
        collapsed_rows = [by_natural_key[key][1] for key in ordered_keys]
        return collapsed_rows, duplicate_candidates

    def _resolve_target_account_ids(self, *, client_id: int, account_id: str | None = None) -> list[str]:
        attached_accounts = client_registry_service.list_client_platform_accounts(platform="tiktok_ads", client_id=int(client_id))
        attached_by_normalized: dict[str, str] = {}
        for item in attached_accounts:
            if not isinstance(item, dict):
                continue
            normalized_id = self._normalize_account_id(item.get("id"))
            if normalized_id == "":
                continue
            attached_by_normalized[normalized_id] = normalized_id

        if len(attached_by_normalized) <= 0:
            raise TikTokAdsIntegrationError("No TikTok advertiser accounts are attached to this client.", error_category="local_attachment_error")

        requested_account_id = self._normalize_account_id(account_id)
        if requested_account_id != "":
            selected = attached_by_normalized.get(requested_account_id)
            if selected is None:
                raise TikTokAdsIntegrationError(f"TikTok account_id '{requested_account_id}' is not attached to client_id={int(client_id)}.", error_category="local_attachment_error", advertiser_id=requested_account_id)
            return [selected]

        return list(attached_by_normalized.values())

    def sync_client(
        self,
        *,
        client_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        grain: TikTokSyncGrain = "account_daily",
        account_id: str | None = None,
    ) -> dict[str, object]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.", error_category="provider_http_error_generic")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.", error_category="local_attachment_error")

        resolved_grain = str(grain).strip().lower()
        if resolved_grain not in {"account_daily", "campaign_daily", "ad_group_daily", "ad_daily"}:
            raise TikTokAdsIntegrationError(f"grain invalid: {resolved_grain}", error_category="local_attachment_error")

        range_start, range_end = self._resolve_sync_window(start_date=start_date, end_date=end_date)

        access_token, token_source, _ = self._access_token_with_source()
        if access_token == "":
            raise TikTokAdsIntegrationError("TikTok sync requires a usable OAuth token. Connect TikTok first.", error_category="token_missing_or_invalid", token_source=token_source)

        account_ids = self._resolve_target_account_ids(client_id=int(client_id), account_id=account_id)

        for selected_account_id in account_ids:
            self._probe_selected_advertiser_access(
                account_id=selected_account_id,
                access_token=access_token,
                token_source=token_source,
            )

        rows_written = 0
        rows_downloaded = 0
        rows_mapped = 0
        zero_row_observability: list[dict[str, object]] = []
        account_daily_identity_warnings: list[dict[str, object]] = []
        totals = {
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0.0,
            "revenue": 0.0,
        }

        if resolved_grain == "account_daily":
            for account_id in account_ids:
                daily_rows = self._fetch_account_daily_metrics(
                    account_id=account_id,
                    access_token=access_token,
                    start_date=range_start,
                    end_date=range_end,
                )
                fetch_stats = self._consume_reporting_fetch_observability(
                    grain="account_daily",
                    account_id=account_id,
                    rows_mapped=len(daily_rows),
                )
                rows_downloaded += int(fetch_stats.get("rows_downloaded") or 0)
                rows_mapped += int(fetch_stats.get("rows_mapped") or 0)
                if fetch_stats.get("zero_row_marker") is not None:
                    zero_row_observability.append(fetch_stats)
                provider_ids_in_scope: list[str] = []
                for row in daily_rows:
                    provider_ids_in_scope.append(self._normalize_account_id(row.account_id))
                    tiktok_meta = row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics, dict) else None
                    if isinstance(tiktok_meta, dict):
                        candidates = tiktok_meta.get("provider_identity_candidates")
                        if isinstance(candidates, list):
                            for candidate in candidates:
                                normalized_candidate = self._normalize_account_id(candidate)
                                if normalized_candidate != "":
                                    provider_ids_in_scope.append(normalized_candidate)

                identity_resolution = resolve_tiktok_account_daily_persistence_identity(
                    attached_account_id=account_id,
                    provider_ids_in_scope=provider_ids_in_scope,
                )
                if identity_resolution.is_ambiguous or identity_resolution.canonical_persistence_customer_id is None:
                    ambiguity_payload = {
                        "account_id": account_id,
                        "canonical_persistence_customer_id": identity_resolution.canonical_persistence_customer_id,
                        "identity_source": identity_resolution.identity_source,
                        "provider_ids_seen": list(identity_resolution.provider_ids_seen),
                        "is_ambiguous": identity_resolution.is_ambiguous,
                        "ambiguity_reason": identity_resolution.ambiguity_reason,
                        "action": "blocked_account_daily_persistence",
                    }
                    account_daily_identity_warnings.append(ambiguity_payload)
                    raise TikTokAdsIntegrationError(
                        "TikTok account_daily persistence identity is ambiguous; refusing write to prevent non-deterministic account_daily rows.",
                        error_category="local_attachment_error",
                        advertiser_id=account_id,
                        provider_error_code="acct_daily_ambiguous",
                        provider_error_message=json.dumps(ambiguity_payload, ensure_ascii=False),
                        token_source=token_source,
                    )

                persistence_rows, duplicate_candidates = self._collapse_account_daily_rows_for_persistence(
                    rows=daily_rows,
                    canonical_persistence_customer_id=identity_resolution.canonical_persistence_customer_id,
                )
                if duplicate_candidates > 0:
                    account_daily_identity_warnings.append(
                        {
                            "account_id": account_id,
                            "canonical_persistence_customer_id": identity_resolution.canonical_persistence_customer_id,
                            "identity_source": identity_resolution.identity_source,
                            "provider_ids_seen": list(identity_resolution.provider_ids_seen),
                            "is_ambiguous": False,
                            "ambiguity_reason": None,
                            "action": "collapsed_duplicate_write_candidates",
                            "duplicate_candidates": int(duplicate_candidates),
                        }
                    )

                batch_payloads: list[dict] = [
                    {
                        "report_date": row.report_date,
                        "platform": "tiktok_ads",
                        "customer_id": identity_resolution.canonical_persistence_customer_id,
                        "client_id": int(client_id),
                        "spend": row.spend,
                        "impressions": row.impressions,
                        "clicks": row.clicks,
                        "conversions": row.conversions,
                        "conversion_value": row.conversion_value,
                        "extra_metrics": row.extra_metrics,
                    }
                    for row in persistence_rows
                ]
                if batch_payloads:
                    performance_reports_store.write_daily_reports_batch(batch_payloads)
                for row in persistence_rows:
                    rows_written += 1
                    totals["spend"] += row.spend
                    totals["impressions"] += row.impressions
                    totals["clicks"] += row.clicks
                    totals["conversions"] += row.conversions
                    totals["revenue"] += row.conversion_value
        elif resolved_grain == "campaign_daily":
            for account_id in account_ids:
                campaign_rows = self._fetch_campaign_daily_metrics(
                    account_id=account_id,
                    access_token=access_token,
                    start_date=range_start,
                    end_date=range_end,
                )
                fetch_stats = self._consume_reporting_fetch_observability(
                    grain="campaign_daily",
                    account_id=account_id,
                    rows_mapped=len(campaign_rows),
                )
                rows_downloaded += int(fetch_stats.get("rows_downloaded") or 0)
                rows_mapped += int(fetch_stats.get("rows_mapped") or 0)
                if fetch_stats.get("zero_row_marker") is not None:
                    zero_row_observability.append(fetch_stats)
                report_name_by_id = {row.campaign_id: row.campaign_name for row in campaign_rows if str(row.campaign_name or "").strip() != ""}
                campaign_metadata_by_id = self._resolve_and_persist_campaign_metadata_safe(
                    account_id=account_id,
                    access_token=access_token,
                    campaign_ids=[row.campaign_id for row in campaign_rows],
                    report_campaign_name_by_id=report_name_by_id,
                )
                enriched_campaign_rows: list[TikTokCampaignDailyMetric] = []
                for row in campaign_rows:
                    metadata = campaign_metadata_by_id.get(row.campaign_id, {})
                    resolved_campaign_name = str(metadata.get("campaign_name") or row.campaign_name or "").strip()
                    resolved_campaign_status = str(metadata.get("campaign_status") or "").strip()
                    enriched_campaign_rows.append(
                        TikTokCampaignDailyMetric(
                            report_date=row.report_date,
                            account_id=row.account_id,
                            campaign_id=row.campaign_id,
                            campaign_name=resolved_campaign_name,
                            spend=row.spend,
                            impressions=row.impressions,
                            clicks=row.clicks,
                            conversions=row.conversions,
                            conversion_value=row.conversion_value,
                            extra_metrics={
                                **row.extra_metrics,
                                "tiktok_ads": {
                                    **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                                    "campaign_name": resolved_campaign_name,
                                    "campaign_status": resolved_campaign_status or None,
                                },
                            },
                        )
                    )
                rows_written += self._upsert_campaign_rows(
                    enriched_campaign_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                    access_token=access_token,
                )
                for row in enriched_campaign_rows:
                    totals["spend"] += row.spend
                    totals["impressions"] += row.impressions
                    totals["clicks"] += row.clicks
                    totals["conversions"] += row.conversions
                    totals["revenue"] += row.conversion_value
        elif resolved_grain == "ad_group_daily":
            for account_id in account_ids:
                ad_group_rows = self._fetch_ad_group_daily_metrics(
                    account_id=account_id,
                    access_token=access_token,
                    start_date=range_start,
                    end_date=range_end,
                )
                fetch_stats = self._consume_reporting_fetch_observability(
                    grain="ad_group_daily",
                    account_id=account_id,
                    rows_mapped=len(ad_group_rows),
                )
                rows_downloaded += int(fetch_stats.get("rows_downloaded") or 0)
                rows_mapped += int(fetch_stats.get("rows_mapped") or 0)
                if fetch_stats.get("zero_row_marker") is not None:
                    zero_row_observability.append(fetch_stats)
                report_name_by_id = {row.campaign_id: row.campaign_name for row in ad_group_rows if str(row.campaign_id or "").strip() != "" and str(row.campaign_name or "").strip() != ""}
                report_ad_group_name_by_id = {row.ad_group_id: row.ad_group_name for row in ad_group_rows if str(row.ad_group_id or "").strip() != "" and str(row.ad_group_name or "").strip() != ""}
                ad_group_metadata_by_id = self._resolve_and_persist_ad_group_metadata_safe(
                    account_id=account_id,
                    access_token=access_token,
                    ad_group_ids=[row.ad_group_id for row in ad_group_rows],
                    report_ad_group_name_by_id=report_ad_group_name_by_id,
                )
                resolved_campaign_ids = {
                    str(row.campaign_id or "").strip()
                    for row in ad_group_rows
                    if str(row.campaign_id or "").strip() != ""
                }
                resolved_campaign_ids.update(
                    str((ad_group_metadata_by_id.get(row.ad_group_id) or {}).get("campaign_id") or "").strip()
                    for row in ad_group_rows
                    if str((ad_group_metadata_by_id.get(row.ad_group_id) or {}).get("campaign_id") or "").strip() != ""
                )
                campaign_metadata_by_id = self._resolve_and_persist_campaign_metadata_safe(
                    account_id=account_id,
                    access_token=access_token,
                    campaign_ids=sorted(resolved_campaign_ids),
                    report_campaign_name_by_id=report_name_by_id,
                )
                enriched_ad_group_rows: list[TikTokAdGroupDailyMetric] = []
                for row in ad_group_rows:
                    ad_group_metadata = ad_group_metadata_by_id.get(row.ad_group_id, {})
                    resolved_campaign_id = str(row.campaign_id or ad_group_metadata.get("campaign_id") or "").strip()
                    campaign_metadata = campaign_metadata_by_id.get(resolved_campaign_id, {})
                    resolved_campaign_name = str(
                        campaign_metadata.get("campaign_name")
                        or ad_group_metadata.get("campaign_name")
                        or row.campaign_name
                        or ""
                    ).strip()
                    resolved_campaign_status = str(campaign_metadata.get("campaign_status") or "").strip()
                    resolved_ad_group_name = str(row.ad_group_name or ad_group_metadata.get("ad_group_name") or "").strip()
                    resolved_ad_group_status = str(ad_group_metadata.get("ad_group_status") or "").strip()
                    enriched_ad_group_rows.append(
                        TikTokAdGroupDailyMetric(
                            report_date=row.report_date,
                            account_id=row.account_id,
                            ad_group_id=row.ad_group_id,
                            ad_group_name=resolved_ad_group_name,
                            adgroup_name=resolved_ad_group_name,
                            campaign_id=resolved_campaign_id,
                            campaign_name=resolved_campaign_name,
                            spend=row.spend,
                            impressions=row.impressions,
                            clicks=row.clicks,
                            conversions=row.conversions,
                            conversion_value=row.conversion_value,
                            extra_metrics={
                                **row.extra_metrics,
                                "tiktok_ads": {
                                    **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                                    "campaign_id": resolved_campaign_id or None,
                                    "campaign_name": resolved_campaign_name,
                                    "ad_group_name": resolved_ad_group_name or None,
                                    "ad_group_status": resolved_ad_group_status or None,
                                    "campaign_status": resolved_campaign_status or None,
                                },
                            },
                        )
                    )
                rows_written += self._upsert_ad_group_rows(
                    enriched_ad_group_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                    access_token=access_token,
                )
                for row in enriched_ad_group_rows:
                    totals["spend"] += row.spend
                    totals["impressions"] += row.impressions
                    totals["clicks"] += row.clicks
                    totals["conversions"] += row.conversions
                    totals["revenue"] += row.conversion_value
        else:
            for account_id in account_ids:
                ad_rows = self._fetch_ad_daily_metrics(
                    account_id=account_id,
                    access_token=access_token,
                    start_date=range_start,
                    end_date=range_end,
                )
                fetch_stats = self._consume_reporting_fetch_observability(
                    grain="ad_daily",
                    account_id=account_id,
                    rows_mapped=len(ad_rows),
                )
                rows_downloaded += int(fetch_stats.get("rows_downloaded") or 0)
                rows_mapped += int(fetch_stats.get("rows_mapped") or 0)
                if fetch_stats.get("zero_row_marker") is not None:
                    zero_row_observability.append(fetch_stats)
                report_name_by_id = {row.campaign_id: row.campaign_name for row in ad_rows if str(row.campaign_name or "").strip() != ""}
                campaign_metadata_by_id = self._resolve_and_persist_campaign_metadata_safe(
                    account_id=account_id,
                    access_token=access_token,
                    campaign_ids=[row.campaign_id for row in ad_rows],
                    report_campaign_name_by_id=report_name_by_id,
                )
                enriched_ad_rows: list[TikTokAdDailyMetric] = []
                for row in ad_rows:
                    metadata = campaign_metadata_by_id.get(row.campaign_id, {})
                    resolved_campaign_name = str(metadata.get("campaign_name") or row.campaign_name or "").strip()
                    resolved_campaign_status = str(metadata.get("campaign_status") or "").strip()
                    enriched_ad_rows.append(
                        TikTokAdDailyMetric(
                            report_date=row.report_date,
                            account_id=row.account_id,
                            ad_id=row.ad_id,
                            ad_name=row.ad_name,
                            ad_group_id=row.ad_group_id,
                            ad_group_name=row.ad_group_name,
                            campaign_id=row.campaign_id,
                            campaign_name=resolved_campaign_name,
                            spend=row.spend,
                            impressions=row.impressions,
                            clicks=row.clicks,
                            conversions=row.conversions,
                            conversion_value=row.conversion_value,
                            extra_metrics={
                                **row.extra_metrics,
                                "tiktok_ads": {
                                    **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                                    "campaign_name": resolved_campaign_name,
                                    "campaign_status": resolved_campaign_status or None,
                                },
                            },
                        )
                    )
                rows_written += self._upsert_ad_rows(
                    enriched_ad_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                )
                for row in enriched_ad_rows:
                    totals["spend"] += row.spend
                    totals["impressions"] += row.impressions
                    totals["clicks"] += row.clicks
                    totals["conversions"] += row.conversions
                    totals["revenue"] += row.conversion_value

        snapshot = {
            "client_id": int(client_id),
            "platform": "tiktok_ads",
            "spend": round(float(totals["spend"]), 2),
            "impressions": int(totals["impressions"]),
            "clicks": int(totals["clicks"]),
            "conversions": int(round(float(totals["conversions"]))),
            "revenue": round(float(totals["revenue"]), 2),
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "attempts": 1,
        }
        tiktok_snapshot_store.upsert_snapshot(payload=snapshot)

        return {
            "status": "success",
            "platform": "tiktok_ads",
            "grain": resolved_grain,
            "client_id": int(client_id),
            "date_start": range_start.isoformat(),
            "date_end": range_end.isoformat(),
            "accounts_processed": len(account_ids),
            "account_ids": account_ids,
            "provider_row_count": rows_downloaded,
            "rows_downloaded": rows_downloaded,
            "rows_mapped": rows_mapped,
            "rows_written": rows_written,
            "zero_row_observability": zero_row_observability,
            "account_daily_identity_warnings": account_daily_identity_warnings,
            "token_source": token_source,
            **snapshot,
        }

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return tiktok_snapshot_store.get_snapshot(client_id=client_id)


tiktok_ads_service = TikTokAdsService()
