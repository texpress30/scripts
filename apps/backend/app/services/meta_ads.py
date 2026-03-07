from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from urllib import parse, request, error
import secrets

from app.core.config import load_settings
from app.services.integration_secrets_store import integration_secrets_store
from app.services.client_registry import client_registry_service
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store


class MetaAdsIntegrationError(RuntimeError):
    pass


class MetaAdsService:
    _oauth_state_cache: set[str]

    def __init__(self) -> None:
        self._oauth_state_cache = set()
        self._runtime_access_token = ""

    def _oauth_config_missing_vars(self) -> list[str]:
        settings = load_settings()
        missing: list[str] = []
        if settings.meta_app_id.strip() == "":
            missing.append("META_APP_ID")
        if settings.meta_app_secret.strip() == "":
            missing.append("META_APP_SECRET")
        if settings.meta_redirect_uri.strip() == "":
            missing.append("META_REDIRECT_URI")
        return missing

    def _require_oauth_config(self) -> None:
        missing = self._oauth_config_missing_vars()
        if missing:
            raise MetaAdsIntegrationError(f"Meta OAuth configuration incomplete: {', '.join(missing)}")

    def _meta_api_version(self) -> str:
        raw = load_settings().meta_api_version.strip().strip("/")
        if raw == "":
            return "v20.0"
        return raw

    def _meta_scopes(self) -> tuple[str, ...]:
        return ("ads_read", "ads_management", "business_management")

    def _http_json(self, *, method: str, url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
        req = request.Request(url, method=method, headers=headers or {})
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
                if raw.strip() == "":
                    return {}
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise MetaAdsIntegrationError("Meta API returned invalid response payload")
                return payload
        except error.HTTPError as exc:
            try:
                response_body = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                response_body = "<unreadable body>"
            raise MetaAdsIntegrationError(
                f"Meta API request failed: method={method} url={url} status={exc.code} response={response_body[:500]}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise MetaAdsIntegrationError(f"Meta API request failed: method={method} url={url} error={exc}") from exc

    @staticmethod
    def _normalize_meta_account_id(*, raw_id: object, raw_account_id: object) -> str:
        account_id = str(raw_account_id or "").strip().replace("act_", "")
        if account_id != "" and account_id.isdigit():
            return f"act_{account_id}"

        normalized_id = str(raw_id or "").strip()
        if normalized_id.startswith("act_"):
            return normalized_id
        if normalized_id.isdigit():
            return f"act_{normalized_id}"
        return normalized_id

    def _resolve_active_access_token_with_source(self) -> tuple[str, str, str | None, str | None]:
        access_token_secret = None
        expires_secret = None
        try:
            access_token_secret = integration_secrets_store.get_secret(provider="meta_ads", secret_key="access_token")
            expires_secret = integration_secrets_store.get_secret(provider="meta_ads", secret_key="access_token_expires_at")
        except Exception:  # noqa: BLE001
            access_token_secret = None
            expires_secret = None

        if access_token_secret is not None and access_token_secret.value.strip() != "":
            token_updated_at = access_token_secret.updated_at.isoformat() if access_token_secret.updated_at is not None else None
            expires_at = str(expires_secret.value).strip() if expires_secret is not None and str(expires_secret.value).strip() != "" else None
            return access_token_secret.value.strip(), "database", token_updated_at, expires_at

        runtime_token = (self._runtime_access_token or "").strip()
        if runtime_token != "":
            return runtime_token, "runtime", None, None

        env_token = load_settings().meta_access_token.strip()
        if env_token != "" and not env_token.startswith("your_"):
            return env_token, "env_fallback", None, None

        return "", "missing", None, None

    def _active_access_token(self) -> str:
        token, _, _, _ = self._resolve_active_access_token_with_source()
        if token == "":
            raise MetaAdsIntegrationError("Meta Ads token is missing or placeholder.")
        return token

    def list_accessible_ad_accounts(self) -> list[dict[str, object]]:
        access_token = self._active_access_token()
        version = self._meta_api_version()

        fields = [
            "id",
            "account_id",
            "name",
            "account_status",
            "currency",
            "timezone_name",
            "timezone_offset_hours_utc",
            "business",
            "owner",
        ]

        discovered: dict[str, dict[str, object]] = {}
        after: str | None = None

        while True:
            params: dict[str, object] = {
                "fields": ",".join(fields),
                "limit": 200,
            }
            if after is not None and after.strip() != "":
                params["after"] = after

            url = f"https://graph.facebook.com/{version}/me/adaccounts?{parse.urlencode(params)}"
            payload = self._http_json(
                method="GET",
                url=url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            raw_data = payload.get("data")
            rows = raw_data if isinstance(raw_data, list) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                canonical_id = self._normalize_meta_account_id(raw_id=row.get("id"), raw_account_id=row.get("account_id"))
                if canonical_id == "":
                    continue

                name = str(row.get("name") or canonical_id).strip() or canonical_id
                account_status = row.get("account_status")
                currency = str(row.get("currency") or "").strip().upper() or None
                timezone_name = str(row.get("timezone_name") or "").strip() or None

                account_payload: dict[str, object] = {
                    "id": canonical_id,
                    "name": name,
                    "account_status": None if account_status is None else str(account_status),
                    "currency_code": currency,
                    "account_timezone": timezone_name,
                    "raw_id": str(row.get("id") or "").strip() or None,
                    "raw_account_id": str(row.get("account_id") or "").strip() or None,
                }
                discovered[canonical_id] = account_payload

            paging = payload.get("paging") if isinstance(payload.get("paging"), dict) else {}
            cursors = paging.get("cursors") if isinstance(paging.get("cursors"), dict) else {}
            next_after = str(cursors.get("after") or "").strip()
            if next_after == "":
                break
            after = next_after

        return [discovered[key] for key in sorted(discovered.keys())]

    def integration_status(self) -> dict[str, str | bool | None]:
        token, token_source, token_updated_at, token_expires_at = self._resolve_active_access_token_with_source()
        oauth_configured = len(self._oauth_config_missing_vars()) == 0
        connected = token != ""
        return {
            "provider": "meta_ads",
            "status": "connected" if connected else "pending",
            "message": (
                "Meta Ads access token is available."
                if connected
                else "Meta Ads access token missing. Complete OAuth connect or configure fallback token."
            ),
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "token_expires_at": token_expires_at,
            "oauth_configured": oauth_configured,
        }

    def build_oauth_authorize_url(self) -> dict[str, str]:
        self._require_oauth_config()
        settings = load_settings()
        state = secrets.token_urlsafe(24)
        self._oauth_state_cache.add(state)
        params = {
            "client_id": settings.meta_app_id,
            "redirect_uri": settings.meta_redirect_uri,
            "state": state,
            "scope": ",".join(self._meta_scopes()),
            "response_type": "code",
        }
        return {
            "authorize_url": f"https://www.facebook.com/{self._meta_api_version()}/dialog/oauth?{parse.urlencode(params)}",
            "state": state,
        }

    def exchange_oauth_code(self, *, code: str, state: str) -> dict[str, str | bool | None]:
        self._require_oauth_config()
        if state not in self._oauth_state_cache:
            raise MetaAdsIntegrationError("Invalid OAuth state for Meta connect callback")
        self._oauth_state_cache.discard(state)

        settings = load_settings()
        base_oauth_url = f"https://graph.facebook.com/{self._meta_api_version()}/oauth/access_token"

        code_exchange_params = {
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": settings.meta_redirect_uri,
            "code": code,
        }
        short_lived_payload = self._http_json(method="GET", url=f"{base_oauth_url}?{parse.urlencode(code_exchange_params)}")
        short_lived_token = str(short_lived_payload.get("access_token") or "").strip()
        if short_lived_token == "":
            raise MetaAdsIntegrationError("Meta OAuth code exchange failed: missing access_token")

        long_lived_exchange_params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "fb_exchange_token": short_lived_token,
        }
        long_lived_payload = self._http_json(method="GET", url=f"{base_oauth_url}?{parse.urlencode(long_lived_exchange_params)}")
        long_lived_token = str(long_lived_payload.get("access_token") or "").strip()
        if long_lived_token == "":
            raise MetaAdsIntegrationError("Meta OAuth long-lived token exchange failed: missing access_token")

        integration_secrets_store.upsert_secret(provider="meta_ads", secret_key="access_token", value=long_lived_token)
        self._runtime_access_token = long_lived_token

        expires_in_raw = long_lived_payload.get("expires_in")
        token_expires_at: str | None = None
        if expires_in_raw is not None:
            try:
                expires_in_seconds = int(expires_in_raw)
                if expires_in_seconds > 0:
                    token_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat()
                    integration_secrets_store.upsert_secret(
                        provider="meta_ads",
                        secret_key="access_token_expires_at",
                        value=token_expires_at,
                    )
            except Exception:  # noqa: BLE001
                token_expires_at = None

        _, token_source, token_updated_at, resolved_expires_at = self._resolve_active_access_token_with_source()
        return {
            "status": "connected",
            "message": "Meta OAuth connected. Access token stored securely in application database.",
            "token_source": token_source,
            "token_updated_at": token_updated_at,
            "token_expires_at": resolved_expires_at or token_expires_at,
            "oauth_configured": True,
        }

    @staticmethod
    def _parse_numeric(value: object) -> float:
        try:
            return float(str(value).strip())
        except Exception:  # noqa: BLE001
            return 0.0

    @staticmethod
    def _parse_int(value: object) -> int:
        return int(round(MetaAdsService._parse_numeric(value)))

    @staticmethod
    def _to_api_account_id(account_id: str) -> str:
        normalized = str(account_id or "").strip()
        if normalized == "":
            return ""
        return normalized if normalized.startswith("act_") else f"act_{normalized}"

    @staticmethod
    def _resolve_sync_window(*, start_date: date | None, end_date: date | None) -> tuple[date, date]:
        today = datetime.now(timezone.utc).date()
        default_end = today - timedelta(days=1)
        resolved_end = end_date or default_end
        resolved_start = start_date or (resolved_end - timedelta(days=6))
        if resolved_start > resolved_end:
            raise MetaAdsIntegrationError("start_date must be before or equal to end_date")
        return resolved_start, resolved_end

    def _list_client_meta_account_ids(self, *, client_id: int) -> list[str]:
        mapped_accounts = client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=int(client_id))
        account_ids: list[str] = []
        seen: set[str] = set()
        for item in mapped_accounts:
            if not isinstance(item, dict):
                continue
            account_id = str(item.get("id") or item.get("account_id") or "").strip()
            if account_id == "":
                continue
            canonical = self._to_api_account_id(account_id)
            if canonical in seen:
                continue
            seen.add(canonical)
            account_ids.append(canonical)
        return account_ids

    def _fetch_account_daily_insights(
        self,
        *,
        account_id: str,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> list[dict[str, object]]:
        version = self._meta_api_version()
        fields = [
            "date_start",
            "date_stop",
            "spend",
            "impressions",
            "clicks",
            "actions",
            "action_values",
            "outbound_clicks",
            "inline_link_clicks",
            "unique_clicks",
            "reach",
            "frequency",
            "cpm",
            "cpp",
            "ctr",
        ]

        all_rows: list[dict[str, object]] = []
        after: str | None = None
        while True:
            params: dict[str, object] = {
                "fields": ",".join(fields),
                "level": "account",
                "time_increment": 1,
                "limit": 200,
                "time_range": json.dumps({"since": start_date.isoformat(), "until": end_date.isoformat()}),
            }
            if after:
                params["after"] = after
            url = f"https://graph.facebook.com/{version}/{account_id}/insights?{parse.urlencode(params)}"
            payload = self._http_json(method="GET", url=url, headers={"Authorization": f"Bearer {access_token}"})
            rows = payload.get("data") if isinstance(payload.get("data"), list) else []
            for row in rows:
                if isinstance(row, dict):
                    all_rows.append(row)
            paging = payload.get("paging") if isinstance(payload.get("paging"), dict) else {}
            cursors = paging.get("cursors") if isinstance(paging.get("cursors"), dict) else {}
            after_cursor = str(cursors.get("after") or "").strip()
            if after_cursor == "":
                break
            after = after_cursor
        return all_rows

    @staticmethod
    def _derive_conversions(*, actions: object) -> float:
        if not isinstance(actions, list):
            return 0.0
        allowed = {
            "purchase",
            "omni_purchase",
            "offsite_conversion",
            "offsite_conversion.purchase",
            "onsite_conversion.purchase",
            "app_custom_event.fb_mobile_purchase",
        }
        total = 0.0
        for item in actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip().lower()
            if action_type not in allowed:
                continue
            total += MetaAdsService._parse_numeric(item.get("value"))
        return total

    @staticmethod
    def _derive_conversion_value(*, action_values: object) -> float:
        if not isinstance(action_values, list):
            return 0.0
        allowed = {
            "purchase",
            "omni_purchase",
            "offsite_conversion",
            "offsite_conversion.purchase",
            "onsite_conversion.purchase",
            "app_custom_event.fb_mobile_purchase",
        }
        total = 0.0
        for item in action_values:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip().lower()
            if action_type not in allowed:
                continue
            total += MetaAdsService._parse_numeric(item.get("value"))
        return total

    def sync_client(self, client_id: int, *, start_date: date | None = None, end_date: date | None = None) -> dict[str, object]:
        resolved_start, resolved_end = self._resolve_sync_window(start_date=start_date, end_date=end_date)
        access_token, token_source, _, _ = self._resolve_active_access_token_with_source()
        if access_token == "":
            raise MetaAdsIntegrationError("Meta Ads token is missing or placeholder.")

        account_ids = self._list_client_meta_account_ids(client_id=int(client_id))
        if len(account_ids) == 0:
            raise MetaAdsIntegrationError("No Meta Ads accounts attached to this client.")

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
            insights_rows = self._fetch_account_daily_insights(
                account_id=account_id,
                start_date=resolved_start,
                end_date=resolved_end,
                access_token=access_token,
            )
            account_rows_written = 0
            account_totals = {
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0.0,
                "conversion_value": 0.0,
            }
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
                conversions = self._derive_conversions(actions=item.get("actions"))
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
                    extra_metrics={
                        "meta_ads": {
                            "actions": item.get("actions") if isinstance(item.get("actions"), list) else [],
                            "action_values": item.get("action_values") if isinstance(item.get("action_values"), list) else [],
                            "outbound_clicks": item.get("outbound_clicks"),
                            "inline_link_clicks": item.get("inline_link_clicks"),
                            "unique_clicks": item.get("unique_clicks"),
                            "reach": item.get("reach"),
                            "frequency": item.get("frequency"),
                            "cpm": item.get("cpm"),
                            "cpp": item.get("cpp"),
                            "ctr": item.get("ctr"),
                            "date_stop": item.get("date_stop"),
                        }
                    },
                )
                rows_written += 1
                account_rows_written += 1
                totals["spend"] += spend
                totals["impressions"] += impressions
                totals["clicks"] += clicks
                totals["conversions"] += conversions
                totals["revenue"] += conversion_value
                account_totals["spend"] += spend
                account_totals["impressions"] += impressions
                account_totals["clicks"] += clicks
                account_totals["conversions"] += conversions
                account_totals["conversion_value"] += conversion_value

            account_summaries.append(
                {
                    "account_id": account_id,
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
            "message": "Meta Ads account_daily sync completed.",
            "platform": "meta_ads",
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

        meta_snapshot_store.upsert_snapshot(payload={
            "client_id": int(client_id),
            "spend": float(snapshot["spend"]),
            "impressions": int(snapshot["impressions"]),
            "clicks": int(snapshot["clicks"]),
            "conversions": int(round(float(snapshot["conversions"]))),
            "revenue": float(snapshot["revenue"]),
            "synced_at": str(snapshot["synced_at"]),
        })
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return meta_snapshot_store.get_snapshot(client_id=client_id)


meta_ads_service = MetaAdsService()
