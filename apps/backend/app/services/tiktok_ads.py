from __future__ import annotations

import base64
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

    def _is_test_mode(self) -> bool:
        settings = load_settings()
        return settings.app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise TikTokAdsIntegrationError("psycopg is required for campaign/ad_group daily persistence")
        return psycopg.connect(settings.database_url)

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
                metrics=("spend", "impressions", "clicks", "conversion", "conversion_value", "total_purchase_value"),
            )
        if grain == "ad_group_daily":
            return TikTokReportingSchema(
                data_level="AUCTION_ADGROUP",
                dimensions=("stat_time_day", "adgroup_id"),
                metrics=("spend", "impressions", "clicks", "conversion", "conversion_value", "total_purchase_value"),
            )
        return TikTokReportingSchema(
            data_level="AUCTION_AD",
            dimensions=("stat_time_day", "ad_id"),
            metrics=("spend", "impressions", "clicks", "conversion", "conversion_value", "total_purchase_value"),
        )

    def _report_integrated_endpoint(self, *, query: str | None = None) -> str:
        settings = load_settings()
        base = f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/"
        if query:
            return f"{base}?{query}"
        return base

    def _report_integrated_get(
        self,
        *,
        account_id: str,
        access_token: str,
        report_type: str,
        data_level: str,
        dimensions: list[str],
        metrics: list[str],
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict[str, object]:
        query = parse.urlencode(
            {
                "advertiser_id": account_id,
                "report_type": report_type,
                "data_level": data_level,
                "dimensions": json.dumps(dimensions, separators=(",", ":")),
                "metrics": json.dumps(metrics, separators=(",", ":")),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "page": page,
                "page_size": page_size,
            }
        )
        return self._http_json(
            method="GET",
            url=self._report_integrated_endpoint(query=query),
            headers={"Access-Token": access_token},
        )

    def _fetch_account_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokDailyMetric]:
        schema = self._report_schema_for_grain("account_daily")
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type="BASIC",
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
            return []

        rows: list[TikTokDailyMetric] = []
        for item in rows_raw:
            if not isinstance(item, dict):
                continue
            dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
            raw_day = str(dimensions.get("stat_time_day") or "").strip()
            if raw_day == "":
                continue
            try:
                report_day = date.fromisoformat(raw_day)
            except ValueError:
                continue

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
                            "source": "report.integrated.get",
                            "grain": "account_daily",
                        }
                    },
                )
            )

        return rows

    def _fetch_campaign_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokCampaignDailyMetric]:
        schema = self._report_schema_for_grain("campaign_daily")
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type="BASIC",
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
            return []

        rows: list[TikTokCampaignDailyMetric] = []
        for item in rows_raw:
            if not isinstance(item, dict):
                continue
            dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}

            raw_day = str(dimensions.get("stat_time_day") or "").strip()
            campaign_id = str(dimensions.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or item.get("campaign_name") or "").strip()
            if raw_day == "" or campaign_id == "":
                continue
            try:
                report_day = date.fromisoformat(raw_day)
            except ValueError:
                continue

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

        return rows

    def _fetch_ad_group_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokAdGroupDailyMetric]:
        schema = self._report_schema_for_grain("ad_group_daily")
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type="BASIC",
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
            return []

        rows: list[TikTokAdGroupDailyMetric] = []
        for item in rows_raw:
            if not isinstance(item, dict):
                continue
            dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}

            raw_day = str(dimensions.get("stat_time_day") or "").strip()
            ad_group_id = str(dimensions.get("adgroup_id") or item.get("adgroup_id") or "").strip()
            ad_group_name = str(dimensions.get("adgroup_name") or item.get("adgroup_name") or "").strip()
            campaign_id = str(dimensions.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or item.get("campaign_name") or "").strip()
            if raw_day == "" or ad_group_id == "":
                continue
            try:
                report_day = date.fromisoformat(raw_day)
            except ValueError:
                continue

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
                            "ad_group_name": ad_group_name,
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "source": "report.integrated.get",
                            "grain": "ad_group_daily",
                        }
                    },
                )
            )

        return rows

    def _fetch_ad_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokAdDailyMetric]:
        schema = self._report_schema_for_grain("ad_daily")
        raw = self._report_integrated_get(
            account_id=account_id,
            access_token=access_token,
            report_type="BASIC",
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
            return []

        rows: list[TikTokAdDailyMetric] = []
        for item in rows_raw:
            if not isinstance(item, dict):
                continue
            dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}

            raw_day = str(dimensions.get("stat_time_day") or "").strip()
            ad_id = str(dimensions.get("ad_id") or item.get("ad_id") or "").strip()
            ad_name = str(dimensions.get("ad_name") or item.get("ad_name") or "").strip()
            ad_group_id = str(dimensions.get("adgroup_id") or item.get("adgroup_id") or "").strip()
            ad_group_name = str(dimensions.get("adgroup_name") or item.get("adgroup_name") or "").strip()
            campaign_id = str(dimensions.get("campaign_id") or item.get("campaign_id") or "").strip()
            campaign_name = str(dimensions.get("campaign_name") or item.get("campaign_name") or "").strip()
            if raw_day == "" or ad_id == "":
                continue
            try:
                report_day = date.fromisoformat(raw_day)
            except ValueError:
                continue

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

        return rows

    def _upsert_ad_group_rows(self, rows: list[TikTokAdGroupDailyMetric], *, source_window_start: date, source_window_end: date) -> int:
        if len(rows) == 0:
            return 0

        if self._is_test_mode():
            for row in rows:
                key = ("tiktok_ads", row.account_id, row.ad_group_id, row.report_date.isoformat())
                self._memory_ad_group_rows[key] = {
                    "platform": "tiktok_ads",
                    "account_id": row.account_id,
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
                "ad_group_id": row.ad_group_id,
                "campaign_id": row.campaign_id or None,
                "report_date": row.report_date,
                "spend": row.spend,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "conversions": row.conversions,
                "conversion_value": row.conversion_value,
                "extra_metrics": row.extra_metrics,
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            }
            for row in rows
        ]
        with self._connect() as conn:
            written = int(upsert_ad_group_performance_reports(conn, payload_rows) or 0)
            conn.commit()
            return written

    def _upsert_campaign_rows(self, rows: list[TikTokCampaignDailyMetric], *, source_window_start: date, source_window_end: date) -> int:
        if len(rows) == 0:
            return 0

        if self._is_test_mode():
            for row in rows:
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
                    "extra_metrics": row.extra_metrics,
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
                    **row.extra_metrics,
                    "tiktok_ads": {
                        **(row.extra_metrics.get("tiktok_ads") if isinstance(row.extra_metrics.get("tiktok_ads"), dict) else {}),
                        "campaign_name": row.campaign_name,
                    },
                },
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            }
            for row in rows
        ]
        with self._connect() as conn:
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
                for row in daily_rows:
                    performance_reports_store.write_daily_report(
                        report_date=row.report_date,
                        platform="tiktok_ads",
                        customer_id=row.account_id,
                        client_id=int(client_id),
                        spend=row.spend,
                        impressions=row.impressions,
                        clicks=row.clicks,
                        conversions=row.conversions,
                        conversion_value=row.conversion_value,
                        extra_metrics=row.extra_metrics,
                    )
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
                rows_written += self._upsert_campaign_rows(
                    campaign_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                )
                for row in campaign_rows:
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
                rows_written += self._upsert_ad_group_rows(
                    ad_group_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                )
                for row in ad_group_rows:
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
                rows_written += self._upsert_ad_rows(
                    ad_rows,
                    source_window_start=range_start,
                    source_window_end=range_end,
                )
                for row in ad_rows:
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
            "rows_written": rows_written,
            "token_source": token_source,
            **snapshot,
        }

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return tiktok_snapshot_store.get_snapshot(client_id=client_id)


tiktok_ads_service = TikTokAdsService()
