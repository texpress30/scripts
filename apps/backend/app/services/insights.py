from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock

from app.services.ai_assistant import ai_assistant_service
from app.services.ai_guardrails import has_sufficient_data
from app.services.dashboard import unified_dashboard_service


@dataclass
class WeeklyInsight:
    client_id: int
    created_at: str
    summary: str
    spend: float
    conversions: int
    roas: float


class InsightsService:
    def __init__(self) -> None:
        self._items: dict[int, list[WeeklyInsight]] = {}
        self._lock = Lock()

    def generate_weekly_insight(self, client_id: int) -> dict[str, object]:
        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard.get("totals", {})
        spend = float(totals.get("spend", 0.0))
        conversions = int(totals.get("conversions", 0))
        roas = float(totals.get("roas", 0.0))

        if not has_sufficient_data(spend, conversions):
            summary = "Nu am destule date"
        else:
            rec = ai_assistant_service.generate_recommendation(client_id)
            summary = (
                f"Săptămâna curentă: Spend={round(spend,2)}, Conversions={conversions}, "
                f"ROAS={round(roas,2)}. Recomandare: {rec['recommendation']}"
            )

        item = WeeklyInsight(
            client_id=client_id,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            summary=summary,
            spend=round(spend, 2),
            conversions=conversions,
            roas=round(roas, 2),
        )

        with self._lock:
            self._items.setdefault(client_id, []).append(item)

        return asdict(item)

    def get_latest(self, client_id: int) -> dict[str, object] | None:
        with self._lock:
            items = self._items.get(client_id, [])
            if not items:
                return None
            return asdict(items[-1])


insights_service = InsightsService()
