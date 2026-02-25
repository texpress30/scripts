from __future__ import annotations

import base64
import json
import logging
import re
import secrets
from datetime import datetime, timezone
from urllib import error, parse, request

from app.core.config import load_settings
from app.services.google_store import google_snapshot_store

logger = logging.getLogger(__name__)


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
        raw = settings.google_ads_api_version.strip().lower() or "v18"
        if raw.startswith("v"):
            return raw
        if raw.isdigit():
            return f"v{raw}"
        return raw

    def _candidate_api_versions(self) -> list[str]:
        # Keep discovery/metrics on one configured version to avoid mixed-version debug noise.
        return [self._google_api_version()]

    def _normalize_customer_id(self, customer_id: str) -> str:
        return customer_id.replace("-", "").strip()

    def _is_valid_customer_id(self, customer_id: str) -> bool:
        normalized = self._normalize_customer_id(customer_id)
        return bool(re.fullmatch(r"\d{10}", normalized))

    def _required_manager_customer_id(self) -> str:
        settings = load_settings()
        manager_customer_id = self._normalize_customer_id(settings.google_ads_manager_customer_id)
        if manager_customer_id == "":
            raise GoogleAdsIntegrationError("GOOGLE_ADS_MANAGER_CUSTOMER_ID is required for Google Ads production requests")
        if not self._is_valid_customer_id(manager_customer_id):
            raise GoogleAdsIntegrationError("GOOGLE_ADS_MANAGER_CUSTOMER_ID must be 10 digits (no dashes)")
        return manager_customer_id

    def _build_google_ads_url(self, api_version: str, path: str) -> str:
        normalized_version = api_version.strip().strip("/")
        normalized_path = path.strip().lstrip("/")
        return f"https://googleads.googleapis.com/{normalized_version}/{normalized_path}"

    def _extract_google_ads_error_details(
        self,
        *,
        response_body: str,
        response_headers: object,
    ) -> tuple[str | None, list[object]]:
        request_id: str | None = None
        if hasattr(response_headers, "get"):
            try:
                request_id = response_headers.get("request-id") or response_headers.get("x-request-id")
            except Exception:  # noqa: BLE001
                request_id = None

        failure_details: list[object] = []
        try:
            payload = json.loads(response_body)
            error_obj = payload.get("error", {}) if isinstance(payload, dict) else {}
            if isinstance(error_obj, dict):
                details = error_obj.get("details", [])
                if isinstance(details, list):
                    failure_details = details
        except Exception:  # noqa: BLE001
            failure_details = []

        return request_id, failure_details

    def _list_accessible_customers_via_service(self, *, access_token: str, manager_customer_id: str) -> list[str]:
        settings = load_settings()
        api_version = self._google_api_version()
        payload = self._http_json(
            method="GET",
            url=self._build_google_ads_url(api_version, "customers:listAccessibleCustomers"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_ads_developer_token,
                "login-customer-id": manager_customer_id,
            },
        )
        if not isinstance(payload, dict):
            raise GoogleAdsIntegrationError("Invalid response received from Google customers:listAccessibleCustomers")

        resource_names = payload.get("resourceNames", [])
        if not isinstance(resource_names, list):
            return []

        discovered: list[str] = []
        for resource_name in resource_names:
            value = str(resource_name).strip()
            if value.startswith("customers/"):
                value = value.split("/", 1)[1]
            value = self._normalize_customer_id(value)
            if self._is_valid_customer_id(value) and value not in discovered:
                discovered.append(value)
        return discovered

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

        logger.info("Google Ads request: method=%s url=%s", method, url)

        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
                if raw.strip() == "":
                    return {}
                return json.loads(raw)
        except error.HTTPError as exc:
            try:
                response_body = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                response_body = "<unreadable body>"

            request_id: str | None = None
            failure_details: list[object] = []
            if "googleads.googleapis.com" in url:
                request_id, failure_details = self._extract_google_ads_error_details(
                    response_body=response_body,
                    response_headers=getattr(exc, "headers", None),
                )
                logger.error(
                    "Google Ads error payload: method=%s url=%s status=%s request_id=%s failure_details=%s response=%s",
                    method,
                    url,
                    exc.code,
                    request_id,
                    failure_details,
                    response_body[:2000],
                )

            raise GoogleAdsIntegrationError(
                "Google Ads HTTP request failed: "
                f"method={method} url={url} status={exc.code} reason={exc.reason} "
                f"request_id={request_id} failure_details={failure_details} response={response_body[:1200]}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise GoogleAdsIntegrationError(f"Google Ads HTTP request failed: method={method} url={url} error={exc}") from exc

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

    def production_diagnostics(self) -> dict[str, object]:
        settings = load_settings()
        manager_raw = settings.google_ads_manager_customer_id.strip()
        manager_normalized = self._normalize_customer_id(manager_raw)
        manager_has_dashes = "-" in manager_raw
        warnings: list[str] = []

        if settings.google_ads_developer_token.strip() == "":
            warnings.append("GOOGLE_ADS_DEVELOPER_TOKEN is missing")
        elif len(settings.google_ads_developer_token.strip()) < 10:
            warnings.append("GOOGLE_ADS_DEVELOPER_TOKEN looks too short")

        if manager_raw == "":
            warnings.append("GOOGLE_ADS_MANAGER_CUSTOMER_ID is missing")
        elif not self._is_valid_customer_id(manager_raw):
            warnings.append("GOOGLE_ADS_MANAGER_CUSTOMER_ID must be 10 digits (no dashes)")
        elif manager_has_dashes:
            warnings.append("GOOGLE_ADS_MANAGER_CUSTOMER_ID contains dashes; set it in Railway without dashes")

        refresh_available = bool((self._runtime_refresh_token or settings.google_ads_refresh_token).strip())
        if not refresh_available:
            warnings.append("GOOGLE_ADS_REFRESH_TOKEN is missing (complete OAuth exchange first)")

        return {
            "mode": settings.google_ads_mode,
            "api_version_effective": self._google_api_version(),
            "api_version_candidates": self._candidate_api_versions(),
            "developer_token_present": settings.google_ads_developer_token.strip() != "",
            "manager_customer_id_raw": manager_raw,
            "manager_customer_id_normalized": manager_normalized,
            "manager_customer_id_valid": self._is_valid_customer_id(manager_raw) if manager_raw else False,
            "manager_customer_id_has_dashes": manager_has_dashes,
            "refresh_token_present": refresh_available,
            "redirect_uri": settings.google_ads_redirect_uri,
            "customer_ids_csv_count": len([item for item in settings.google_ads_customer_ids_csv.split(",") if item.strip()]),
            "warnings": warnings,
        }

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
        manager_customer_id = self._required_manager_customer_id()

        access_token = self._access_token_from_refresh()
        preflight_accounts = self._list_accessible_customers_via_service(
            access_token=access_token,
            manager_customer_id=manager_customer_id,
        )
        if not preflight_accounts:
            raise GoogleAdsIntegrationError(
                "Google customers:listAccessibleCustomers returned no accounts. "
                "OAuth refresh token or developer token likely lacks access to the configured MCC."
            )

        api_version = self._google_api_version()
        query = (
            "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager "
            "FROM customer_client"
        )

        operations = [
            {
                "name": "searchStream",
                "method": "POST",
                "path": f"customers/{manager_customer_id}/googleAds:searchStream",
                "payload": {"query": query},
            },
            {
                "name": "search",
                "method": "POST",
                "path": f"customers/{manager_customer_id}/googleAds:search",
                "payload": {"query": query, "pageSize": 1000},
            },
        ]

        last_error: GoogleAdsIntegrationError | None = None
        for operation in operations:
            url = self._build_google_ads_url(api_version, operation["path"])
            try:
                payload = self._http_json(
                    method=str(operation["method"]),
                    url=url,
                    payload=operation["payload"],
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "developer-token": settings.google_ads_developer_token,
                        "login-customer-id": manager_customer_id,
                    },
                )

                rows: list[dict[str, object]] = []
                if operation["name"] == "searchStream":
                    if not isinstance(payload, list):
                        raise GoogleAdsIntegrationError("Invalid response received from Google manager searchStream")
                    for chunk in payload:
                        if isinstance(chunk, dict) and isinstance(chunk.get("results"), list):
                            rows.extend([item for item in chunk["results"] if isinstance(item, dict)])
                else:
                    if not isinstance(payload, dict):
                        raise GoogleAdsIntegrationError("Invalid response received from Google manager search")
                    result_rows = payload.get("results", [])
                    if isinstance(result_rows, list):
                        rows.extend([item for item in result_rows if isinstance(item, dict)])

                account_ids: list[str] = []
                for row in rows:
                    customer_client = row.get("customerClient", {})
                    if not isinstance(customer_client, dict):
                        continue
                    cid = str(customer_client.get("id", "")).strip()
                    if cid and cid not in account_ids:
                        account_ids.append(cid)

                if manager_customer_id not in account_ids:
                    account_ids.insert(0, manager_customer_id)
                logger.info(
                    "Google Ads manager discovery succeeded using operation=%s version=%s count=%s",
                    operation["name"],
                    api_version,
                    len(account_ids),
                )
                return account_ids
            except GoogleAdsIntegrationError as exc:
                last_error = exc
                if "status=404" in str(exc):
                    logger.warning(
                        "Google Ads manager discovery 404 for operation=%s version=%s url=%s",
                        operation["name"],
                        api_version,
                        url,
                    )
                    continue
                raise

        if last_error is not None:
            raise GoogleAdsIntegrationError(
                "Google Ads manager account discovery failed after operation fallback attempts. "
                f"Last error: {last_error}"
            ) from last_error

        return [manager_customer_id]

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
        login_customer_id = self._required_manager_customer_id()
        query = (
            "SELECT metrics.cost_micros, metrics.impressions, metrics.clicks, "
            "metrics.conversions, metrics.conversions_value "
            "FROM customer WHERE segments.date DURING LAST_30_DAYS"
        )

        response_payload = self._http_json(
            method="POST",
            url=self._build_google_ads_url(api_version, f"customers/{normalized_customer_id}/googleAds:searchStream"),
            payload={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_ads_developer_token,
                "login-customer-id": login_customer_id,
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
            if not self._is_valid_customer_id(customer_id):
                raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")
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
