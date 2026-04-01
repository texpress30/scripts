from __future__ import annotations

import pytest

from app.services.enriched_catalog import repository as repository_module
from app.services.enriched_catalog.exceptions import TemplateNotFoundError
from app.services.enriched_catalog.template_service import TemplateService


# ---------------------------------------------------------------------------
# Fake MongoDB helpers (same pattern as test_ai_recommendations_repository)
# ---------------------------------------------------------------------------


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeUpdateResult:
    def __init__(self, modified_count: int) -> None:
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        self.index_calls.append({"keys": list(keys), **kwargs})
        return kwargs.get("name", "index")

    def insert_one(self, payload: dict[str, object]):
        stored = dict(payload)
        stored["_id"] = f"id-{len(self.docs) + 1}"
        self.docs.append(stored)
        return type("Res", (), {"inserted_id": stored["_id"]})()

    def find_one(self, query: dict[str, object]):
        for item in self.docs:
            if self._matches(item, query):
                return dict(item)
        return None

    def find(self, query: dict[str, object]):
        return FakeCursor([dict(item) for item in self.docs if self._matches(item, query)])

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        found = None
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                found = dict(item)
                self.docs[idx] = found
                break
        if found is None:
            if not upsert:
                return None
            found = dict(query)
            found["_id"] = f"id-{len(self.docs) + 1}"
            self.docs.append(found)
        for key, value in dict(update.get("$set") or {}).items():
            found[key] = value
        for key, value in dict(update.get("$setOnInsert") or {}).items():
            found.setdefault(key, value)
        return dict(found)

    def update_one(self, query, update, upsert=False):
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                doc = dict(item)
                for key, value in dict(update.get("$set") or {}).items():
                    doc[key] = value
                self.docs[idx] = doc
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    def delete_one(self, query):
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                self.docs.pop(idx)
                return FakeDeleteResult(1)
        return FakeDeleteResult(0)

    def _matches(self, payload, query):
        for key, value in query.items():
            if payload.get(key) != value:
                return False
        return True


class FakeCursor:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items

    def sort(self, keys):
        for key, direction in reversed(keys):
            reverse = int(direction) < 0
            self.items.sort(key=lambda item, k=key: (item.get(k) is None, item.get(k)), reverse=reverse)
        return self

    def limit(self, value: int):
        self.items = self.items[: int(value)]
        return self

    def __iter__(self):
        return iter(self.items)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _patch_mongo(monkeypatch):
    templates_col = FakeCollection()
    treatments_col = FakeCollection()

    def fake_get_collection(name):
        if name == "creative_templates":
            return templates_col
        if name == "treatments":
            return treatments_col
        return None

    monkeypatch.setattr(repository_module, "get_mongo_collection", fake_get_collection)
    # Use deterministic IDs for tests
    counter = {"value": 0}

    def fake_new_id():
        counter["value"] += 1
        return f"test-id-{counter['value']}"

    monkeypatch.setattr(repository_module, "_new_id", fake_new_id)
    return templates_col, treatments_col


# ---------------------------------------------------------------------------
# Tests — template CRUD
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_mongo")
class TestCreateTemplate:
    def test_create_template_with_canvas_elements(self):
        service = TemplateService()
        result = service.create_template(
            subaccount_id=42,
            data={
                "name": "Summer Sale Banner",
                "canvas_width": 1200,
                "canvas_height": 628,
                "elements": [
                    {
                        "type": "text",
                        "position_x": 10,
                        "position_y": 20,
                        "width": 400,
                        "height": 50,
                        "style": {"font_size": 24, "color": "#000000"},
                        "content": "Summer Sale!",
                    },
                    {
                        "type": "dynamic_field",
                        "position_x": 10,
                        "position_y": 80,
                        "width": 400,
                        "height": 30,
                        "dynamic_binding": "{{product_title}}",
                    },
                    {
                        "type": "image",
                        "position_x": 500,
                        "position_y": 20,
                        "width": 300,
                        "height": 300,
                        "dynamic_binding": "{{image_url}}",
                    },
                ],
                "background_color": "#F5F5F5",
            },
        )

        assert result["id"] == "test-id-1"
        assert result["subaccount_id"] == 42
        assert result["name"] == "Summer Sale Banner"
        assert result["canvas_width"] == 1200
        assert result["canvas_height"] == 628
        assert len(result["elements"]) == 3
        assert result["elements"][0]["type"] == "text"
        assert result["elements"][1]["dynamic_binding"] == "{{product_title}}"
        assert result["background_color"] == "#F5F5F5"

    def test_create_template_defaults(self):
        service = TemplateService()
        result = service.create_template(
            subaccount_id=1,
            data={"name": "Minimal"},
        )

        assert result["canvas_width"] == 1080
        assert result["canvas_height"] == 1080
        assert result["background_color"] == "#FFFFFF"
        assert result["elements"] == []


