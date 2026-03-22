from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.mongo_provider import get_mongo_collection

_RECOMMENDATIONS_COLLECTION = "ai_recommendations"
_COUNTERS_COLLECTION = "ai_recommendation_counters"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIRecommendationsRepository:
    def _recommendations_collection(self):
        collection = get_mongo_collection(_RECOMMENDATIONS_COLLECTION)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for ai recommendations repository usage).")
        return collection

    def _counters_collection(self):
        collection = get_mongo_collection(_COUNTERS_COLLECTION)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for ai recommendations repository usage).")
        return collection

    def initialize_indexes(self) -> None:
        self._recommendations_collection().create_index(
            [("recommendation_id", 1)],
            unique=True,
            name="ux_ai_recommendations_recommendation_id",
        )
        self._recommendations_collection().create_index(
            [("client_id", 1), ("updated_at", -1)],
            name="ix_ai_recommendations_client_updated_at",
        )
        self._counters_collection().create_index(
            [("counter_name", 1)],
            unique=True,
            name="ux_ai_recommendation_counters_name",
        )

    def next_recommendation_id(self) -> int:
        from pymongo import ReturnDocument

        result = self._counters_collection().find_one_and_update(
            {"counter_name": "recommendation_id"},
            {
                "$inc": {"value": 1},
                "$setOnInsert": {"counter_name": "recommendation_id", "created_at": _utcnow()},
                "$set": {"updated_at": _utcnow()},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        value = int((result or {}).get("value") or 0)
        if value <= 0:
            raise RuntimeError("Failed to allocate recommendation_id")
        return value

    def create_recommendation(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_recommendation_payload(payload)
        now = _utcnow()
        normalized.setdefault("created_at", now.isoformat())
        normalized["updated_at"] = str(normalized.get("updated_at") or now.isoformat())
        self._recommendations_collection().insert_one(dict(normalized))
        return normalized

    def get_recommendation(self, *, client_id: int, recommendation_id: int) -> dict[str, Any] | None:
        found = self._recommendations_collection().find_one(
            {"client_id": int(client_id), "recommendation_id": int(recommendation_id)}
        )
        return self._normalize_document(found)

    def list_recommendations(self, *, client_id: int, limit: int = 1000) -> list[dict[str, Any]]:
        cursor = (
            self._recommendations_collection()
            .find({"client_id": int(client_id)})
            .sort([("recommendation_id", 1)])
            .limit(max(0, int(limit)))
        )
        return [self._normalize_document(item) for item in cursor if isinstance(item, dict)]

    def update_recommendation_and_append_action(
        self,
        *,
        client_id: int,
        recommendation_id: int,
        status: str,
        updated_at: str,
        action: dict[str, Any],
        snoozed_until: str | None = None,
    ) -> dict[str, Any] | None:
        set_payload: dict[str, Any] = {
            "status": str(status),
            "updated_at": str(updated_at),
        }
        if snoozed_until is not None:
            set_payload["snoozed_until"] = str(snoozed_until)
        from pymongo import ReturnDocument

        result = self._recommendations_collection().find_one_and_update(
            {"client_id": int(client_id), "recommendation_id": int(recommendation_id)},
            {"$set": set_payload, "$push": {"actions": self._normalize_action(action)}},
            return_document=ReturnDocument.AFTER,
        )
        return self._normalize_document(result)

    def append_action(
        self,
        *,
        client_id: int,
        recommendation_id: int,
        action: dict[str, Any],
        updated_at: str | None = None,
    ) -> dict[str, Any] | None:
        update_payload: dict[str, Any] = {"$push": {"actions": self._normalize_action(action)}}
        if updated_at is not None:
            update_payload["$set"] = {"updated_at": str(updated_at)}
        from pymongo import ReturnDocument

        result = self._recommendations_collection().find_one_and_update(
            {"client_id": int(client_id), "recommendation_id": int(recommendation_id)},
            update_payload,
            return_document=ReturnDocument.AFTER,
        )
        return self._normalize_document(result)

    def update_recommendation_state(
        self,
        *,
        client_id: int,
        recommendation_id: int,
        status: str,
        updated_at: str,
        snoozed_until: str | None = None,
    ) -> dict[str, Any] | None:
        set_payload: dict[str, Any] = {"status": str(status), "updated_at": str(updated_at)}
        if snoozed_until is not None:
            set_payload["snoozed_until"] = str(snoozed_until)
        from pymongo import ReturnDocument

        result = self._recommendations_collection().find_one_and_update(
            {"client_id": int(client_id), "recommendation_id": int(recommendation_id)},
            {"$set": set_payload},
            return_document=ReturnDocument.AFTER,
        )
        return self._normalize_document(result)

    def list_actions(self, *, client_id: int) -> list[dict[str, Any]]:
        items = self.list_recommendations(client_id=client_id, limit=5000)
        flattened: list[dict[str, Any]] = []
        for recommendation in items:
            recommendation_id = int(recommendation.get("recommendation_id") or 0)
            for action in list(recommendation.get("actions") or []):
                if not isinstance(action, dict):
                    continue
                normalized = self._normalize_action(action)
                if int(normalized.get("recommendation_id") or 0) <= 0:
                    normalized["recommendation_id"] = recommendation_id
                flattened.append(normalized)
        flattened.sort(key=lambda item: str(item.get("timestamp") or ""))
        return flattened

    def _normalize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(action or {})
        normalized["recommendation_id"] = int(normalized.get("recommendation_id") or 0)
        normalized["action"] = str(normalized.get("action") or "")
        normalized["actor"] = str(normalized.get("actor") or "")
        normalized["status"] = str(normalized.get("status") or "")
        normalized["details"] = dict(normalized.get("details") or {})
        normalized["timestamp"] = str(normalized.get("timestamp") or _utcnow().isoformat())
        return normalized

    def _normalize_recommendation_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        recommendation_id = int(normalized.get("recommendation_id") or normalized.get("id") or 0)
        if recommendation_id <= 0:
            raise ValueError("recommendation_id is required")
        normalized["recommendation_id"] = recommendation_id
        normalized["id"] = recommendation_id
        normalized["client_id"] = int(normalized.get("client_id") or 0)
        if int(normalized["client_id"]) <= 0:
            raise ValueError("client_id is required")
        normalized["payload"] = dict(normalized.get("payload") or {})
        normalized["status"] = str(normalized.get("status") or "new")
        normalized["source"] = str(normalized.get("source") or "rules+llm")
        snoozed_until = normalized.get("snoozed_until")
        normalized["snoozed_until"] = str(snoozed_until) if snoozed_until is not None else None
        normalized["created_at"] = str(normalized.get("created_at") or _utcnow().isoformat())
        normalized["updated_at"] = str(normalized.get("updated_at") or normalized["created_at"])
        normalized["actions"] = [
            self._normalize_action(dict(item))
            for item in list(normalized.get("actions") or [])
            if isinstance(item, dict)
        ]
        return normalized

    def _normalize_document(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        normalized.pop("_id", None)
        return self._normalize_recommendation_payload(normalized)


ai_recommendations_repository = AIRecommendationsRepository()
