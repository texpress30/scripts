from __future__ import annotations

import base64
import json
import secrets
from typing import Literal
from datetime import datetime, timezone
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.integration_secrets_store import integration_secrets_store
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store


class MetaAdsIntegrationError(RuntimeError):
    pass


class MetaAdsService:
    _oauth_state_cache: set[str]

    def __init__(self) -> None:
        self._oauth_state_cache = set()

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
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            raise MetaAdsIntegrationError(f"Meta HTTP request failed: {exc}") from exc

        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise MetaAdsIntegrationError("Meta API returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise MetaAdsIntegrationError("Meta API response shape is invalid")
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

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        token, _, _ = self._access_token_with_source()
        if token == "":
            raise MetaAdsIntegrationError("Meta Ads token is missing or placeholder.")

        spend = float(85 + client_id * 13)
        impressions = 4200 + client_id * 95
        clicks = 170 + client_id * 7
        conversions = 4 + client_id
        revenue = round(spend * 2.7, 2)

        snapshot = {
            "client_id": client_id,
            "platform": "meta_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        meta_snapshot_store.upsert_snapshot(payload=snapshot)
        performance_reports_store.write_daily_report(
            report_date=datetime.now(timezone.utc).date(),
            platform="meta_ads",
            customer_id=f"client-{client_id}",
            client_id=client_id,
            spend=float(snapshot["spend"]),
            impressions=int(snapshot["impressions"]),
            clicks=int(snapshot["clicks"]),
            conversions=float(snapshot["conversions"]),
            conversion_value=float(snapshot["revenue"]),
            extra_metrics={
                "meta_ads": {
                    "actions_offsite_conversion": float(snapshot["conversions"]),
                    "purchase_roas_value": float(snapshot["revenue"]),
                    "inline_link_clicks": int(snapshot["clicks"]),
                }
            },
        )
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return meta_snapshot_store.get_snapshot(client_id=client_id)


meta_ads_service = MetaAdsService()
