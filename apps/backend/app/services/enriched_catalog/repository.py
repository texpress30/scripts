from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.mongo_provider import get_mongo_collection

_TEMPLATES_COLLECTION = "creative_templates"
_TREATMENTS_COLLECTION = "treatments"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Creative Template Repository
# ---------------------------------------------------------------------------


class CreativeTemplateRepository:
    def _collection(self):
        collection = get_mongo_collection(_TEMPLATES_COLLECTION)
        if collection is None:
            raise RuntimeError(
                "Mongo is not configured (MONGO_URI/MONGO_DATABASE are required "
                "for creative template repository usage)."
            )
        return collection

    def initialize_indexes(self) -> None:
        self._collection().create_index(
            [("id", 1)],
            unique=True,
            name="ux_creative_templates_id",
        )
        self._collection().create_index(
            [("subaccount_id", 1), ("updated_at", -1)],
            name="ix_creative_templates_subaccount_updated_at",
        )

    # -- CRUD ---------------------------------------------------------------

    def create(self, subaccount_id: int, data: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        doc: dict[str, Any] = {
            "id": _new_id(),
            "subaccount_id": int(subaccount_id),
            "name": str(data.get("name") or ""),
            "canvas_width": int(data.get("canvas_width") or 1080),
            "canvas_height": int(data.get("canvas_height") or 1080),
            "elements": list(data.get("elements") or []),
            "background_color": str(data.get("background_color") or "#FFFFFF"),
            "format_group_id": data.get("format_group_id") or None,
            "format_label": data.get("format_label") or None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._collection().insert_one(dict(doc))
        return doc

    def get_by_id(self, template_id: str) -> dict[str, Any] | None:
        found = self._collection().find_one({"id": str(template_id)})
        return self._normalize(found)

    def get_by_subaccount(self, subaccount_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self._collection()
            .find({"subaccount_id": int(subaccount_id)})
            .sort([("updated_at", -1)])
            .limit(max(0, int(limit)))
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def list_all(self, *, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self._collection()
            .find({})
            .sort([("updated_at", -1)])
            .limit(max(0, int(limit)))
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def get_by_format_group(self, format_group_id: str) -> list[dict[str, Any]]:
        cursor = (
            self._collection()
            .find({"format_group_id": str(format_group_id)})
            .sort([("canvas_width", 1), ("canvas_height", 1)])
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def update(self, template_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        set_payload: dict[str, Any] = {"updated_at": _utcnow().isoformat()}
        for key in ("name", "canvas_width", "canvas_height", "elements", "background_color", "format_group_id", "format_label"):
            if key in data and data[key] is not None:
                set_payload[key] = data[key]

        from pymongo import ReturnDocument

        result = self._collection().find_one_and_update(
            {"id": str(template_id)},
            {"$set": set_payload},
            return_document=ReturnDocument.AFTER,
        )
        return self._normalize(result)

    def delete(self, template_id: str) -> bool:
        result = self._collection().delete_one({"id": str(template_id)})
        return (result.deleted_count or 0) > 0

    def duplicate(self, template_id: str, new_name: str, *, new_format_group_id: str | None = None) -> dict[str, Any] | None:
        original = self.get_by_id(template_id)
        if original is None:
            return None
        now = _utcnow()
        doc: dict[str, Any] = {
            **original,
            "id": _new_id(),
            "name": str(new_name),
            "format_group_id": new_format_group_id if new_format_group_id is not None else original.get("format_group_id"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._collection().insert_one(dict(doc))
        return doc

    # -- helpers ------------------------------------------------------------

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        normalized.pop("_id", None)
        return normalized


# ---------------------------------------------------------------------------
# Treatment Repository
# ---------------------------------------------------------------------------


class TreatmentRepository:
    def _collection(self):
        collection = get_mongo_collection(_TREATMENTS_COLLECTION)
        if collection is None:
            raise RuntimeError(
                "Mongo is not configured (MONGO_URI/MONGO_DATABASE are required "
                "for treatment repository usage)."
            )
        return collection

    def initialize_indexes(self) -> None:
        self._collection().create_index(
            [("id", 1)],
            unique=True,
            name="ux_treatments_id",
        )
        self._collection().create_index(
            [("output_feed_id", 1), ("priority", 1)],
            name="ix_treatments_output_feed_priority",
        )

    # -- CRUD ---------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        doc: dict[str, Any] = {
            "id": _new_id(),
            "output_feed_id": str(data.get("output_feed_id") or ""),
            "name": str(data.get("name") or ""),
            "template_id": str(data.get("template_id") or ""),
            "filters": list(data.get("filters") or []),
            "priority": int(data.get("priority") or 0),
            "is_default": bool(data.get("is_default")),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._collection().insert_one(dict(doc))
        return doc

    def get_by_id(self, treatment_id: str) -> dict[str, Any] | None:
        found = self._collection().find_one({"id": str(treatment_id)})
        return self._normalize(found)

    def get_by_output_feed(self, output_feed_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self._collection()
            .find({"output_feed_id": str(output_feed_id)})
            .sort([("priority", 1)])
            .limit(max(0, int(limit)))
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def update(self, treatment_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        set_payload: dict[str, Any] = {"updated_at": _utcnow().isoformat()}
        for key in ("name", "template_id", "filters", "priority", "is_default"):
            if key in data and data[key] is not None:
                set_payload[key] = data[key]

        from pymongo import ReturnDocument

        result = self._collection().find_one_and_update(
            {"id": str(treatment_id)},
            {"$set": set_payload},
            return_document=ReturnDocument.AFTER,
        )
        return self._normalize(result)

    def delete(self, treatment_id: str) -> bool:
        result = self._collection().delete_one({"id": str(treatment_id)})
        return (result.deleted_count or 0) > 0

    def reorder_priority(self, output_feed_id: str, ordered_ids: list[str]) -> None:
        for priority, treatment_id in enumerate(ordered_ids):
            self._collection().update_one(
                {"id": str(treatment_id), "output_feed_id": str(output_feed_id)},
                {"$set": {"priority": priority, "updated_at": _utcnow().isoformat()}},
            )

    def get_matching_treatment(self, output_feed_id: str, product_data: dict[str, Any]) -> dict[str, Any] | None:
        treatments = self.get_by_output_feed(output_feed_id)
        for treatment in treatments:
            if not isinstance(treatment, dict):
                continue
            filters = list(treatment.get("filters") or [])
            if not filters:
                if treatment.get("is_default"):
                    return treatment
                continue
            if self._matches_filters(filters, product_data):
                return treatment
        # Fall back to default treatment
        for treatment in treatments:
            if isinstance(treatment, dict) and treatment.get("is_default"):
                return treatment
        return None

    def _matches_filters(self, filters: list[dict[str, Any]], product_data: dict[str, Any]) -> bool:
        for f in filters:
            field_name = str(f.get("field_name") or "")
            operator = str(f.get("operator") or "")
            filter_value = f.get("value")
            product_value = str(product_data.get(field_name) or "")

            if operator == "equals":
                if product_value != str(filter_value or ""):
                    return False
            elif operator == "contains":
                if str(filter_value or "") not in product_value:
                    return False
            elif operator == "in_list":
                values_list = filter_value if isinstance(filter_value, list) else [str(filter_value or "")]
                if product_value not in values_list:
                    return False
            else:
                return False
        return True

    # -- helpers ------------------------------------------------------------

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        normalized.pop("_id", None)
        return normalized


creative_template_repository = CreativeTemplateRepository()
treatment_repository = TreatmentRepository()
