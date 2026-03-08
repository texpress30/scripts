from __future__ import annotations

import base64
import json
import secrets
import time
from datetime import datetime, timezone
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.integration_secrets_store import integration_secrets_store
from app.services.performance_reports import performance_reports_store
from app.services.tiktok_store import tiktok_snapshot_store


class TikTokAdsIntegrationError(RuntimeError):
    pass


class TikTokAdsService:
    _oauth_state_cache: set[str]

    def __init__(self) -> None:
        self._oauth_state_cache = set()

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
            with request.urlopen(req, timeout=20) as response:  # noqa: S310
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
        return integration_secrets_store.get_secret(provider="tiktok_ads", secret_key=key)

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
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")
        if not self._oauth_configured():
            raise TikTokAdsIntegrationError("TikTok OAuth is not configured. Set TIKTOK_APP_ID, TIKTOK_APP_SECRET, and TIKTOK_REDIRECT_URI.")

        state = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8").rstrip("=")
        self._oauth_state_cache.add(state)
        params = {
            "client_key": settings.tiktok_app_id,
            "redirect_uri": settings.tiktok_redirect_uri,
            "response_type": "code",
            "scope": "user.info.basic,advertiser.info.basic",
            "state": state,
        }
        return {
            "authorize_url": f"https://www.tiktok.com/v2/auth/authorize/?{parse.urlencode(params)}",
            "state": state,
        }

    def exchange_oauth_code(self, *, code: str, state: str) -> dict[str, object]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")
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
        settings = load_settings()
        oauth_configured = self._oauth_configured()

        if not settings.ff_tiktok_integration:
            return {
                "provider": "tiktok_ads",
                "status": "disabled",
                "message": "TikTok integration is disabled by feature flag.",
                "token_source": "missing",
                "token_updated_at": None,
                "token_expires_at": None,
                "oauth_configured": oauth_configured,
                "has_usable_token": False,
            }

        token, token_source, token_updated_at = self._access_token_with_source()
        token_expires_at = self._token_expires_at()
        has_usable_token = token != ""

        if not oauth_configured:
            return {
                "provider": "tiktok_ads",
                "status": "pending",
                "message": "TikTok OAuth configuration is incomplete.",
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
                "message": "TikTok OAuth token is available.",
                "token_source": token_source,
                "token_updated_at": token_updated_at,
                "token_expires_at": token_expires_at,
                "oauth_configured": True,
                "has_usable_token": True,
            }

        return {
            "provider": "tiktok_ads",
            "status": "pending",
            "message": "TikTok OAuth is configured but no usable token is stored yet.",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "token_expires_at": token_expires_at,
            "oauth_configured": True,
            "has_usable_token": False,
        }


    def _require_access_token(self) -> tuple[str, str, str | None]:
        token, token_source, token_updated_at = self._access_token_with_source()
        if token == "":
            raise TikTokAdsIntegrationError("TikTok OAuth token missing. Complete OAuth connect flow before importing accounts.")
        return token, token_source, token_updated_at

    def _extract_tiktok_api_error(self, payload: dict[str, object], *, operation: str) -> None:
        code = payload.get("code")
        if code in (None, 0, "0"):
            return
        message = str(payload.get("message") or payload.get("msg") or "unknown error").strip()
        raise TikTokAdsIntegrationError(f"TikTok API error during {operation}: {message}")

    def _list_advertiser_accounts_page(self, *, access_token: str, page: int, page_size: int) -> tuple[list[dict[str, object]], bool]:
        settings = load_settings()
        query = parse.urlencode(
            {
                "access_token": access_token,
                "page": int(page),
                "page_size": int(page_size),
            }
        )
        payload = self._http_json(
            method="GET",
            url=f"{settings.tiktok_api_base_url.rstrip('/')}/open_api/{settings.tiktok_api_version.strip('/')}/oauth2/advertiser/get/?{query}",
        )
        self._extract_tiktok_api_error(payload, operation="advertiser list")

        container = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if not isinstance(container, dict):
            return [], False

        raw_items = container.get("list") if isinstance(container.get("list"), list) else []
        items = [item for item in raw_items if isinstance(item, dict)]

        page_info = container.get("page_info") if isinstance(container.get("page_info"), dict) else {}
        if isinstance(page_info, dict) and "total_page" in page_info and isinstance(page_info.get("total_page"), (int, float)):
            has_more = int(page) < int(page_info.get("total_page") or 0)
        else:
            has_more = len(items) >= int(page_size)

        return items, has_more

    def list_accessible_advertiser_accounts(self) -> tuple[list[dict[str, object]], str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        access_token, token_source, _ = self._require_access_token()

        page = 1
        page_size = 100
        collected: list[dict[str, object]] = []
        while True:
            items, has_more = self._list_advertiser_accounts_page(access_token=access_token, page=page, page_size=page_size)
            collected.extend(items)
            if not has_more:
                break
            page += 1
            if page > 200:
                raise TikTokAdsIntegrationError("TikTok advertiser pagination exceeded safety limit")

        normalized: list[dict[str, object]] = []
        for item in collected:
            advertiser_id = str(item.get("advertiser_id") or item.get("id") or "").strip()
            if advertiser_id == "":
                continue
            normalized.append(
                {
                    "account_id": advertiser_id,
                    "name": str(item.get("name") or item.get("advertiser_name") or advertiser_id),
                    "status": str(item.get("status") or "").strip() or None,
                    "currency_code": str(item.get("currency") or item.get("currency_code") or "").strip().upper() or None,
                    "account_timezone": str(item.get("timezone") or item.get("time_zone") or "").strip() or None,
                    "metadata": {
                        "advertiser_id": advertiser_id,
                        "business_center_id": item.get("business_center_id"),
                    },
                }
            )

        return normalized, token_source

    def import_advertiser_accounts(self) -> dict[str, object]:
        accounts, token_source = self.list_accessible_advertiser_accounts()
        existing_accounts = {
            str(item.get("id") or item.get("account_id") or ""): item
            for item in client_registry_service.list_platform_accounts(platform="tiktok_ads")
            if str(item.get("id") or item.get("account_id") or "") != ""
        }

        upsert_payload = [{"id": item["account_id"], "name": item["name"]} for item in accounts]
        client_registry_service.upsert_platform_accounts(platform="tiktok_ads", accounts=upsert_payload)

        imported = 0
        updated = 0
        unchanged = 0
        for account in accounts:
            account_id = str(account["account_id"])
            previous = existing_accounts.get(account_id)
            prev_name = str((previous or {}).get("name") or "")
            prev_status = str((previous or {}).get("status") or "")
            prev_currency = str((previous or {}).get("currency") or (previous or {}).get("currency_code") or "").upper()
            prev_timezone = str((previous or {}).get("timezone") or (previous or {}).get("account_timezone") or "")

            next_status = str(account.get("status") or "")
            next_currency = str(account.get("currency_code") or "")
            next_timezone = str(account.get("account_timezone") or "")

            if previous is None:
                imported += 1
            elif prev_name == str(account["name"]) and prev_status == next_status and prev_currency == next_currency and prev_timezone == next_timezone:
                unchanged += 1
            else:
                updated += 1

            client_registry_service.update_platform_account_operational_metadata(
                platform="tiktok_ads",
                account_id=account_id,
                status=next_status if next_status != "" else None,
                currency_code=next_currency if next_currency != "" else None,
                account_timezone=next_timezone if next_timezone != "" else None,
            )

        return {
            "status": "ok",
            "message": "TikTok advertiser accounts imported into platform registry.",
            "platform": "tiktok_ads",
            "token_source": token_source,
            "accounts_discovered": len(accounts),
            "imported": imported,
            "updated": updated,
            "unchanged": unchanged,
        }

    def _provider_snapshot(self, *, client_id: int, attempt: int, forced_failures: int) -> dict[str, float | int | str]:
        if attempt <= forced_failures:
            raise RuntimeError("Transient TikTok provider timeout")

        spend = float(70 + client_id * 11)
        impressions = 3200 + client_id * 90
        clicks = 140 + client_id * 6
        conversions = 3 + client_id
        revenue = round(spend * 2.4, 2)
        synced_at = datetime.now(timezone.utc).isoformat()

        return {
            "client_id": client_id,
            "platform": "tiktok_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": synced_at,
            "status": "success",
            "attempts": attempt,
            "sync_mode": "stub",
            "message": "TikTok sync endpoint is still stubbed for metrics import in this phase.",
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.")

        retry_attempts = max(1, settings.tiktok_sync_retry_attempts)
        backoff_seconds = max(0, settings.tiktok_sync_backoff_ms) / 1000.0
        forced_failures = max(0, settings.tiktok_sync_force_transient_failures)

        last_error: Exception | None = None
        for attempt in range(1, retry_attempts + 1):
            try:
                snapshot = self._provider_snapshot(
                    client_id=client_id,
                    attempt=attempt,
                    forced_failures=forced_failures,
                )
                tiktok_snapshot_store.upsert_snapshot(payload=snapshot)
                performance_reports_store.write_daily_report(
                    report_date=datetime.now(timezone.utc).date(),
                    platform="tiktok_ads",
                    customer_id=f"client-{client_id}",
                    client_id=client_id,
                    spend=float(snapshot["spend"]),
                    impressions=int(snapshot["impressions"]),
                    clicks=int(snapshot["clicks"]),
                    conversions=float(snapshot["conversions"]),
                    conversion_value=float(snapshot["revenue"]),
                    extra_metrics={
                        "tiktok_ads": {
                            "result": float(snapshot["conversions"]),
                            "gmv": float(snapshot["revenue"]),
                            "click_through_rate_clicks": int(snapshot["clicks"]),
                        }
                    },
                )
                return snapshot
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retry_attempts and backoff_seconds > 0:
                    time.sleep(backoff_seconds * attempt)

        raise TikTokAdsIntegrationError(
            f"TikTok provider transient failure after {retry_attempts} attempts"
        ) from last_error

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return tiktok_snapshot_store.get_snapshot(client_id=client_id)


tiktok_ads_service = TikTokAdsService()
