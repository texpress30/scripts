from __future__ import annotations

import pytest

from app.api import creative_templates as templates_api
from app.services.auth import AuthUser
from app.services.enriched_catalog import repository as repository_module
from app.services.enriched_catalog.models import CreativeTemplateCreate, CreativeTemplateUpdate


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        return kwargs.get("name", "index")

    def insert_one(self, payload):
        stored = dict(payload)
        stored["_id"] = f"id-{len(self.docs) + 1}"
        self.docs.append(stored)
        return type("Res", (), {"inserted_id": stored["_id"]})()

    def find_one(self, query):
        for item in self.docs:
            if self._matches(item, query):
                return dict(item)
        return None

    def find(self, query):
        return FakeCursor([dict(item) for item in self.docs if self._matches(item, query)])

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                found = dict(item)
                for key, value in dict(update.get("$set") or {}).items():
                    found[key] = value
                self.docs[idx] = found
                return dict(found)
        return None

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
    def __init__(self, items):
        self.items = items

    def sort(self, keys):
        for key, direction in reversed(keys):
            reverse = int(direction) < 0
            self.items.sort(key=lambda item, k=key: (item.get(k) is None, item.get(k)), reverse=reverse)
        return self

    def limit(self, value):
        self.items = self.items[: int(value)]
        return self

    def __iter__(self):
        return iter(self.items)


def _admin_user() -> AuthUser:
    return AuthUser(email="owner@example.com", role="agency_admin")


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    templates_col = FakeCollection()
    treatments_col = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda name: templates_col if name == "creative_templates" else treatments_col if name == "treatments" else None)
    counter = {"value": 0}
    def fake_new_id():
        counter["value"] += 1
        return f"tpl-{counter['value']}"
    monkeypatch.setattr(repository_module, "_new_id", fake_new_id)
    monkeypatch.setattr(templates_api, "enforce_subaccount_action", lambda **_kwargs: None)


class TestTemplatesCRUD:
    def test_create_and_get_template(self):
        created = templates_api.create_template(payload=CreativeTemplateCreate(name="Banner Ad", canvas_width=1200, canvas_height=628, background_color="#FF0000"), subaccount_id=42, user=_admin_user())
        assert created["id"] == "tpl-1"
        assert created["name"] == "Banner Ad"
        assert created["subaccount_id"] == 42
        fetched = templates_api.get_template(template_id="tpl-1", user=_admin_user())
        assert fetched["name"] == "Banner Ad"

    def test_list_templates(self):
        templates_api.create_template(payload=CreativeTemplateCreate(name="T1"), subaccount_id=10, user=_admin_user())
        templates_api.create_template(payload=CreativeTemplateCreate(name="T2"), subaccount_id=10, user=_admin_user())
        templates_api.create_template(payload=CreativeTemplateCreate(name="T3"), subaccount_id=99, user=_admin_user())
        result = templates_api.list_templates(subaccount_id=10, user=_admin_user())
        assert len(result["items"]) == 2

    def test_update_template(self):
        templates_api.create_template(payload=CreativeTemplateCreate(name="Original"), subaccount_id=1, user=_admin_user())
        updated = templates_api.update_template(template_id="tpl-1", payload=CreativeTemplateUpdate(name="Updated Name", canvas_width=800), user=_admin_user())
        assert updated["name"] == "Updated Name"
        assert updated["canvas_width"] == 800

    def test_delete_template(self):
        templates_api.create_template(payload=CreativeTemplateCreate(name="ToDelete"), subaccount_id=1, user=_admin_user())
        result = templates_api.delete_template(template_id="tpl-1", user=_admin_user())
        assert result["status"] == "ok"
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            templates_api.get_template(template_id="tpl-1", user=_admin_user())
        assert exc_info.value.status_code == 404

    def test_get_nonexistent_returns_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            templates_api.get_template(template_id="nonexistent", user=_admin_user())
        assert exc_info.value.status_code == 404


class TestTemplateDuplicate:
    def test_duplicate_template(self):
        templates_api.create_template(payload=CreativeTemplateCreate(name="Original", canvas_width=1080), subaccount_id=5, user=_admin_user())
        duplicated = templates_api.duplicate_template(template_id="tpl-1", payload=templates_api.DuplicateTemplateRequest(new_name="Copy"), user=_admin_user())
        assert duplicated["id"] != "tpl-1"
        assert duplicated["name"] == "Copy"
        assert duplicated["canvas_width"] == 1080


class TestTemplatePreview:
    def test_preview_resolves_dynamic_fields(self):
        from app.services.enriched_catalog.models import CanvasElement
        templates_api.create_template(
            payload=CreativeTemplateCreate(name="Dynamic", elements=[
                CanvasElement(type="dynamic_field", dynamic_binding="{{product_title}}"),
                CanvasElement(type="dynamic_field", dynamic_binding="{{price}}"),
                CanvasElement(type="text", content="Static"),
            ]),
            subaccount_id=1, user=_admin_user(),
        )
        preview = templates_api.preview_template(
            template_id="tpl-1",
            payload=templates_api.PreviewTemplateRequest(product_data={"product_title": "Cool Shoes", "price": "29.99"}),
            user=_admin_user(),
        )
        assert preview["rendered_elements"][0]["resolved_value"] == "Cool Shoes"
        assert preview["rendered_elements"][1]["resolved_value"] == "29.99"
        assert "resolved_value" not in preview["rendered_elements"][2]
