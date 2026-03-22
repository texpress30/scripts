from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Literal

from app.core.config import load_settings
from app.services.ai_recommendations_repository import ai_recommendations_repository
from app.services.dashboard import unified_dashboard_service

RecommendationStatus = Literal["new", "approved", "rejected", "applied", "expired"]
ActionType = Literal["approve", "dismiss", "snooze", "apply"]


@dataclass
class RecommendationPayload:
    problema: str
    cauza: str
    actiune: str
    impact_estimat: str
    incredere: float
    risc: str


@dataclass
class RecommendationRecord:
    id: int
    client_id: int
    payload: RecommendationPayload
    status: RecommendationStatus = "new"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    snoozed_until: str | None = None
    source: str = "rules+llm"


@dataclass
class RecommendationAction:
    recommendation_id: int
    action: ActionType
    actor: str
    status: str
    details: dict[str, object]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RedisQueueMock:
    def __init__(self) -> None:
        self._jobs: list[dict[str, object]] = []
        self._next_job_id = 1
        self._lock = Lock()

    def enqueue(self, queue_name: str, payload: dict[str, object]) -> dict[str, object]:
        with self._lock:
            job = {
                "job_id": self._next_job_id,
                "queue": queue_name,
                "payload": payload,
                "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._next_job_id += 1
            self._jobs.append(job)
            return dict(job)

    def pop_next(self, queue_name: str) -> dict[str, object] | None:
        with self._lock:
            for index, job in enumerate(self._jobs):
                if job["queue"] == queue_name and job["status"] == "queued":
                    self._jobs[index]["status"] = "processing"
                    return dict(self._jobs[index])
        return None


class RecommendationsService:
    def __init__(self) -> None:
        self._items: dict[int, list[RecommendationRecord]] = {}
        self._actions: list[RecommendationAction] = []
        self._next_id = 1
        self._lock = Lock()
        self._queue = RedisQueueMock()

    def _mongo_source_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "ai_recommendations_mongo_source_enabled", False))

    def generate_recommendations(self, client_id: int) -> list[dict[str, object]]:
        payload = self._build_rule_based_payload(client_id)
        llm_payload = self._refine_with_llm(payload)
        if self._mongo_source_enabled():
            now = datetime.now(timezone.utc).isoformat()
            recommendation_id = ai_recommendations_repository.next_recommendation_id()
            created = ai_recommendations_repository.create_recommendation(
                {
                    "recommendation_id": recommendation_id,
                    "client_id": int(client_id),
                    "payload": asdict(llm_payload),
                    "status": "new",
                    "source": "rules+llm",
                    "created_at": now,
                    "updated_at": now,
                    "snoozed_until": None,
                    "actions": [],
                }
            )
            return [self._serialize_from_dict(created)]
        with self._lock:
            record = RecommendationRecord(id=self._next_id, client_id=client_id, payload=llm_payload)
            self._next_id += 1
            self._items.setdefault(client_id, []).append(record)
            return [self._serialize(record)]

    def list_recommendations(self, client_id: int) -> list[dict[str, object]]:
        if self._mongo_source_enabled():
            items = ai_recommendations_repository.list_recommendations(client_id=int(client_id))
            return [self._serialize_from_dict(item) for item in items]
        with self._lock:
            return [self._serialize(item) for item in self._items.get(client_id, [])]

    def list_actions(self, client_id: int) -> list[dict[str, object]]:
        if self._mongo_source_enabled():
            return ai_recommendations_repository.list_actions(client_id=int(client_id))
        with self._lock:
            recommendation_ids = {item.id for item in self._items.get(client_id, [])}
            actions = [asdict(action) for action in self._actions if action.recommendation_id in recommendation_ids]
        return actions

    def review_recommendation(
        self,
        client_id: int,
        recommendation_id: int,
        action: Literal["approve", "dismiss", "snooze"],
        actor: str,
        snooze_days: int = 3,
    ) -> dict[str, object]:
        if self._mongo_source_enabled():
            recommendation = ai_recommendations_repository.get_recommendation(
                client_id=int(client_id),
                recommendation_id=int(recommendation_id),
            )
            if not isinstance(recommendation, dict):
                raise ValueError("Recommendation not found")

            now = datetime.now(timezone.utc).isoformat()
            if action == "approve":
                updated = ai_recommendations_repository.update_recommendation_and_append_action(
                    client_id=int(client_id),
                    recommendation_id=int(recommendation_id),
                    status="approved",
                    updated_at=now,
                    action={
                        "recommendation_id": int(recommendation_id),
                        "action": "approve",
                        "actor": actor,
                        "status": "ok",
                        "details": {"message": "Recommendation approved"},
                        "timestamp": now,
                    },
                    snoozed_until=recommendation.get("snoozed_until"),
                )
                if not isinstance(updated, dict):
                    raise ValueError("Recommendation not found")
                self._enqueue_apply_job(client_id=client_id, recommendation_id=recommendation_id, actor=actor)
            elif action == "dismiss":
                updated = ai_recommendations_repository.update_recommendation_and_append_action(
                    client_id=int(client_id),
                    recommendation_id=int(recommendation_id),
                    status="rejected",
                    updated_at=now,
                    action={
                        "recommendation_id": int(recommendation_id),
                        "action": "dismiss",
                        "actor": actor,
                        "status": "ok",
                        "details": {"message": "Recommendation dismissed"},
                        "timestamp": now,
                    },
                    snoozed_until=recommendation.get("snoozed_until"),
                )
                if not isinstance(updated, dict):
                    raise ValueError("Recommendation not found")
            else:
                snoozed_until = (datetime.now(timezone.utc) + timedelta(days=snooze_days)).isoformat()
                updated = ai_recommendations_repository.update_recommendation_and_append_action(
                    client_id=int(client_id),
                    recommendation_id=int(recommendation_id),
                    status="expired",
                    updated_at=now,
                    action={
                        "recommendation_id": int(recommendation_id),
                        "action": "snooze",
                        "actor": actor,
                        "status": "ok",
                        "details": {"snoozed_days": snooze_days},
                        "timestamp": now,
                    },
                    snoozed_until=snoozed_until,
                )
                if not isinstance(updated, dict):
                    raise ValueError("Recommendation not found")
            return self.get_recommendation(client_id, recommendation_id)

        with self._lock:
            recommendation = self._find_recommendation(client_id, recommendation_id)
            if action == "approve":
                recommendation.status = "approved"
                recommendation.updated_at = datetime.now(timezone.utc).isoformat()
                self._actions.append(
                    RecommendationAction(
                        recommendation_id=recommendation.id,
                        action="approve",
                        actor=actor,
                        status="ok",
                        details={"message": "Recommendation approved"},
                    )
                )
            elif action == "dismiss":
                recommendation.status = "rejected"
                recommendation.updated_at = datetime.now(timezone.utc).isoformat()
                self._actions.append(
                    RecommendationAction(
                        recommendation_id=recommendation.id,
                        action="dismiss",
                        actor=actor,
                        status="ok",
                        details={"message": "Recommendation dismissed"},
                    )
                )
            else:
                recommendation.status = "expired"
                recommendation.snoozed_until = (datetime.now(timezone.utc) + timedelta(days=snooze_days)).isoformat()
                recommendation.updated_at = datetime.now(timezone.utc).isoformat()
                self._actions.append(
                    RecommendationAction(
                        recommendation_id=recommendation.id,
                        action="snooze",
                        actor=actor,
                        status="ok",
                        details={"snoozed_days": snooze_days},
                    )
                )

        if action == "approve":
            self._enqueue_apply_job(client_id=client_id, recommendation_id=recommendation_id, actor=actor)

        return self.get_recommendation(client_id, recommendation_id)

    def get_recommendation(self, client_id: int, recommendation_id: int) -> dict[str, object]:
        if self._mongo_source_enabled():
            recommendation = ai_recommendations_repository.get_recommendation(
                client_id=int(client_id),
                recommendation_id=int(recommendation_id),
            )
            if not isinstance(recommendation, dict):
                raise ValueError("Recommendation not found")
            return self._serialize_from_dict(recommendation)
        with self._lock:
            recommendation = self._find_recommendation(client_id, recommendation_id)
            return self._serialize(recommendation)

    def get_impact_report(self, client_id: int) -> dict[str, object]:
        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard.get("totals", {})
        spend = float(totals.get("spend", 1.0) or 1.0)
        conversions = float(totals.get("conversions", 1.0) or 1.0)
        roas = float(totals.get("roas", 0.0))

        base_cpa = spend / conversions
        report = []
        for days, factor in [(3, 0.02), (7, 0.05), (14, 0.08)]:
            report.append(
                {
                    "window_days": days,
                    "delta_cpa": round(-base_cpa * factor, 2),
                    "delta_roas": round(roas * factor, 2),
                    "delta_cvr": round(factor * 100, 2),
                }
            )

        return {"client_id": client_id, "windows": report}

    def _enqueue_apply_job(self, client_id: int, recommendation_id: int, actor: str) -> None:
        job = self._queue.enqueue(
            queue_name="recommendations_apply",
            payload={"client_id": client_id, "recommendation_id": recommendation_id, "actor": actor},
        )
        if self._mongo_source_enabled():
            now = datetime.now(timezone.utc).isoformat()
            ai_recommendations_repository.append_action(
                client_id=int(client_id),
                recommendation_id=int(recommendation_id),
                updated_at=now,
                action={
                    "recommendation_id": int(recommendation_id),
                    "action": "apply",
                    "actor": "system_worker",
                    "status": "queued",
                    "details": {"job_id": job["job_id"]},
                    "timestamp": now,
                },
            )
            self._process_apply_queue()
            return
        self._process_apply_queue()
        with self._lock:
            self._actions.append(
                RecommendationAction(
                    recommendation_id=recommendation_id,
                    action="apply",
                    actor="system_worker",
                    status="queued",
                    details={"job_id": job["job_id"]},
                )
            )

    def _process_apply_queue(self) -> None:
        job = self._queue.pop_next("recommendations_apply")
        if not job:
            return

        client_id = int(job["payload"]["client_id"])
        recommendation_id = int(job["payload"]["recommendation_id"])
        apply_result = self._apply_platform_change(client_id=client_id, recommendation_id=recommendation_id)

        if self._mongo_source_enabled():
            status = "applied" if apply_result["status"] == "success" else "approved"
            now = datetime.now(timezone.utc).isoformat()
            ai_recommendations_repository.append_action(
                client_id=client_id,
                recommendation_id=recommendation_id,
                updated_at=now,
                action={
                    "recommendation_id": recommendation_id,
                    "action": "apply",
                    "actor": "system_worker",
                    "status": str(apply_result["status"]),
                    "details": dict(apply_result),
                    "timestamp": now,
                },
            )
            ai_recommendations_repository.update_recommendation_state(
                client_id=client_id,
                recommendation_id=recommendation_id,
                status=status,
                updated_at=now,
            )
            return

        with self._lock:
            recommendation = self._find_recommendation(client_id, recommendation_id)
            recommendation.status = "applied" if apply_result["status"] == "success" else "approved"
            recommendation.updated_at = datetime.now(timezone.utc).isoformat()
            self._actions.append(
                RecommendationAction(
                    recommendation_id=recommendation_id,
                    action="apply",
                    actor="system_worker",
                    status=apply_result["status"],
                    details=apply_result,
                )
            )

    def _apply_platform_change(self, client_id: int, recommendation_id: int) -> dict[str, object]:
        # Mock call to platform API
        return {
            "status": "success",
            "client_id": client_id,
            "recommendation_id": recommendation_id,
            "message": "Budget adjustment pushed to platform API",
        }

    def _build_rule_based_payload(self, client_id: int) -> RecommendationPayload:
        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard.get("totals", {})
        spend = float(totals.get("spend", 0.0))
        conversions = float(totals.get("conversions", 0.0))
        roas = float(totals.get("roas", 0.0))

        if spend > 0 and roas < 2.0:
            return RecommendationPayload(
                problema="ROAS sub pragul tinta",
                cauza="Cost ridicat pe campaniile de prospectare",
                actiune="Reduce bugetul pe ad set-urile cu CPA peste medie cu 15%",
                impact_estimat="+8% ROAS in 7 zile",
                incredere=0.78,
                risc="mediu",
            )
        if conversions > 0 and roas >= 2.0:
            return RecommendationPayload(
                problema="Potential de scalare neexploatat",
                cauza="Campanii profitabile limitate de buget",
                actiune="Creste bugetul pe campaniile cu ROAS > 2.5 cu 10%",
                impact_estimat="+6% conversii in 7 zile",
                incredere=0.74,
                risc="scazut",
            )

        return RecommendationPayload(
            problema="Volum insuficient pentru optimizari agresive",
            cauza="Date limitate in ultima perioada",
            actiune="Mentine bugetele si acumuleaza date suplimentare 3 zile",
            impact_estimat="Stabilizare CPA",
            incredere=0.6,
            risc="scazut",
        )

    def _refine_with_llm(self, payload: RecommendationPayload) -> RecommendationPayload:
        settings = load_settings()
        if not settings.openai_api_key or settings.openai_api_key.startswith("your_"):
            return payload

        prompt = (
            "Reformuleaza recomandarea de marketing in JSON strict cu cheile: "
            "problema,cauza,actiune,impact_estimat,incredere,risc. "
            f"Input: {json.dumps(asdict(payload), ensure_ascii=False)}"
        )

        response_text = self._call_openai(prompt)
        try:
            parsed = json.loads(response_text)
            return RecommendationPayload(
                problema=str(parsed.get("problema", payload.problema)),
                cauza=str(parsed.get("cauza", payload.cauza)),
                actiune=str(parsed.get("actiune", payload.actiune)),
                impact_estimat=str(parsed.get("impact_estimat", payload.impact_estimat)),
                incredere=float(parsed.get("incredere", payload.incredere)),
                risc=str(parsed.get("risc", payload.risc)),
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return payload

    def _call_openai(self, prompt: str) -> str:
        settings = load_settings()
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Return only valid JSON."},
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
                return str(body["choices"][0]["message"]["content"])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError):
            return json.dumps(asdict(self._build_rule_based_payload(client_id=1)), ensure_ascii=False)

    def _find_recommendation(self, client_id: int, recommendation_id: int) -> RecommendationRecord:
        for item in self._items.get(client_id, []):
            if item.id == recommendation_id:
                return item
        raise ValueError("Recommendation not found")

    def _serialize(self, recommendation: RecommendationRecord) -> dict[str, object]:
        return {
            "id": recommendation.id,
            "client_id": recommendation.client_id,
            "status": recommendation.status,
            "payload": asdict(recommendation.payload),
            "source": recommendation.source,
            "created_at": recommendation.created_at,
            "updated_at": recommendation.updated_at,
            "snoozed_until": recommendation.snoozed_until,
        }

    def _serialize_from_dict(self, recommendation: dict[str, object]) -> dict[str, object]:
        return {
            "id": int(recommendation.get("recommendation_id") or recommendation.get("id") or 0),
            "client_id": int(recommendation.get("client_id") or 0),
            "status": str(recommendation.get("status") or ""),
            "payload": dict(recommendation.get("payload") or {}),
            "source": str(recommendation.get("source") or "rules+llm"),
            "created_at": str(recommendation.get("created_at") or ""),
            "updated_at": str(recommendation.get("updated_at") or ""),
            "snoozed_until": recommendation.get("snoozed_until"),
        }


recommendations_service = RecommendationsService()
