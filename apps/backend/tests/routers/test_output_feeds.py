from __future__ import annotations

import pytest

from app.api import output_feeds as output_feeds_api
from app.api import treatments as treatments_api
from app.services.auth import AuthUser
from app.services.enriched_catalog import repository as repository_module
from app.services.enriched_catalog.models import TreatmentCreate
from app.services.enriched_catalog.output_feed_service import OutputFeedService


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeUpdateResult:
    def __init__(self, modified_count: int) -> None:
        self.modified_count = modified_count


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

    def update_one(self, query, update, upsert=False):
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                doc = dict(item)
                for key, value in dict(update.get("$set") or {}).items():
                    doc[key] = value
                self.docs[idx] = doc
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

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


class FakeOutputFeedRepository:
    def __init__(self) -> None:
        self.feeds: list[dict[str, object]] = []
        self.jobs: list[dict[str, object]] = []
        self._counter = 0
        self._job_counter = 0

    def create_output_feed(self, *, subaccount_id, name, feed_source_id=None):
        self._counter += 1
        doc = {"id": f"feed-{self._counter}", "subaccount_id": int(subaccount_id), "name": str(name), "feed_source_id": feed_source_id, "status": "draft", "enriched_feed_url": None, "last_render_at": None, "created_at": "2026-04-01T00:00:00+00:00", "updated_at": "2026-04-01T00:00:00+00:00"}
        self.feeds.append(doc)
        return dict(doc)

    def get_by_id(self, output_feed_id):
        for f in self.feeds:
            if f["id"] == output_feed_id:
                return dict(f)
        return None

    def list_by_subaccount(self, subaccount_id, *, limit=100):
        return [dict(f) for f in self.feeds if f["subaccount_id"] == int(subaccount_id)][:limit]

    def update(self, output_feed_id, data):
        for idx, f in enumerate(self.feeds):
            if f["id"] == output_feed_id:
                updated = dict(f)
                for k, v in data.items():
                    if v is not None:
                        updated[k] = v
                self.feeds[idx] = updated
                return dict(updated)
        return None

    def delete(self, output_feed_id):
        for idx, f in enumerate(self.feeds):
            if f["id"] == output_feed_id:
                self.feeds.pop(idx)
                return True
        return False

    def create_render_job(self, *, template_id, output_feed_id, total_products=0):
        self._job_counter += 1
        doc = {"id": f"job-{self._job_counter}", "template_id": template_id, "output_feed_id": output_feed_id, "status": "pending", "total_products": total_products, "rendered_products": 0, "errors": [], "started_at": "2026-04-01T00:00:00+00:00", "completed_at": None, "created_at": "2026-04-01T00:00:00+00:00"}
        self.jobs.append(doc)
        return dict(doc)

    def get_latest_render_job(self, output_feed_id):
        matching = [j for j in self.jobs if j["output_feed_id"] == output_feed_id]
        return dict(matching[-1]) if matching else None


def _admin_user() -> AuthUser:
    return AuthUser(email="owner@example.com", role="agency_admin")


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    treatments_col = FakeCollection()
    templates_col = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda name: treatments_col if name == "treatments" else templates_col if name == "creative_templates" else None)
    counter = {"value": 0}
    def fake_new_id():
        counter["value"] += 1
        return f"treat-{counter['value']}"
    monkeypatch.setattr(repository_module, "_new_id", fake_new_id)
    fake_repo = FakeOutputFeedRepository()
    fake_service = OutputFeedService(repo=fake_repo)
    monkeypatch.setattr(output_feeds_api, "output_feed_service", fake_service)
    monkeypatch.setattr(treatments_api, "output_feed_service", fake_service)
    monkeypatch.setattr(output_feeds_api, "enforce_subaccount_action", lambda **_kwargs: None)
    monkeypatch.setattr(treatments_api, "enforce_subaccount_action", lambda **_kwargs: None)


class TestOutputFeedCRUD:
    def test_create_output_feed(self):
        created = output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="My Feed", feed_source_id="src-1"), subaccount_id=42, user=_admin_user())
        assert created["id"] == "feed-1"
        assert created["name"] == "My Feed"
        assert created["subaccount_id"] == 42
        assert created["status"] == "draft"

    def test_list_output_feeds(self):
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="A"), subaccount_id=10, user=_admin_user())
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="B"), subaccount_id=10, user=_admin_user())
        assert len(output_feeds_api.list_output_feeds(subaccount_id=10, user=_admin_user())["items"]) == 2

    def test_get_output_feed_includes_treatments(self):
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="Feed"), subaccount_id=1, user=_admin_user())
        treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="Default", template_id="tpl-1", output_feed_id="feed-1", is_default=True), user=_admin_user())
        feed = output_feeds_api.get_output_feed(output_feed_id="feed-1", user=_admin_user())
        assert len(feed["treatments"]) == 1
        assert feed["treatments"][0]["name"] == "Default"


class TestTreatmentsWithFilters:
    def test_create_treatment_with_filters(self):
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="Feed"), subaccount_id=1, user=_admin_user())
        created = treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="Sandals Only", template_id="tpl-sandals", output_feed_id="feed-1", filters=[{"field_name": "category", "operator": "equals", "value": "Sandals"}]), user=_admin_user())
        assert created["name"] == "Sandals Only"
        assert len(created["filters"]) == 1

    def test_treatment_matching_category_equals(self):
        from app.services.enriched_catalog.repository import treatment_repository
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="Feed"), subaccount_id=1, user=_admin_user())
        treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="Sandals Treatment", template_id="tpl-sandals", output_feed_id="feed-1", filters=[{"field_name": "category", "operator": "equals", "value": "Sandals"}], priority=0), user=_admin_user())
        treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="Default", template_id="tpl-default", output_feed_id="feed-1", is_default=True, priority=10), user=_admin_user())
        match = treatment_repository.get_matching_treatment("feed-1", {"category": "Sandals", "price": "49.99"})
        assert match is not None and match["name"] == "Sandals Treatment"
        fallback = treatment_repository.get_matching_treatment("feed-1", {"category": "Boots"})
        assert fallback is not None and fallback["name"] == "Default"

    def test_list_and_delete_treatments(self):
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="Feed"), subaccount_id=1, user=_admin_user())
        treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="T1", template_id="tpl-1", output_feed_id="feed-1"), user=_admin_user())
        treatments_api.create_treatment(output_feed_id="feed-1", payload=TreatmentCreate(name="T2", template_id="tpl-2", output_feed_id="feed-1"), user=_admin_user())
        assert len(treatments_api.list_treatments(output_feed_id="feed-1", user=_admin_user())["items"]) == 2
        treatments_api.delete_treatment(treatment_id="treat-1", user=_admin_user())
        assert len(treatments_api.list_treatments(output_feed_id="feed-1", user=_admin_user())["items"]) == 1


class _FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


class TestRenderJob:
    def test_start_render_and_check_status(self):
        output_feeds_api.create_output_feed(payload=output_feeds_api.CreateOutputFeedRequest(name="Feed"), subaccount_id=1, user=_admin_user())
        bg = _FakeBackgroundTasks()
        job = output_feeds_api.start_render(output_feed_id="feed-1", payload=output_feeds_api.StartRenderRequest(template_id="tpl-1", products=[{"id": "p1"}] * 100), background_tasks=bg, user=_admin_user())
        assert job["id"] == "job-1"
        assert job["status"] == "pending"
        assert job["total_products"] == 100
        assert len(bg.tasks) == 1
        status_result = output_feeds_api.get_render_status(output_feed_id="feed-1", user=_admin_user())
        assert status_result["id"] == "job-1"
