from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import load_settings
from app.services.ai_guardrails import has_sufficient_data, sanitize_ai_output
from app.services.dashboard import unified_dashboard_service


@dataclass
class AIRecommendationResult:
    client_id: int
    recommendation: str
    source: str


class AIAssistantService:
    def generate_recommendation(self, client_id: int) -> dict[str, object]:
        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard.get("totals", {})
        spend = float(totals.get("spend", 0.0))
        conversions = int(totals.get("conversions", 0))
        roas = float(totals.get("roas", 0.0))

        if not has_sufficient_data(spend, conversions):
            return AIRecommendationResult(
                client_id=client_id,
                recommendation="Nu am destule date",
                source="fallback",
            ).__dict__

        prompt = (
            "Analizeaza performanta campaniilor Google + Meta si ofera 2 recomandari concrete, actionabile, "
            "in romana, fara introduceri. Date: "
            f"spend={spend}, conversions={conversions}, roas={roas}."
        )

        ai_text = self._call_openai(prompt)
        safe = sanitize_ai_output(ai_text)
        source = "openai" if safe != "Nu am destule date" else "guardrail"

        return AIRecommendationResult(client_id=client_id, recommendation=safe, source=source).__dict__

    def _call_openai(self, prompt: str) -> str:
        settings = load_settings()

        if not settings.openai_api_key or settings.openai_api_key.startswith("your_"):
            return "Nu am destule date"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict marketing assistant. Return concise, concrete recommendations.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError):
            return "Nu am destule date"


ai_assistant_service = AIAssistantService()
