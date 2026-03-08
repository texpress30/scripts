from __future__ import annotations

import base64
import json
import secrets
import time
from datetime import datetime, timezone
from urllib import error, parse, request

from app.core.config import load_settings
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
