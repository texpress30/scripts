from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone
from urllib import parse, request

from app.core.config import load_settings
from app.services.google_store import google_snapshot_store


class GoogleAdsIntegrationError(RuntimeError):
    pass


class GoogleAdsService:
    _oauth_state_cache: set[str]
    _runtime_refresh_token: str | None

    def __init__(self) -> None:
        self._oauth_state_cache = set()
        self._runtime_refresh_token = None

    def _is_production_mode(self) -> bool:
        settings = load_settings()
        return settings.google_ads_mode == "production"

    def _google_api_version(self) -> str:
        settings = load_settings()
        return settings.google_ads_api_version.strip() or "v18"

    def _normalize_customer_id(self, customer_id: str) -> str:
        return customer_id.replace("-", "").strip()

    def _http_json(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object] | list[dict[str, object]]:
        body = None
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
                if raw.strip() == "":
                    return {}
                return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            raise GoogleAdsIntegrationError(f"Google Ads HTTP request failed: {exc}") from exc

    def _require_production_credentials(self) -> None:
        settings = load_settings()
        missing: list[str] = []
        if settings.google_ads_developer_token.strip() == "":
            missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
        if settings.google_ads_client_id.strip() == "":
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if settings.google_ads_client_secret.strip() == "":
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if settings.google_ads_redirect_uri.strip() == "":
            missing.append("GOOGLE_ADS_REDIRECT_URI")
        if missing:
            raise GoogleAdsIntegrationError(f"Google Ads production mode missing env vars: {', '.join(missing)}")

    def _refresh_token(self) -> str:
        settings = load_settings()
        token = self._runtime_refresh_token or settings.google_ads_refresh_token
        token = token.strip()
        if token == "":
            raise GoogleAdsIntegrationError(
                "Google refresh token missing. Complete OAuth connect flow and set GOOGLE_ADS_REFRESH_TOKEN in Railway."
            )
        return token

    def _access_token_from_refresh(self) -> str:
        settings = load_settings()
        token_payload = self._http_json(
            method="POST",
            url="https://oauth2.googleapis.com/token",
            payload={
                "client_id": settings.google_ads_client_id,
                "client_secret": settings.google_ads_client_secret,
                "refresh_token": self._refresh_token(),
                "grant_type": "refresh_token",
            },
        )
        if not isinstance(token_payload, dict) or "access_token" not in token_payload:
            raise GoogleAdsIntegrationError("Failed to obtain Google OAuth access token from refresh token")
        return str(token_payload["access_token"])

    def integration_status(self) -> dict[str, str]:
        settings = load_settings()

        if self._is_production_mode():
            connected = bool((self._runtime_refresh_token or settings.google_ads_refresh_token).strip())
            return {
                "provider": "google_ads",
                "status": "connected" if connected else "pending",
                "message": "Google Ads production mode is enabled." if connected else "Google Ads production mode awaiting OAuth token.",
                "mode": "production",
            }

        token = settings.google_ads_token.strip()
        if not token or token.startswith("your_"):
            return {
                "provider": "google_ads",
                "status": "pending",
                "message": "Google Ads token is configured as placeholder.",
                "mode": "mock",
            }
        return {
            "provider": "google_ads",
            "status": "connected",
            "message": "Google Ads token is available.",
            "mode": "mock",
        }

    def build_oauth_authorize_url(self) -> dict[str, str]:
        self._require_production_credentials()
        settings = load_settings()
        state = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8").rstrip("=")
        self._oauth_state_cache.add(state)
        params = {
            "client_id": settings.google_ads_client_id,
            "redirect_uri": settings.google_ads_redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": "https://www.googleapis.com/auth/adwords",
            "state": state,
        }
        return {
            "authorize_url": f"https://accounts.google.com/o/oauth2/v2/auth?{parse.urlencode(params)}",
            "state": state,
        }

    def exchange_oauth_code(self, *, code: str, state: str) -> dict[str, object]:
        self._require_production_credentials()
        if state not in self._oauth_state_cache:
            raise GoogleAdsIntegrationError("Invalid OAuth state for Google connect callback")
        self._oauth_state_cache.discard(state)

        settings = load_settings()
        token_payload = self._http_json(
            method="POST",
            url="https://oauth2.googleapis.com/token",
            payload={
                "client_id": settings.google_ads_client_id,
                "client_secret": settings.google_ads_client_secret,
                "redirect_uri": settings.google_ads_redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
            },
        )
        if not isinstance(token_payload, dict) or "refresh_token" not in token_payload:
            raise GoogleAdsIntegrationError("Google OAuth callback did not return a refresh token. Re-run consent with prompt=consent.")

        refresh_token = str(token_payload["refresh_token"])
        self._runtime_refresh_token = refresh_token

        accessible_customers = self.list_accessible_customers()
        return {
            "status": "connected",
            "refresh_token": refresh_token,
            "accessible_customers": accessible_customers,
            "persist_instruction": "Set GOOGLE_ADS_REFRESH_TOKEN in Railway using refresh_token from this response.",
        }

    def list_accessible_customers(self) -> list[str]:
        if not self._is_production_mode():
            return []
        settings = load_settings()
        self._require_production_credentials()
        access_token = self._access_token_from_refresh()
        api_version = self._google_api_version()
        payload = self._http_json(
            method="POST",
            url=f"https://googleads.googleapis.com/{api_version}/customers:listAccessibleCustomers",
            payload={},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_ads_developer_token,
            },
        )
        if not isinstance(payload, dict):
            raise GoogleAdsIntegrationError("Invalid response received from Google listAccessibleCustomers")
        resource_names = payload.get("resourceNames", [])
        if not isinstance(resource_names, list):
            return []
        return [str(name).split("/")[-1] for name in resource_names]

    def get_recommended_customer_id_for_client(self, client_id: int) -> str | None:
        settings = load_settings()
        configured = tuple(item.strip() for item in settings.google_ads_customer_ids_csv.split(",") if item.strip())
        if client_id <= 0:
            return None
        if client_id <= len(configured):
            return self._normalize_customer_id(configured[client_id - 1])
        return None

    def _fetch_production_metrics(self, *, customer_id: str) -> dict[str, float | int | str]:
        settings = load_settings()
        access_token = self._access_token_from_refresh()
        api_version = self._google_api_version()
        normalized_customer_id = self._normalize_customer_id(customer_id)
        query = (
            "SELECT metrics.cost_micros, metrics.impressions, metrics.clicks, "
            "metrics.conversions, metrics.conversions_value "
            "FROM customer WHERE segments.date DURING LAST_30_DAYS"
        )

        response_payload = self._http_json(
            method="POST",
            url=f"https://googleads.googleapis.com/{api_version}/customers/{normalized_customer_id}/googleAds:searchStream",
            payload={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_ads_developer_token,
                "login-customer-id": self._normalize_customer_id(settings.google_ads_manager_customer_id),
            },
        )

        if not isinstance(response_payload, list):
            raise GoogleAdsIntegrationError("Invalid Google Ads searchStream response")

        total_cost_micros = 0.0
        impressions = 0
        clicks = 0
        conversions = 0.0
        revenue = 0.0

        for chunk in response_payload:
            if not isinstance(chunk, dict):
                continue
            results = chunk.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                metrics = result.get("metrics", {})
                if not isinstance(metrics, dict):
                    continue
                total_cost_micros += float(metrics.get("costMicros", 0.0))
                impressions += int(metrics.get("impressions", 0))
                clicks += int(metrics.get("clicks", 0))
                conversions += float(metrics.get("conversions", 0.0))
                revenue += float(metrics.get("conversionsValue", 0.0))

        spend = round(total_cost_micros / 1_000_000.0, 2)
        return {
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": int(round(conversions)),
            "revenue": round(revenue, 2),
            "google_customer_id": normalized_customer_id,
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        if self._is_production_mode():
            customer_id = self.get_recommended_customer_id_for_client(client_id)
            if not customer_id:
                raise GoogleAdsIntegrationError(
                    "No Google customer mapping for this client. Set GOOGLE_ADS_CUSTOMER_IDS_CSV ordered by local client ids or import accounts first."
                )
            real_metrics = self._fetch_production_metrics(customer_id=customer_id)
            snapshot = {
                "client_id": client_id,
                "platform": "google_ads",
                "spend": round(float(real_metrics["spend"]), 2),
                "impressions": int(real_metrics["impressions"]),
                "clicks": int(real_metrics["clicks"]),
                "conversions": int(real_metrics["conversions"]),
                "revenue": round(float(real_metrics["revenue"]), 2),
                "google_customer_id": str(real_metrics["google_customer_id"]),
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            google_snapshot_store.upsert_snapshot(payload=snapshot)
            return snapshot

        settings = load_settings()
        token = settings.google_ads_token.strip()
        if not token or token.startswith("your_"):
            raise GoogleAdsIntegrationError("Google Ads token is missing or placeholder.")

        spend = float(100 + client_id * 17)
        impressions = 5000 + client_id * 110
        clicks = 200 + client_id * 9
        conversions = 5 + client_id
        revenue = round(spend * 3.2, 2)

        snapshot = {
            "client_id": client_id,
            "platform": "google_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        google_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return google_snapshot_store.get_snapshot(client_id=client_id)


google_ads_service = GoogleAdsService()
