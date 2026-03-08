from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
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


class TikTokAdsIntegrationError(RuntimeError):
    pass


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
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            raise TikTokAdsIntegrationError(f"TikTok HTTP request failed: {exc}") from exc

        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise TikTokAdsIntegrationError("TikTok API returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise TikTokAdsIntegrationError("TikTok API response shape is invalid")
        return parsed

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

        return {
            "status": "ok",
            "provider": "tiktok_ads",
            "token_source": token_source,
            "accounts_discovered": 0,
            "imported": 0,
            "updated": 0,
            "unchanged": 0,
            "message": "TikTok account import is enabled and awaiting account discovery implementation.",
        }

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

    def _fetch_account_daily_metrics(self, *, account_id: str, access_token: str, start_date: date, end_date: date) -> list[TikTokDailyMetric]:
        settings = load_settings()
        payload = {
            "advertiser_id": account_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_ADVERTISER",
            "dimensions": ["stat_time_day"],
            "metrics": [
                "spend",
                "impressions",
                "clicks",
                "conversion",
                "conversion_value",
                "total_purchase_value",
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": 1,
            "page_size": 1000,
        }
        raw = self._http_json(
            method="POST",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/",
            headers={"Access-Token": access_token},
            payload=payload,
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
        settings = load_settings()
        payload = {
            "advertiser_id": account_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_CAMPAIGN",
            "dimensions": ["stat_time_day", "campaign_id", "campaign_name"],
            "metrics": [
                "spend",
                "impressions",
                "clicks",
                "conversion",
                "conversion_value",
                "total_purchase_value",
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": 1,
            "page_size": 1000,
        }
        raw = self._http_json(
            method="POST",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/",
            headers={"Access-Token": access_token},
            payload=payload,
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
        settings = load_settings()
        payload = {
            "advertiser_id": account_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_ADGROUP",
            "dimensions": ["stat_time_day", "adgroup_id", "adgroup_name", "campaign_id", "campaign_name"],
            "metrics": [
                "spend",
                "impressions",
                "clicks",
                "conversion",
                "conversion_value",
                "total_purchase_value",
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": 1,
            "page_size": 1000,
        }
        raw = self._http_json(
            method="POST",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/",
            headers={"Access-Token": access_token},
            payload=payload,
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
        settings = load_settings()
        payload = {
            "advertiser_id": account_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_AD",
            "dimensions": ["stat_time_day", "ad_id", "ad_name", "adgroup_id", "adgroup_name", "campaign_id", "campaign_name"],
            "metrics": [
                "spend",
                "impressions",
                "clicks",
                "conversion",
                "conversion_value",
                "total_purchase_value",
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": 1,
            "page_size": 1000,
        }
        raw = self._http_json(
            method="POST",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/report/integrated/get/",
            headers={"Access-Token": access_token},
            payload=payload,
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

    def sync_client(
        self,
        client_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        grain: TikTokSyncGrain = "account_daily",
    ) -> dict[str, object]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.")

        resolved_grain = str(grain).strip().lower()
        if resolved_grain not in {"account_daily", "campaign_daily", "ad_group_daily", "ad_daily"}:
            raise TikTokAdsIntegrationError(f"grain invalid: {resolved_grain}")

        range_start, range_end = self._resolve_sync_window(start_date=start_date, end_date=end_date)

        access_token, token_source, _ = self._access_token_with_source()
        if access_token == "":
            raise TikTokAdsIntegrationError("TikTok sync requires a usable OAuth token. Connect TikTok first.")

        attached_accounts = client_registry_service.list_client_platform_accounts(platform="tiktok_ads", client_id=int(client_id))
        account_ids = [str(item.get("id") or "").strip() for item in attached_accounts if isinstance(item, dict)]
        account_ids = [account_id for account_id in account_ids if account_id != ""]

        if len(account_ids) == 0:
            return {
                "status": "no_accounts",
                "platform": "tiktok_ads",
                "grain": resolved_grain,
                "client_id": int(client_id),
                "date_start": range_start.isoformat(),
                "date_end": range_end.isoformat(),
                "accounts_processed": 0,
                "rows_written": 0,
                "message": "No TikTok advertiser accounts are attached to this client.",
            }

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
