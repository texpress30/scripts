from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock

from app.core.config import load_settings
from app.services.dashboard import unified_dashboard_service


@dataclass
class ExportRun:
    client_id: int
    created_at: str
    status: str
    campaign_rows: int
    ad_rows: int
    message: str


class BigQueryExportService:
    def __init__(self) -> None:
        self._runs: list[ExportRun] = []
        self._lock = Lock()

    def run_export_for_client(self, client_id: int) -> dict[str, object]:
        settings = load_settings()
        project_id = settings.bigquery_project_id

        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard.get("totals", {})
        platforms = dashboard.get("platforms", {})

        campaign_row = {
            "client_id": client_id,
            "spend": totals.get("spend", 0.0),
            "impressions": totals.get("impressions", 0),
            "clicks": totals.get("clicks", 0),
            "conversions": totals.get("conversions", 0),
            "revenue": totals.get("revenue", 0.0),
            "roas": totals.get("roas", 0.0),
            "event_time": datetime.now(tz=timezone.utc).isoformat(),
        }

        ad_rows = []
        for platform_name in ("google_ads", "meta_ads"):
            platform = platforms.get(platform_name, {})
            ad_rows.append(
                {
                    "client_id": client_id,
                    "platform": platform_name,
                    "spend": platform.get("spend", 0.0),
                    "impressions": platform.get("impressions", 0),
                    "clicks": platform.get("clicks", 0),
                    "conversions": platform.get("conversions", 0),
                    "revenue": platform.get("revenue", 0.0),
                    "event_time": datetime.now(tz=timezone.utc).isoformat(),
                }
            )

        message = self._export_rows(project_id, "campaign_performance", [campaign_row])
        ad_message = self._export_rows(project_id, "ad_performance", ad_rows)

        run = ExportRun(
            client_id=client_id,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            status="ok",
            campaign_rows=1,
            ad_rows=len(ad_rows),
            message=f"{message}; {ad_message}",
        )

        with self._lock:
            self._runs.append(run)

        return asdict(run)

    def _export_rows(self, project_id: str, table: str, rows: list[dict[str, object]]) -> str:
        settings = load_settings()

        if project_id.startswith("your_"):
            return f"mock_export:{table}:project_placeholder"

        if settings.openai_api_key.startswith("your_"):
            # no service-account flow configured in this phase; keep deterministic mock mode
            return f"mock_export:{table}:no_service_account"

        # lightweight placeholder for direct BigQuery insertAll endpoint integration
        url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/datasets/mcc/tables/{table}/insertAll"
        payload = {"rows": [{"json": row} for row in rows]}
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                _ = resp.read()
            return f"exported:{table}:{len(rows)}"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return f"mock_export:{table}:network_or_auth_unavailable"

    def list_runs(self) -> list[dict[str, object]]:
        with self._lock:
            return [asdict(x) for x in self._runs]


bigquery_export_service = BigQueryExportService()