# ---------------------------------------------------------------------------
# Tests — validate dynamic bindings
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_mongo")
class TestValidateDynamicBindings:
    def test_valid_bindings_return_no_errors(self):
        service = TemplateService()
        service.create_template(
            subaccount_id=1,
            data={
                "name": "T1",
                "elements": [
                    {"type": "dynamic_field", "dynamic_binding": "{{product_title}}"},
                    {"type": "dynamic_field", "dynamic_binding": "{{price}}"},
                ],
            },
        )

        errors = service.validate_dynamic_bindings(
            "test-id-1",
            available_fields=["product_title", "price", "image_url"],
        )
        assert errors == []

    def test_missing_field_returns_error(self):
        service = TemplateService()
        service.create_template(
            subaccount_id=1,
            data={
                "name": "T2",
                "elements": [
                    {"type": "dynamic_field", "dynamic_binding": "{{nonexistent_field}}"},
                ],
            },
        )

        errors = service.validate_dynamic_bindings(
            "test-id-1",
            available_fields=["product_title", "price"],
        )
        assert len(errors) == 1
        assert "nonexistent_field" in errors[0]

    def test_template_not_found_raises(self):
        service = TemplateService()
        with pytest.raises(TemplateNotFoundError):
            service.validate_dynamic_bindings("missing-id", available_fields=[])


# ---------------------------------------------------------------------------
# Tests — duplicate template
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_mongo")
class TestDuplicateTemplate:
    def test_duplicate_creates_new_template(self):
        service = TemplateService()
        service.create_template(
            subaccount_id=5,
            data={
                "name": "Original",
                "canvas_width": 800,
                "canvas_height": 600,
                "elements": [{"type": "text", "content": "Hello"}],
            },
        )

        duplicated = service.duplicate_template("test-id-1", "Copy of Original")

        assert duplicated["id"] != "test-id-1"
        assert duplicated["name"] == "Copy of Original"
        assert duplicated["canvas_width"] == 800
        assert len(duplicated["elements"]) == 1

    def test_duplicate_nonexistent_raises(self):
        service = TemplateService()
        with pytest.raises(TemplateNotFoundError):
            service.duplicate_template("no-such-id", "Copy")


# ---------------------------------------------------------------------------
# Tests — preview template
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_mongo")
class TestPreviewTemplate:
    def test_preview_resolves_dynamic_bindings(self):
        service = TemplateService()
        service.create_template(
            subaccount_id=1,
            data={
                "name": "Preview Test",
                "elements": [
                    {"type": "dynamic_field", "dynamic_binding": "{{product_title}}"},
                    {"type": "dynamic_field", "dynamic_binding": "{{price}}"},
                    {"type": "text", "content": "Static text"},
                ],
            },
        )

        preview = service.preview_template(
            "test-id-1",
            sample_product_data={"product_title": "Cool Shoes", "price": "29.99"},
        )

        assert preview["template_id"] == "test-id-1"
        assert preview["rendered_elements"][0]["resolved_value"] == "Cool Shoes"
        assert preview["rendered_elements"][1]["resolved_value"] == "29.99"
        assert "resolved_value" not in preview["rendered_elements"][2]


# ---------------------------------------------------------------------------
# Tests — treatment matching logic
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_mongo")
class TestTreatmentMatching:
    def test_equals_filter_matches(self):
        from app.services.enriched_catalog.repository import treatment_repository

        treatment_repository.create({
            "output_feed_id": "feed-1",
            "name": "Sandals Treatment",
            "template_id": "tpl-1",
            "filters": [{"field_name": "category", "operator": "equals", "value": "Sandals"}],
            "priority": 0,
            "is_default": False,
        })

        result = treatment_repository.get_matching_treatment(
            "feed-1",
            {"category": "Sandals", "price": "49.99"},
        )

        assert result is not None
        assert result["name"] == "Sandals Treatment"

    def test_equals_filter_no_match_falls_to_default(self):
        from app.services.enriched_catalog.repository import treatment_repository

        treatment_repository.create({
            "output_feed_id": "feed-2",
            "name": "Specific",
            "template_id": "tpl-1",
            "filters": [{"field_name": "category", "operator": "equals", "value": "Boots"}],
            "priority": 0,
            "is_default": False,
        })
        treatment_repository.create({
            "output_feed_id": "feed-2",
            "name": "Default",
            "template_id": "tpl-2",
            "filters": [],
            "priority": 10,
            "is_default": True,
        })

        result = treatment_repository.get_matching_treatment(
            "feed-2",
            {"category": "Sneakers"},
        )

        assert result is not None
        assert result["name"] == "Default"

    def test_contains_filter_matches(self):
        from app.services.enriched_catalog.repository import treatment_repository

        treatment_repository.create({
            "output_feed_id": "feed-3",
            "name": "Premium",
            "template_id": "tpl-1",
            "filters": [{"field_name": "title", "operator": "contains", "value": "Premium"}],
            "priority": 0,
            "is_default": False,
        })

        result = treatment_repository.get_matching_treatment(
            "feed-3",
            {"title": "Premium Leather Sandals", "price": "99.99"},
        )

        assert result is not None
        assert result["name"] == "Premium"

    def test_in_list_filter_matches(self):
        from app.services.enriched_catalog.repository import treatment_repository

        treatment_repository.create({
            "output_feed_id": "feed-4",
            "name": "Summer Categories",
            "template_id": "tpl-1",
            "filters": [{"field_name": "category", "operator": "in_list", "value": ["Sandals", "Shorts", "T-Shirts"]}],
            "priority": 0,
            "is_default": False,
        })

        result = treatment_repository.get_matching_treatment(
            "feed-4",
            {"category": "Shorts"},
        )

        assert result is not None
        assert result["name"] == "Summer Categories"

    def test_no_treatments_returns_none(self):
        from app.services.enriched_catalog.repository import treatment_repository

        result = treatment_repository.get_matching_treatment(
            "feed-nonexistent",
            {"category": "Anything"},
        )
        assert result is None
