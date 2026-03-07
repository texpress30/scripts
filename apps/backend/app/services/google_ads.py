from __future__ import annotations

import base64
import json
import logging
import re
import secrets
import os
from datetime import date, datetime, timezone, timedelta
from urllib import error, parse, request

try:
    from google.ads.googleads.client import GoogleAdsClient
except Exception:  # noqa: BLE001
    GoogleAdsClient = None

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.google_store import google_snapshot_store
from app.services.integration_secrets_store import integration_secrets_store
from app.services.performance_reports import performance_reports_store
from app.services.sync_engine import BackfillRunResult, DailyMetricRow, enqueue_backfill

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
        raw = settings.google_ads_api_version.strip().lower() or "v23"
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


    def _refresh_token_with_source(self) -> tuple[str, str, str | None]:
        try:
            db_secret = integration_secrets_store.get_secret(provider="google_ads", secret_key="refresh_token")
        except Exception:  # noqa: BLE001
            db_secret = None
        if db_secret is not None and db_secret.value.strip() != "":
            updated_at = db_secret.updated_at.isoformat() if db_secret.updated_at is not None else None
            return db_secret.value.strip(), "database", updated_at

        runtime_token = (self._runtime_refresh_token or "").strip()
        if runtime_token != "":
            return runtime_token, "runtime", None

        env_token = load_settings().google_ads_refresh_token.strip()
        if env_token != "":
            return env_token, "env_fallback", None

        return "", "missing", None

    def _google_ads_client(self, *, refresh_token: str | None = None) -> object:
        settings = load_settings()
        if GoogleAdsClient is None:
            raise GoogleAdsIntegrationError(
                "google-ads SDK is not installed. Add it to backend requirements to use production account discovery."
            )

        resolved_token, _, _ = self._refresh_token_with_source()
        effective_refresh_token = (refresh_token or resolved_token).strip()
        if effective_refresh_token == "":
            raise GoogleAdsIntegrationError(
                "Google Ads SDK client requires refresh token. Complete OAuth exchange to persist token in app storage."
            )

        config: dict[str, object] = {
            "developer_token": settings.google_ads_developer_token,
            "use_proto_plus": True,
            "oauth2_client_id": settings.google_ads_client_id,
            "oauth2_client_secret": settings.google_ads_client_secret,
            "oauth2_refresh_token": effective_refresh_token,
        }
        try:
            return GoogleAdsClient.load_from_dict(config, version=self._google_api_version())
        except ValueError as exc:
            raise GoogleAdsIntegrationError(f"Google Ads SDK configuration error: {exc}") from exc

    def _list_accessible_customers_via_http(self, *, access_token: str) -> list[str]:
        settings = load_settings()
        url = self._build_google_ads_url(self._google_api_version(), "customers:listAccessibleCustomers")
        payload = self._http_json(
            method="GET",
            url=url,
            payload=None,
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_ads_developer_token,
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
            response_headers = getattr(exc, "headers", None)
            response_headers_debug: dict[str, str] = {}
            if hasattr(response_headers, "items"):
                try:
                    response_headers_debug = {str(k): str(v) for k, v in response_headers.items()}
                except Exception:  # noqa: BLE001
                    response_headers_debug = {}
            if "googleads.googleapis.com" in url:
                request_id, failure_details = self._extract_google_ads_error_details(
                    response_body=response_body,
                    response_headers=response_headers,
                )
                logger.error(
                    "Google Ads error payload: method=%s url=%s status=%s request_id=%s failure_details=%s response_headers=%s response=%s",
                    method,
                    url,
                    exc.code,
                    request_id,
                    failure_details,
                    response_headers_debug,
                    response_body[:2000],
                )

            raise GoogleAdsIntegrationError(
                "Google Ads HTTP request failed: "
                f"method={method} url={url} status={exc.code} reason={exc.reason} "
                f"request_id={request_id} failure_details={failure_details} response_headers={response_headers_debug} "
                f"response={response_body[:1200]}"
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

        _, token_source, _ = self._refresh_token_with_source()
        refresh_available = token_source != "missing"
        if not refresh_available:
            warnings.append("Google Ads refresh token is missing (complete OAuth exchange first)")

        return {
            "mode": settings.google_ads_mode,
            "api_version_effective": self._google_api_version(),
            "api_version_candidates": self._candidate_api_versions(),
            "developer_token_present": settings.google_ads_developer_token.strip() != "",
            "manager_customer_id_raw_masked": self._mask_identifier(manager_raw),
            "manager_customer_id_normalized": manager_normalized,
            "manager_customer_id_valid": self._is_valid_customer_id(manager_raw) if manager_raw else False,
            "manager_customer_id_has_dashes": manager_has_dashes,
            "refresh_token_present": refresh_available,
            "refresh_token_source": token_source,
            "redirect_uri": settings.google_ads_redirect_uri,
            "customer_ids_csv_count": len([item for item in settings.google_ads_customer_ids_csv.split(",") if item.strip()]),
            "warnings": warnings,
        }

    def _mask_identifier(self, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            return ""
        if len(normalized) <= 4:
            return "****"
        return f"***{normalized[-4:]}"

    def _db_diagnostics_last_30_days(self) -> dict[str, object]:
        database_url = os.environ.get("DATABASE_URL") or load_settings().database_url
        try:
            if psycopg is None:
                raise RuntimeError("psycopg not installed")
            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.ad_performance_reports')")
                    table_exists = (cur.fetchone() or [None])[0] is not None
                    if not table_exists:
                        return {
                            "db_rows_last_30_days": 0,
                            "last_report_date": None,
                            "last_sync_at": None,
                            "db_error": "Tabela ad_performance_reports lipsește",
                        }

                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'ad_performance_reports'
                              AND column_name = 'provider'
                        )
                        """
                    )
                    has_provider = bool((cur.fetchone() or [False])[0])

                    if has_provider:
                        cur.execute(
                            """
                            SELECT COALESCE(COUNT(*), 0), MAX(synced_at)
                            FROM ad_performance_reports
                            WHERE provider = %s
                              AND synced_at >= NOW() - INTERVAL '30 days'
                            """,
                            ("google",),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT COALESCE(COUNT(*), 0), MAX(synced_at)
                            FROM ad_performance_reports
                            WHERE platform = %s
                              AND synced_at >= NOW() - INTERVAL '30 days'
                            """,
                            ("google_ads",),
                        )
                    row = cur.fetchone() or (0, None)
            return {
                "db_rows_last_30_days": int(row[0] or 0),
                "last_report_date": None,
                "last_sync_at": str(row[1]) if row[1] else None,
                "db_error": None,
            }
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            lowered = message.lower()
            if "does not exist" in lowered and "ad_performance_reports" in lowered:
                message = "Tabela ad_performance_reports lipsește"
            return {
                "db_rows_last_30_days": 0,
                "last_report_date": None,
                "last_sync_at": None,
                "db_error": message,
            }

    def db_debug_summary(self) -> dict[str, object]:
        database_url = os.environ.get("DATABASE_URL") or load_settings().database_url
        result: dict[str, object] = {
            "db_ok": False,
            "table_exists": False,
            "table": "ad_performance_reports",
            "last_90_days": {
                "count_total": 0,
                "count_by_provider": [],
                "count_by_platform": [],
                "max_report_date": None,
                "max_synced_at": None,
            },
            "other_relevant_tables": [],
            "last_error": None,
        }

        try:
            if psycopg is None:
                raise RuntimeError("psycopg not installed")

            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.ad_performance_reports')")
                    table_exists = (cur.fetchone() or [None])[0] is not None
                    result["table_exists"] = bool(table_exists)

                    if table_exists:
                        cur.execute(
                            """
                            SELECT COALESCE(COUNT(*), 0), MAX(report_date), MAX(synced_at)
                            FROM ad_performance_reports
                            WHERE synced_at >= NOW() - INTERVAL '90 days'
                            """
                        )
                        total_row = cur.fetchone() or (0, None, None)
                        result["last_90_days"] = {
                            "count_total": int(total_row[0] or 0),
                            "count_by_provider": [],
                            "count_by_platform": [],
                            "max_report_date": str(total_row[1]) if total_row[1] else None,
                            "max_synced_at": str(total_row[2]) if total_row[2] else None,
                        }

                        cur.execute(
                            """
                            SELECT EXISTS (
                                SELECT 1
                                FROM information_schema.columns
                                WHERE table_schema='public' AND table_name='ad_performance_reports' AND column_name='provider'
                            )
                            """
                        )
                        has_provider = bool((cur.fetchone() or [False])[0])
                        if has_provider:
                            cur.execute(
                                """
                                SELECT provider, COUNT(*)
                                FROM ad_performance_reports
                                WHERE synced_at >= NOW() - INTERVAL '90 days'
                                GROUP BY provider
                                ORDER BY COUNT(*) DESC
                                """
                            )
                            result["last_90_days"]["count_by_provider"] = [
                                {"provider": str(row[0] or ""), "count": int(row[1] or 0)} for row in cur.fetchall() or []
                            ]

                        cur.execute(
                            """
                            SELECT EXISTS (
                                SELECT 1
                                FROM information_schema.columns
                                WHERE table_schema='public' AND table_name='ad_performance_reports' AND column_name='platform'
                            )
                            """
                        )
                        has_platform = bool((cur.fetchone() or [False])[0])
                        if has_platform:
                            cur.execute(
                                """
                                SELECT platform, COUNT(*)
                                FROM ad_performance_reports
                                WHERE synced_at >= NOW() - INTERVAL '90 days'
                                GROUP BY platform
                                ORDER BY COUNT(*) DESC
                                """
                            )
                            result["last_90_days"]["count_by_platform"] = [
                                {"platform": str(row[0] or ""), "count": int(row[1] or 0)} for row in cur.fetchall() or []
                            ]

                    cur.execute(
                        """
                        SELECT table_name,
                               MAX(CASE WHEN column_name='customer_id' THEN 1 ELSE 0 END) AS has_customer_id,
                               MAX(CASE WHEN column_name='provider' THEN 1 ELSE 0 END) AS has_provider,
                               MAX(CASE WHEN column_name='platform' THEN 1 ELSE 0 END) AS has_platform,
                               MAX(CASE WHEN column_name='cost_micros' THEN 1 ELSE 0 END) AS has_cost_micros,
                               MAX(CASE WHEN column_name='impressions' THEN 1 ELSE 0 END) AS has_impressions,
                               MAX(CASE WHEN column_name='synced_at' THEN 1 ELSE 0 END) AS has_synced_at,
                               MAX(CASE WHEN column_name='report_date' THEN 1 ELSE 0 END) AS has_report_date
                        FROM information_schema.columns
                        WHERE table_schema='public'
                        GROUP BY table_name
                        HAVING MAX(CASE WHEN column_name IN ('customer_id','provider','platform','cost_micros','impressions') THEN 1 ELSE 0 END) = 1
                        ORDER BY table_name
                        """
                    )
                    tables = cur.fetchall() or []
                    extras: list[dict[str, object]] = []
                    for row in tables:
                        table_name = str(row[0])
                        if table_name == "ad_performance_reports":
                            continue
                        has_synced_at = bool(row[6])
                        has_report_date = bool(row[7])
                        row_count = 0
                        max_date = None
                        max_synced_at = None
                        if has_synced_at:
                            cur.execute(
                                psycopg.sql.SQL(
                                    "SELECT COALESCE(COUNT(*), 0), MAX(synced_at) FROM {} WHERE synced_at >= NOW() - INTERVAL '90 days'"
                                ).format(psycopg.sql.Identifier(table_name))
                            )
                            agg = cur.fetchone() or (0, None)
                            row_count = int(agg[0] or 0)
                            max_synced_at = str(agg[1]) if agg[1] else None
                        elif has_report_date:
                            cur.execute(
                                psycopg.sql.SQL(
                                    "SELECT COALESCE(COUNT(*), 0), MAX(report_date) FROM {} WHERE report_date >= CURRENT_DATE - INTERVAL '90 days'"
                                ).format(psycopg.sql.Identifier(table_name))
                            )
                            agg = cur.fetchone() or (0, None)
                            row_count = int(agg[0] or 0)
                            max_date = str(agg[1]) if agg[1] else None
                        else:
                            cur.execute(
                                psycopg.sql.SQL("SELECT COALESCE(COUNT(*), 0) FROM {}").format(
                                    psycopg.sql.Identifier(table_name)
                                )
                            )
                            agg = cur.fetchone() or (0,)
                            row_count = int(agg[0] or 0)

                        extras.append(
                            {
                                "table": table_name,
                                "rows_last_90_days": row_count,
                                "max_report_date": max_date,
                                "max_synced_at": max_synced_at,
                                "has_customer_id": bool(row[1]),
                                "has_provider": bool(row[2]),
                                "has_platform": bool(row[3]),
                                "has_cost_micros": bool(row[4]),
                                "has_impressions": bool(row[5]),
                            }
                        )

                    result["other_relevant_tables"] = extras
                    result["db_ok"] = True
        except Exception as exc:  # noqa: BLE001
            result["last_error"] = str(exc)

        return result

    def run_diagnostics(self) -> dict[str, object]:
        base = self.production_diagnostics()
        manager_id = str(base.get("manager_customer_id_normalized") or "")

        oauth_ok = False
        developer_token_ok = False
        child_accounts_count = 0
        accessible_customers_count = 0
        sample_metrics_last_30_days: dict[str, object] = {
            "customer_id_masked": None,
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
        }
        last_error: str | None = None

        try:
            access_token = self._access_token_from_refresh()
            oauth_ok = bool(access_token)
            accounts = self.list_accessible_customer_accounts()
            accessible_customers_count = len(accounts)
            developer_token_ok = accessible_customers_count > 0

            non_manager = [item for item in accounts if self._normalize_customer_id(item.get("id", "")) != manager_id]
            child_accounts_count = len(non_manager)
            target = non_manager[0]["id"] if non_manager else (accounts[0]["id"] if accounts else "")

            if target:
                normalized_customer_id = self._normalize_customer_id(target)
                metrics_payload = self._http_json(
                    method="POST",
                    url=self._build_google_ads_url(
                        self._google_api_version(),
                        f"customers/{normalized_customer_id}/googleAds:searchStream",
                    ),
                    payload={
                        "query": (
                            "SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros "
                            "FROM customer WHERE segments.date DURING LAST_30_DAYS"
                        )
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "developer-token": load_settings().google_ads_developer_token,
                        "login-customer-id": manager_id,
                    },
                )

                impressions = 0
                clicks = 0
                cost_micros = 0
                if isinstance(metrics_payload, list):
                    for chunk in metrics_payload:
                        if not isinstance(chunk, dict):
                            continue
                        rows = chunk.get("results", [])
                        if not isinstance(rows, list):
                            continue
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            metrics = row.get("metrics", {})
                            if not isinstance(metrics, dict):
                                continue
                            impressions += int(metrics.get("impressions", 0) or 0)
                            clicks += int(metrics.get("clicks", 0) or 0)
                            cost_micros += int(metrics.get("costMicros", 0) or 0)

                sample_metrics_last_30_days = {
                    "customer_id_masked": self._mask_identifier(normalized_customer_id),
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost_micros": cost_micros,
                }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

        db_diag = self._db_diagnostics_last_30_days()
        return {
            "oauth_ok": oauth_ok,
            "developer_token_ok": developer_token_ok,
            "manager_id": self._mask_identifier(manager_id),
            "child_accounts_count": child_accounts_count,
            "accessible_customers_count": accessible_customers_count,
            "sample_metrics_last_30_days": sample_metrics_last_30_days,
            "db_rows_last_30_days": db_diag["db_rows_last_30_days"],
            "rows_in_db_last_30_days": db_diag["db_rows_last_30_days"],
            "last_sync_at": db_diag["last_sync_at"],
            "last_error": last_error or db_diag.get("db_error"),
            "api_version": self._google_api_version(),
            "refresh_token_source": base.get("refresh_token_source", "missing"),
            "refresh_token_present": bool(base.get("refresh_token_present", False)),
        }

    def _refresh_token(self) -> str:
        token, _, _ = self._refresh_token_with_source()
        if token == "":
            raise GoogleAdsIntegrationError(
                "Google refresh token missing. Complete OAuth connect flow to store token in app database."
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
            _, token_source, token_updated_at = self._refresh_token_with_source()
            connected = token_source != "missing"
            return {
                "provider": "google_ads",
                "status": "connected" if connected else "pending",
                "message": "Google Ads production mode is enabled." if connected else "Google Ads production mode awaiting OAuth token.",
                "mode": "production",
                "refresh_token_source": token_source,
                "refresh_token_updated_at": token_updated_at,
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
        integration_secrets_store.upsert_secret(
            provider="google_ads",
            secret_key="refresh_token",
            value=refresh_token,
        )
        self._runtime_refresh_token = refresh_token

        accessible_customers = [item["id"] for item in self.list_accessible_customer_accounts()]
        _, token_source, token_updated_at = self._refresh_token_with_source()
        return {
            "status": "connected",
            "accessible_customers": accessible_customers,
            "refresh_token_source": token_source,
            "refresh_token_updated_at": token_updated_at,
            "message": "Google OAuth connected. Refresh token stored securely in application database.",
        }

    def list_accessible_customer_accounts(self) -> list[dict[str, object]]:
        if not self._is_production_mode():
            return []

        settings = load_settings()
        self._require_production_credentials()
        manager_customer_id = self._required_manager_customer_id()

        access_token = self._access_token_from_refresh()
        preflight_accounts = self._list_accessible_customers_via_http(access_token=access_token)
        if not preflight_accounts:
            raise GoogleAdsIntegrationError(
                "Google customers:listAccessibleCustomers returned no accounts. "
                "OAuth refresh token or developer token likely lacks access to the configured MCC."
            )

        api_version = self._google_api_version()
        query = (
            "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.currency_code "
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

                account_items: list[dict[str, object]] = []
                for row in rows:
                    customer_client = row.get("customerClient", {})
                    if not isinstance(customer_client, dict):
                        continue
                    cid = str(customer_client.get("id", "")).strip()
                    if not cid:
                        continue
                    descriptive_name = str(customer_client.get("descriptiveName", "")).strip() or cid
                    is_manager = bool(customer_client.get("manager", False))
                    currency_code_raw = customer_client.get("currencyCode")
                    currency_code = str(currency_code_raw).strip() if currency_code_raw is not None else None
                    if currency_code == "":
                        currency_code = None
                    if any(item["id"] == cid for item in account_items):
                        continue
                    account_items.append({
                        "id": cid,
                        "name": descriptive_name,
                        "is_manager": is_manager,
                        "currency_code": currency_code,
                    })

                if not any(item["id"] == manager_customer_id for item in account_items):
                    account_items.insert(0, {
                        "id": manager_customer_id,
                        "name": manager_customer_id,
                        "is_manager": True,
                        "currency_code": None,
                    })
                logger.info(
                    "Google Ads manager discovery succeeded using operation=%s version=%s count=%s",
                    operation["name"],
                    api_version,
                    len(account_items),
                )
                return account_items
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

        return [{"id": manager_customer_id, "name": manager_customer_id, "is_manager": True, "currency_code": None}]

    def list_accessible_customers(self) -> list[str]:
        return [item["id"] for item in self.list_accessible_customer_accounts()]

    def get_recommended_customer_id_for_client(self, client_id: int) -> str | None:
        if client_id <= 0:
            return None

        mapped_customer_id = client_registry_service.get_google_customer_for_client(client_id=client_id)
        if mapped_customer_id:
            return self._normalize_customer_id(mapped_customer_id)

        settings = load_settings()
        configured = tuple(item.strip() for item in settings.google_ads_customer_ids_csv.split(",") if item.strip())
        if client_id <= len(configured):
            return self._normalize_customer_id(configured[client_id - 1])
        return None

    def get_recommended_customer_ids_for_client(self, client_id: int) -> list[str]:
        if client_id <= 0:
            return []

        mapped_accounts = [
            self._normalize_customer_id(str(item.get("customer_id") or ""))
            for item in client_registry_service.list_google_mapped_accounts()
            if int(item.get("client_id") or 0) == client_id
        ]

        deduped: list[str] = []
        seen: set[str] = set()
        for item in mapped_accounts:
            if not self._is_valid_customer_id(item):
                continue
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)

        if deduped:
            return deduped

        fallback = self.get_recommended_customer_id_for_client(client_id)
        return [fallback] if fallback else []

    def _fetch_gaql_daily_rows(
        self,
        *,
        customer_id: str,
        query: str,
        login_customer_id: str,
        access_token: str,
    ) -> dict[str, object]:
        settings = load_settings()
        api_version = self._google_api_version()
        normalized_customer_id = self._normalize_customer_id(customer_id)

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

        per_day: dict[str, dict[str, float | int | str]] = {}
        gaql_rows_fetched = 0

        for chunk in response_payload:
            if not isinstance(chunk, dict):
                continue
            results = chunk.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                segments = result.get("segments", {})
                metrics = result.get("metrics", {})
                if not isinstance(segments, dict) or not isinstance(metrics, dict):
                    continue
                report_date = str(segments.get("date", "")).strip()
                if report_date == "":
                    continue
                gaql_rows_fetched += 1
                day_payload = per_day.setdefault(
                    report_date,
                    {
                        "report_date": report_date,
                        "spend": 0.0,
                        "impressions": 0,
                        "clicks": 0,
                        "conversions": 0.0,
                        "revenue": 0.0,
                        "google_customer_id": normalized_customer_id,
                        "extra_metrics": {
                            "google_ads": {
                                "cost_micros": 0,
                                "all_conversions": 0.0,
                                "all_conversions_value": 0.0,
                            }
                        },
                    },
                )
                raw_cost_micros = int(metrics.get("costMicros", 0) or 0)
                raw_conversions = float(metrics.get("conversions", 0.0) or 0.0)
                raw_conversions_value = float(metrics.get("conversionsValue", 0.0) or 0.0)
                day_payload["spend"] = round(float(day_payload["spend"]) + (raw_cost_micros / 1_000_000.0), 2)
                day_payload["impressions"] = int(day_payload["impressions"]) + int(metrics.get("impressions", 0) or 0)
                day_payload["clicks"] = int(day_payload["clicks"]) + int(metrics.get("clicks", 0) or 0)
                day_payload["conversions"] = float(day_payload["conversions"]) + raw_conversions
                day_payload["revenue"] = round(float(day_payload["revenue"]) + raw_conversions_value, 2)
                extra_metrics = day_payload.get("extra_metrics")
                if isinstance(extra_metrics, dict):
                    google_metrics = extra_metrics.get("google_ads")
                    if isinstance(google_metrics, dict):
                        google_metrics["cost_micros"] = int(google_metrics.get("cost_micros", 0) or 0) + raw_cost_micros
                        google_metrics["all_conversions"] = float(google_metrics.get("all_conversions", 0.0) or 0.0) + raw_conversions
                        google_metrics["all_conversions_value"] = round(float(google_metrics.get("all_conversions_value", 0.0) or 0.0) + raw_conversions_value, 2)

        return {
            "rows": [per_day[key] for key in sorted(per_day.keys())],
            "gaql_rows_fetched": gaql_rows_fetched,
        }

    def _fetch_production_daily_metrics(
        self,
        *,
        customer_id: str,
        days: int = 30,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, object]:
        access_token = self._access_token_from_refresh()
        normalized_customer_id = self._normalize_customer_id(customer_id)
        login_customer_id = self._required_manager_customer_id()
        window_days = max(1, min(int(days), 3660))

        resolved_end = end_date or datetime.now(timezone.utc).date()
        resolved_start = start_date or (resolved_end - timedelta(days=window_days - 1))
        if resolved_start > resolved_end:
            resolved_start, resolved_end = resolved_end, resolved_start

        start_literal = resolved_start.isoformat()
        end_literal = resolved_end.isoformat()
        date_clause = f"segments.date BETWEEN '{start_literal}' AND '{end_literal}'"

        primary_query = (
            "SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM customer WHERE {date_clause}"
        )
        primary_payload = self._fetch_gaql_daily_rows(
            customer_id=normalized_customer_id,
            query=primary_query,
            login_customer_id=login_customer_id,
            access_token=access_token,
        )
        primary_rows = list(primary_payload.get("rows", []))
        primary_fetched = int(primary_payload.get("gaql_rows_fetched", 0) or 0)

        used_fallback = False
        fallback_fetched = 0
        rows = primary_rows

        if primary_fetched == 0:
            used_fallback = True
            fallback_query = (
                "SELECT segments.date, metrics.cost_micros "
                f"FROM campaign WHERE {date_clause}"
            )
            fallback_payload = self._fetch_gaql_daily_rows(
                customer_id=normalized_customer_id,
                query=fallback_query,
                login_customer_id=login_customer_id,
                access_token=access_token,
            )
            rows = list(fallback_payload.get("rows", []))
            fallback_fetched = int(fallback_payload.get("gaql_rows_fetched", 0) or 0)

        gaql_rows_fetched = primary_fetched if primary_fetched > 0 else fallback_fetched
        zero_data_message = None
        if gaql_rows_fetched == 0:
            zero_data_message = f"Account has no data in selected range {start_literal}..{end_literal} or no permission"

        return {
            "rows": rows,
            "gaql_rows_fetched": gaql_rows_fetched,
            "used_fallback": used_fallback,
            "zero_data_message": zero_data_message,
            "resolved_start_date": start_literal,
            "resolved_end_date": end_literal,
        }

    def fetch_campaign_daily_metrics(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date_exclusive: date,
    ) -> list[dict[str, object]]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        if not self._is_valid_customer_id(normalized_customer_id):
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")

        resolved_start = start_date
        resolved_end_exclusive = end_date_exclusive
        if resolved_start > resolved_end_exclusive:
            resolved_start, resolved_end_exclusive = resolved_end_exclusive, resolved_start
        if resolved_start == resolved_end_exclusive:
            return []
        resolved_end_inclusive = resolved_end_exclusive - timedelta(days=1)

        if not self._is_production_mode():
            return [
                {
                    "campaign_id": "mock-campaign",
                    "campaign_name": "Mock Campaign",
                    "campaign_status": "ENABLED",
                    "campaign_raw": {"id": "mock-campaign", "name": "Mock Campaign", "status": "ENABLED"},
                    "campaign_payload_hash": "mock-campaign",
                    "report_date": resolved_start.isoformat(),
                    "spend": 1.23,
                    "impressions": 100,
                    "clicks": 10,
                    "conversions": 1.0,
                    "conversion_value": 3.21,
                    "extra_metrics": {
                        "google_ads": {
                            "cost_micros": 1_230_000,
                        }
                    },
                }
            ]

        access_token = self._access_token_from_refresh()
        login_customer_id = self._required_manager_customer_id()
        start_literal = resolved_start.isoformat()
        end_literal = resolved_end_inclusive.isoformat()
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, segments.date, metrics.impressions, metrics.clicks, "
            "metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM campaign WHERE segments.date BETWEEN '{start_literal}' AND '{end_literal}'"
        )

        response_payload = self._http_json(
            method="POST",
            url=self._build_google_ads_url(load_settings().google_ads_api_version, f"customers/{normalized_customer_id}/googleAds:searchStream"),
            payload={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": load_settings().google_ads_developer_token,
                "login-customer-id": login_customer_id,
            },
        )
        if not isinstance(response_payload, list):
            raise GoogleAdsIntegrationError("Invalid Google Ads searchStream response")

        rows: list[dict[str, object]] = []
        for chunk in response_payload:
            if not isinstance(chunk, dict):
                continue
            results = chunk.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                campaign = result.get("campaign", {})
                segments = result.get("segments", {})
                metrics = result.get("metrics", {})
                if not isinstance(campaign, dict) or not isinstance(segments, dict) or not isinstance(metrics, dict):
                    continue
                campaign_id = str(campaign.get("id", "")).strip()
                report_date = str(segments.get("date", "")).strip()
                if campaign_id == "" or report_date == "":
                    continue
                cost_micros = int(metrics.get("costMicros", 0) or 0)
                rows.append(
                    {
                        "campaign_id": campaign_id,
                        "campaign_name": campaign.get("name"),
                        "campaign_status": str(campaign.get("status", "")).strip() or None,
                        "campaign_raw": {
                            "id": campaign.get("id"),
                            "name": campaign.get("name"),
                            "status": campaign.get("status"),
                        },
                        "campaign_payload_hash": f"{campaign_id}:{campaign.get('status')}:{campaign.get('name')}",
                        "report_date": report_date,
                        "spend": cost_micros / 1_000_000.0,
                        "impressions": int(metrics.get("impressions", 0) or 0),
                        "clicks": int(metrics.get("clicks", 0) or 0),
                        "conversions": float(metrics.get("conversions", 0.0) or 0.0),
                        "conversion_value": float(metrics.get("conversionsValue", 0.0) or 0.0),
                        "extra_metrics": {
                            "google_ads": {
                                "cost_micros": cost_micros,
                            }
                        },
                    }
                )
        return rows

    def fetch_ad_group_daily_metrics(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date_exclusive: date,
        source_job_id: str | None = None,
    ) -> list[dict[str, object]]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        if not self._is_valid_customer_id(normalized_customer_id):
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")

        resolved_start = start_date
        resolved_end_exclusive = end_date_exclusive
        if resolved_start > resolved_end_exclusive:
            resolved_start, resolved_end_exclusive = resolved_end_exclusive, resolved_start
        if resolved_start == resolved_end_exclusive:
            return []
        resolved_end_inclusive = resolved_end_exclusive - timedelta(days=1)

        if not self._is_production_mode():
            return [
                {
                    "report_date": resolved_start.isoformat(),
                    "campaign_id": "mock-campaign",
                    "campaign_name": "Mock Campaign",
                    "ad_group_id": "mock-ad-group",
                    "ad_group_name": "Mock Ad Group",
                    "spend": 1.23,
                    "impressions": 100,
                    "clicks": 10,
                    "conversions": 1.0,
                    "conversion_value": 3.21,
                    "extra_metrics": {"google_ads": {"cost_micros": 1_230_000, "source_job_id": source_job_id}},
                }
            ]

        access_token = self._access_token_from_refresh()
        login_customer_id = self._required_manager_customer_id()
        start_literal = resolved_start.isoformat()
        end_literal = resolved_end_inclusive.isoformat()
        query = (
            "SELECT segments.date, campaign.id, campaign.name, ad_group.id, ad_group.name, "
            "metrics.impressions, metrics.clicks, metrics.conversions, metrics.conversions_value, metrics.cost_micros "
            f"FROM ad_group WHERE segments.date BETWEEN '{start_literal}' AND '{end_literal}'"
        )

        response_payload = self._http_json(
            method="POST",
            url=self._build_google_ads_url(load_settings().google_ads_api_version, f"customers/{normalized_customer_id}/googleAds:searchStream"),
            payload={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": load_settings().google_ads_developer_token,
                "login-customer-id": login_customer_id,
            },
        )
        if not isinstance(response_payload, list):
            raise GoogleAdsIntegrationError("Invalid Google Ads searchStream response")

        rows: list[dict[str, object]] = []
        for chunk in response_payload:
            if not isinstance(chunk, dict):
                continue
            results = chunk.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                segments = result.get("segments", {})
                campaign = result.get("campaign", {})
                ad_group = result.get("adGroup", {})
                metrics = result.get("metrics", {})
                if not isinstance(segments, dict) or not isinstance(campaign, dict) or not isinstance(ad_group, dict) or not isinstance(metrics, dict):
                    continue
                report_date = str(segments.get("date", "")).strip()
                campaign_id = str(campaign.get("id", "")).strip()
                ad_group_id = str(ad_group.get("id", "")).strip()
                if report_date == "" or ad_group_id == "":
                    continue
                cost_micros = int(metrics.get("costMicros", 0) or 0)
                rows.append(
                    {
                        "report_date": report_date,
                        "campaign_id": campaign_id or None,
                        "campaign_name": campaign.get("name"),
                        "ad_group_id": ad_group_id,
                        "ad_group_name": ad_group.get("name"),
                        "spend": cost_micros / 1_000_000.0,
                        "impressions": int(metrics.get("impressions", 0) or 0),
                        "clicks": int(metrics.get("clicks", 0) or 0),
                        "conversions": float(metrics.get("conversions", 0.0) or 0.0),
                        "conversion_value": float(metrics.get("conversionsValue", 0.0) or 0.0),
                        "extra_metrics": {
                            "google_ads": {
                                "cost_micros": cost_micros,
                                "source_job_id": source_job_id,
                            }
                        },
                    }
                )
        return rows

    def fetch_ad_unit_daily_metrics(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date_exclusive: date,
        source_job_id: str | None = None,
    ) -> list[dict[str, object]]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        if not self._is_valid_customer_id(normalized_customer_id):
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")

        resolved_start = start_date
        resolved_end_exclusive = end_date_exclusive
        if resolved_start > resolved_end_exclusive:
            resolved_start, resolved_end_exclusive = resolved_end_exclusive, resolved_start
        if resolved_start == resolved_end_exclusive:
            return []
        resolved_end_inclusive = resolved_end_exclusive - timedelta(days=1)

        if not self._is_production_mode():
            return [
                {
                    "report_date": resolved_start.isoformat(),
                    "campaign_id": "mock-campaign",
                    "ad_group_id": "mock-ad-group",
                    "ad_id": "mock-ad",
                    "ad_name": "Mock Ad",
                    "ad_status": "ENABLED",
                    "spend": 1.23,
                    "impressions": 100,
                    "clicks": 10,
                    "conversions": 1.0,
                    "conversion_value": 3.21,
                    "extra_metrics": {"google_ads": {"cost_micros": 1_230_000, "source_job_id": source_job_id}},
                }
            ]

        access_token = self._access_token_from_refresh()
        login_customer_id = self._required_manager_customer_id()
        start_literal = resolved_start.isoformat()
        end_literal = resolved_end_inclusive.isoformat()
        query = (
            "SELECT segments.date, campaign.id, ad_group.id, ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status, "
            "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM ad_group_ad WHERE segments.date >= '{start_literal}' AND segments.date <= '{end_literal}'"
        )

        response_payload = self._http_json(
            method="POST",
            url=self._build_google_ads_url(load_settings().google_ads_api_version, f"customers/{normalized_customer_id}/googleAds:searchStream"),
            payload={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": load_settings().google_ads_developer_token,
                "login-customer-id": login_customer_id,
            },
        )
        if not isinstance(response_payload, list):
            raise GoogleAdsIntegrationError("Invalid Google Ads searchStream response")

        rows: list[dict[str, object]] = []
        for chunk in response_payload:
            if not isinstance(chunk, dict):
                continue
            results = chunk.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                segments = result.get("segments", {})
                campaign = result.get("campaign", {})
                ad_group = result.get("adGroup", {})
                ad_group_ad = result.get("adGroupAd", {})
                metrics = result.get("metrics", {})
                if not isinstance(segments, dict) or not isinstance(campaign, dict) or not isinstance(ad_group, dict) or not isinstance(ad_group_ad, dict) or not isinstance(metrics, dict):
                    continue
                ad_payload = ad_group_ad.get("ad", {})
                if not isinstance(ad_payload, dict):
                    ad_payload = {}
                report_date = str(segments.get("date", "")).strip()
                ad_id = str(ad_payload.get("id", "")).strip()
                if report_date == "" or ad_id == "":
                    continue
                cost_micros = int(metrics.get("costMicros", 0) or 0)
                rows.append(
                    {
                        "report_date": report_date,
                        "campaign_id": str(campaign.get("id", "")).strip() or None,
                        "ad_group_id": str(ad_group.get("id", "")).strip() or None,
                        "ad_id": ad_id,
                        "ad_name": ad_payload.get("name"),
                        "ad_status": str(ad_group_ad.get("status", "")).strip() or None,
                        "spend": cost_micros / 1_000_000.0,
                        "impressions": int(metrics.get("impressions", 0) or 0),
                        "clicks": int(metrics.get("clicks", 0) or 0),
                        "conversions": float(metrics.get("conversions", 0.0) or 0.0),
                        "conversion_value": float(metrics.get("conversionsValue", 0.0) or 0.0),
                        "extra_metrics": {
                            "google_ads": {
                                "cost_micros": cost_micros,
                                "source_job_id": source_job_id,
                            }
                        },
                    }
                )
        return rows

    def _fetch_production_metrics(self, *, customer_id: str) -> dict[str, float | int | str]:
        payload = self._fetch_production_daily_metrics(customer_id=customer_id, days=30)
        rows = list(payload.get("rows", []))
        spend = sum(float(item.get("spend", 0.0)) for item in rows)
        impressions = sum(int(item.get("impressions", 0)) for item in rows)
        clicks = sum(int(item.get("clicks", 0)) for item in rows)
        normalized_customer_id = self._normalize_customer_id(customer_id)
        conversions = sum(float(item.get("conversions", 0.0) or 0.0) for item in rows)
        revenue = sum(float(item.get("revenue", 0.0) or 0.0) for item in rows)
        return {
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": round(conversions, 4),
            "revenue": round(revenue, 2),
            "google_customer_id": normalized_customer_id,
        }

    def _persist_performance_report(self, *, snapshot: dict[str, float | int | str], client_id: int) -> int:
        customer_id = str(snapshot.get("google_customer_id") or self.get_recommended_customer_id_for_client(client_id) or f"client-{client_id}")
        report_date_raw = str(snapshot.get("report_date") or "").strip()
        report_date_value: date
        if report_date_raw:
            report_date_value = date.fromisoformat(report_date_raw)
        else:
            report_date_value = datetime.now(timezone.utc).date()
        performance_reports_store.write_daily_report(
            report_date=report_date_value,
            platform="google_ads",
            customer_id=customer_id,
            client_id=client_id,
            spend=float(snapshot.get("spend", 0.0)),
            impressions=int(snapshot.get("impressions", 0)),
            clicks=int(snapshot.get("clicks", 0)),
            conversions=float(snapshot.get("conversions", 0)),
            conversion_value=float(snapshot.get("revenue", 0.0)),
            extra_metrics=dict(snapshot.get("extra_metrics", {})) if isinstance(snapshot.get("extra_metrics"), dict) else None,
        )
        return 1

    def _count_rows_last_30_days_for_customer(self, *, customer_id: str) -> int:
        database_url = os.environ.get("DATABASE_URL") or load_settings().database_url
        normalized = self._normalize_customer_id(customer_id)
        try:
            if psycopg is None:
                return 0
            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(COUNT(*), 0)
                        FROM ad_performance_reports
                        WHERE platform = %s
                          AND customer_id = %s
                          AND report_date >= CURRENT_DATE - INTERVAL '29 days'
                        """,
                        ("google_ads", normalized),
                    )
                    row = cur.fetchone() or (0,)
                    return int(row[0] or 0)
        except Exception:
            return 0

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        customer_ids = self.get_recommended_customer_ids_for_client(client_id)
        if not customer_ids:
            raise GoogleAdsIntegrationError(
                "No Google customer mapping for this client. Set GOOGLE_ADS_CUSTOMER_IDS_CSV ordered by local client ids or import accounts first."
            )

        invalid_ids = [item for item in customer_ids if not self._is_valid_customer_id(item)]
        if invalid_ids:
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{invalid_ids[0]}'. Expected 10 digits.")

        synced_at = datetime.now(timezone.utc).isoformat()
        aggregated_spend = 0.0
        aggregated_impressions = 0
        aggregated_clicks = 0
        aggregated_conversions = 0
        aggregated_revenue = 0.0

        for customer_id in customer_ids:
            try:
                if self._is_production_mode():
                    daily_payload = self._fetch_production_daily_metrics(customer_id=customer_id, days=30)
                    daily_rows = list(daily_payload.get("rows", []))
                    customer_snapshot = {
                        "client_id": client_id,
                        "platform": "google_ads",
                        "spend": round(sum(float(item.get("spend", 0.0)) for item in daily_rows), 2),
                        "impressions": sum(int(item.get("impressions", 0)) for item in daily_rows),
                        "clicks": sum(int(item.get("clicks", 0)) for item in daily_rows),
                        "conversions": 0,
                        "revenue": 0.0,
                        "google_customer_id": customer_id,
                        "synced_at": synced_at,
                    }
                    for row in daily_rows:
                        payload_row = dict(row)
                        payload_row["google_customer_id"] = customer_id
                        self._persist_performance_report(snapshot=payload_row, client_id=client_id)
                else:
                    spend = float(100 + client_id * 17)
                    impressions = 5000 + client_id * 110
                    clicks = 200 + client_id * 9
                    conversions = 5 + client_id
                    revenue = round(spend * 3.2, 2)
                    customer_snapshot = {
                        "client_id": client_id,
                        "platform": "google_ads",
                        "spend": round(spend, 2),
                        "impressions": impressions,
                        "clicks": clicks,
                        "conversions": conversions,
                        "revenue": revenue,
                        "google_customer_id": customer_id,
                        "synced_at": synced_at,
                    }
                    self._persist_performance_report(snapshot=customer_snapshot, client_id=client_id)

                aggregated_spend += float(customer_snapshot["spend"])
                aggregated_impressions += int(customer_snapshot["impressions"])
                aggregated_clicks += int(customer_snapshot["clicks"])
                aggregated_conversions += int(customer_snapshot["conversions"])
                aggregated_revenue += float(customer_snapshot["revenue"])
            except GoogleAdsIntegrationError:
                raise
            except Exception as exc:  # noqa: BLE001
                masked_customer_id = self._mask_identifier(customer_id)
                raise GoogleAdsIntegrationError(f"Google Ads sync failed for customer {masked_customer_id}: {str(exc)[:300]}") from exc

        snapshot: dict[str, float | int | str] = {
            "client_id": client_id,
            "platform": "google_ads",
            "spend": round(aggregated_spend, 2),
            "impressions": aggregated_impressions,
            "clicks": aggregated_clicks,
            "conversions": aggregated_conversions,
            "revenue": round(aggregated_revenue, 2),
            "google_customer_id": customer_ids[0],
            "synced_customers_count": len(customer_ids),
            "synced_at": synced_at,
        }
        google_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def fetch_chunk(self, *, account_id: str, chunk_start: date, chunk_end: date) -> dict[str, object]:
        return self._fetch_production_daily_metrics(
            customer_id=account_id,
            start_date=chunk_start,
            end_date=chunk_end,
            days=max(1, (chunk_end - chunk_start).days + 1),
        )

    def normalize_to_rows(self, *, payload: dict[str, object], account_id: str, client_id: int) -> list[DailyMetricRow]:
        rows: list[DailyMetricRow] = []
        for item in list(payload.get("rows", [])):
            raw_date = str(item.get("report_date") or "").strip()
            if raw_date == "":
                continue
            rows.append(
                DailyMetricRow(
                    platform="google_ads",
                    account_id=account_id,
                    client_id=client_id,
                    report_date=date.fromisoformat(raw_date),
                    spend=float(item.get("spend", 0.0) or 0.0),
                    impressions=int(item.get("impressions", 0) or 0),
                    clicks=int(item.get("clicks", 0) or 0),
                    conversions=float(item.get("conversions", 0) or 0.0),
                    revenue=float(item.get("revenue", 0.0) or 0.0),
                    extra_metrics=dict(item.get("extra_metrics", {})) if isinstance(item.get("extra_metrics"), dict) else {},
                )
            )
        return rows

    def upsert_rows(self, rows: list[DailyMetricRow]) -> int:
        return performance_reports_store.upsert_rows(rows)

    def _build_historical_range_summary(self, *, run_result: BackfillRunResult) -> dict[str, int]:
        empty_chunks = len([chunk for chunk in run_result.chunks if chunk.status == "ok" and int(chunk.fetched_rows) == 0])
        failed_chunks = len([chunk for chunk in run_result.chunks if chunk.status == "error"])
        return {
            "planned_chunks": int(run_result.attempted_chunks),
            "executed_chunks": int(len(run_result.chunks)),
            "empty_chunks": int(empty_chunks),
            "failed_chunks": int(failed_chunks),
            "rows_upserted": int(run_result.upserted_rows_total),
            "successful_chunks": int(run_result.successful_chunks),
        }

    def _run_customer_backfill_range(
        self,
        *,
        client_id: int,
        customer_id: str,
        start_date: date,
        end_date: date,
        chunk_days: int,
        mode: str,
    ) -> tuple[dict[str, float | int | str], int, int, dict[str, int]]:
        if mode not in ("rolling_30d", "historical_range"):
            raise GoogleAdsIntegrationError(f"Unsupported Google Ads sync mode '{mode}'")
        normalized_customer_id = self._normalize_customer_id(customer_id)
        if not self._is_valid_customer_id(normalized_customer_id):
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")
        if start_date > end_date:
            raise GoogleAdsIntegrationError("historical_range requires start_date <= end_date")
        if int(chunk_days) <= 0:
            raise GoogleAdsIntegrationError("chunk_days must be > 0")

        run_result = enqueue_backfill(
            platform="google_ads",
            account_id=normalized_customer_id,
            client_id=client_id,
            start=start_date,
            end=end_date,
            chunk_days=max(1, min(int(chunk_days), 31)),
            fetch_chunk=lambda account_id, chunk_start, chunk_end: self.fetch_chunk(account_id=account_id, chunk_start=chunk_start, chunk_end=chunk_end),
            normalize_to_rows=lambda payload, account_id, cid: self.normalize_to_rows(payload=payload, account_id=account_id, client_id=cid),
            upsert_rows=self.upsert_rows,
        )

        if mode == "historical_range":
            for chunk in run_result.chunks:
                logger.info(
                    "google_ads.sync mode=%s client_id=%s account_id=%s chunk_start=%s chunk_end=%s rows_upserted=%s status=%s",
                    mode,
                    client_id,
                    normalized_customer_id,
                    chunk.start_date.isoformat(),
                    chunk.end_date.isoformat(),
                    int(chunk.upserted_rows),
                    chunk.status,
                )
                if chunk.status == "ok" and int(chunk.fetched_rows) == 0:
                    logger.warning(
                        "google_ads.sync mode=%s client_id=%s account_id=%s chunk_start=%s chunk_end=%s empty_result=true",
                        mode,
                        client_id,
                        normalized_customer_id,
                        chunk.start_date.isoformat(),
                        chunk.end_date.isoformat(),
                    )
                if chunk.status == "error":
                    logger.warning(
                        "google_ads.sync mode=%s client_id=%s account_id=%s chunk_start=%s chunk_end=%s error=%s",
                        mode,
                        client_id,
                        normalized_customer_id,
                        chunk.start_date.isoformat(),
                        chunk.end_date.isoformat(),
                        str(chunk.error or "")[:300],
                    )

        snapshot: dict[str, float | int | str] = {
            "client_id": client_id,
            "platform": "google_ads",
            "spend": round(float(sum(float(chunk.spend) for chunk in run_result.chunks)), 2),
            "impressions": int(sum(int(chunk.impressions) for chunk in run_result.chunks)),
            "clicks": int(sum(int(chunk.clicks) for chunk in run_result.chunks)),
            "conversions": int(sum(float(chunk.conversions) for chunk in run_result.chunks)),
            "revenue": round(float(sum(float(chunk.revenue) for chunk in run_result.chunks)), 2),
            "google_customer_id": normalized_customer_id,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "effective_start_date": start_date.isoformat(),
            "effective_end_date": end_date.isoformat(),
        }
        return snapshot, int(run_result.fetched_rows_total), int(run_result.upserted_rows_total), self._build_historical_range_summary(run_result=run_result)

    def sync_customer_for_client(self, *, client_id: int, customer_id: str, days: int = 30, start_date: date | None = None, end_date: date | None = None, chunk_days: int = 7) -> dict[str, float | int | str]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        if not self._is_valid_customer_id(normalized_customer_id):
            raise GoogleAdsIntegrationError(f"Invalid customer id mapping '{customer_id}'. Expected 10 digits.")

        window_days = max(1, min(int(days), 3660))
        logger.info("google_ads.sync_now customer_id=%s client_id=%s START", normalized_customer_id, client_id)

        reason_if_zero: str | None = None
        zero_message: str | None = None
        gaql_rows_fetched = 0

        if self._is_production_mode():
            resolved_end = end_date or datetime.now(timezone.utc).date()
            resolved_start = start_date or (resolved_end - timedelta(days=window_days - 1))
            snapshot, gaql_rows_fetched, inserted_rows, chunk_summary = self._run_customer_backfill_range(
                client_id=client_id,
                customer_id=normalized_customer_id,
                start_date=resolved_start,
                end_date=resolved_end,
                chunk_days=chunk_days,
                mode="rolling_30d",
            )
            if gaql_rows_fetched == 0:
                reason_if_zero = "GAQL_RETURNED_0"
                zero_message = f"Account has no data in selected range {resolved_start.isoformat()}..{resolved_end.isoformat()} or no permission"
            logger.info(
                "google_ads.sync_now customer_id=%s client_id=%s CHUNKS ok=%s failed=%s upserted=%s",
                normalized_customer_id,
                client_id,
                int(chunk_summary.get("successful_chunks", 0)),
                int(chunk_summary.get("failed_chunks", 0)),
                inserted_rows,
            )
        else:
            inserted_rows = 0
            spend = float(100 + client_id * 17)
            impressions = 5000 + client_id * 110
            clicks = 200 + client_id * 9
            conversions = 5 + client_id
            revenue = round(spend * 3.2, 2)
            gaql_rows_fetched = 1
            snapshot = {
                "client_id": client_id,
                "platform": "google_ads",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "revenue": revenue,
                "google_customer_id": normalized_customer_id,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "mode": "rolling_30d",
            }
            logger.info("google_ads.sync_now customer_id=%s client_id=%s GAQL ok (mock mode)", normalized_customer_id, client_id)

        logger.info("google_ads.sync_now customer_id=%s client_id=%s GAQL_ROWS=%s", normalized_customer_id, client_id, gaql_rows_fetched)

        google_snapshot_store.upsert_snapshot(payload=snapshot)
        try:
            if not self._is_production_mode():
                inserted_rows = self._persist_performance_report(snapshot=snapshot, client_id=client_id)
        except Exception as exc:  # noqa: BLE001
            reason_if_zero = "DB_INSERT_FAILED"
            zero_message = str(exc)[:300]
            inserted_rows = 0

        logger.info("google_ads.sync_now customer_id=%s client_id=%s UPSERT_INSERTED=%s", normalized_customer_id, client_id, inserted_rows)

        db_rows_last_30 = self._count_rows_last_30_days_for_customer(customer_id=normalized_customer_id)
        logger.info("google_ads.sync_now customer_id=%s client_id=%s DB_ROWS_LAST30=%s", normalized_customer_id, client_id, db_rows_last_30)

        if reason_if_zero is None and gaql_rows_fetched > 0 and inserted_rows > 0 and db_rows_last_30 == 0:
            reason_if_zero = "DB_ROWS_FILTER_MISMATCH"
            zero_message = "Rows were inserted but DB last-30 filter returned 0"

        if reason_if_zero is None and gaql_rows_fetched == 0:
            reason_if_zero = "GAQL_RETURNED_0"
            zero_message = zero_message or "Account has no data in last 30 days or no permission"

        logger.info("google_ads.sync_now customer_id=%s client_id=%s DONE", normalized_customer_id, client_id)
        snapshot["gaql_rows_fetched"] = gaql_rows_fetched
        if self._is_production_mode():
            snapshot["resolved_start_date"] = resolved_start
            snapshot["resolved_end_date"] = resolved_end
        snapshot["inserted_rows"] = inserted_rows
        snapshot["db_rows_last_30_for_customer"] = db_rows_last_30
        snapshot["reason_if_zero"] = reason_if_zero
        if zero_message:
            snapshot["message"] = zero_message
        return snapshot

    def sync_customer_for_client_historical_range(
        self,
        *,
        client_id: int,
        customer_id: str,
        start_date: date,
        end_date: date,
        chunk_days: int,
    ) -> dict[str, object]:
        if not self._is_production_mode():
            raise GoogleAdsIntegrationError("historical_range backfill is supported only in production mode")
        snapshot, gaql_rows_fetched, inserted_rows, chunk_summary = self._run_customer_backfill_range(
            client_id=client_id,
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            chunk_days=chunk_days,
            mode="historical_range",
        )
        google_snapshot_store.upsert_snapshot(payload=snapshot)
        return {
            **snapshot,
            "gaql_rows_fetched": gaql_rows_fetched,
            "rows_upserted": inserted_rows,
            "planned_chunks": int(chunk_summary.get("planned_chunks", 0)),
            "executed_chunks": int(chunk_summary.get("executed_chunks", 0)),
            "empty_chunks": int(chunk_summary.get("empty_chunks", 0)),
            "failed_chunks": int(chunk_summary.get("failed_chunks", 0)),
        }

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return google_snapshot_store.get_snapshot(client_id=client_id)


google_ads_service = GoogleAdsService()
