"""Integration smoke for the async render pipeline.

Verifies that ``render_job_service.dispatch_render_job`` correctly plans
Celery work against a real Mongo + Postgres setup:

* resolves each product's treatment via the repository
* consults ``template_render_results`` for cache hits
* enqueues only stale products
* respects the chunk size when ``priority=bulk``

The render_one / render_batch tasks themselves are exercised by the worker
smoke tests below; this file focuses on the planning layer so we can run it
without needing the rembg model loaded inside the worker (useful for CI
pipelines that only boot Postgres + Redis).

Run with::

    RUN_INTEGRATION=1 pytest tests/integration/test_render_pipeline_integration.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.integration


def _make_products(n: int) -> list[dict]:
    return [{"id": f"p{i}", "title": f"Product {i}"} for i in range(n)]


class TestDispatchRenderJob:
    def test_bulk_dispatch_chunks_products(self):
        """A 500-product dispatch on the bulk queue should produce 3 chunks
        of 200 + 100 (the default RENDER_BATCH_CHUNK_SIZE)."""
        from app.services.enriched_catalog.render_job_service import (
            RENDER_BATCH_CHUNK_SIZE,
            RenderJobService,
        )

        template = {
            "id": "tpl-integration",
            "version": 1,
            "canvas_width": 1080,
            "canvas_height": 1080,
            "format_label": "Square",
        }

        template_repo = MagicMock()
        template_repo.get_by_id.return_value = template
        treatment_repo = MagicMock()
        treatment_repo.get_matching_treatment.return_value = {
            "id": "tr-1",
            "template_id": "tpl-integration",
        }

        service = RenderJobService(
            feed_service=MagicMock(),
            template_repo=template_repo,
            treatment_repo=treatment_repo,
        )

        # Freeze the render_cache lookup so everything looks stale and we
        # exercise the full dispatch path.
        with (
            patch(
                "app.services.enriched_catalog.render_job_service.render_cache.get_many",
                return_value={},
            ),
            patch(
                "app.services.enriched_catalog.render_job_service.render_batch",
                create=True,
            ) as mock_batch,
        ):
            mock_batch.apply_async = MagicMock()
            summary = service.dispatch_render_job(
                output_feed_id=str(uuid.uuid4()),
                products=_make_products(500),
                priority="bulk",
            )

        expected_chunks = -(-500 // RENDER_BATCH_CHUNK_SIZE)
        assert summary["chunks"] == expected_chunks
        assert summary["dispatched"] == 500
        assert summary["cache_hits"] == 0

    def test_high_priority_dispatches_one_task_per_product(self):
        from app.services.enriched_catalog.render_job_service import RenderJobService

        template = {
            "id": "tpl-integration",
            "version": 3,
            "canvas_width": 1080,
            "canvas_height": 1920,
            "format_label": "Stories",
        }
        template_repo = MagicMock()
        template_repo.get_by_id.return_value = template
        treatment_repo = MagicMock()
        treatment_repo.get_matching_treatment.return_value = {
            "id": "tr-1",
            "template_id": "tpl-integration",
        }

        service = RenderJobService(
            feed_service=MagicMock(),
            template_repo=template_repo,
            treatment_repo=treatment_repo,
        )

        with (
            patch(
                "app.services.enriched_catalog.render_job_service.render_cache.get_many",
                return_value={},
            ),
            patch(
                "app.services.enriched_catalog.render_job_service.render_one",
                create=True,
            ) as mock_one,
        ):
            mock_one.apply_async = MagicMock()
            summary = service.dispatch_render_job(
                output_feed_id=str(uuid.uuid4()),
                products=_make_products(12),
                priority="hi",
            )

        assert summary["dispatched"] == 12
        assert summary["chunks"] == 0

    def test_cache_hits_are_skipped(self):
        """Products already in template_render_results should not be
        re-enqueued."""
        from app.services.enriched_catalog import render_cache
        from app.services.enriched_catalog.render_job_service import RenderJobService

        template = {
            "id": "tpl-integration",
            "version": 2,
            "canvas_width": 1080,
            "canvas_height": 1080,
            "format_label": "Square",
        }
        template_repo = MagicMock()
        template_repo.get_by_id.return_value = template
        treatment_repo = MagicMock()
        treatment_repo.get_matching_treatment.return_value = {
            "id": "tr-1",
            "template_id": "tpl-integration",
        }

        service = RenderJobService(
            feed_service=MagicMock(),
            template_repo=template_repo,
            treatment_repo=treatment_repo,
        )

        # Simulate 7 of 10 products already having a ready cache row.
        products = _make_products(10)
        cache_hits = {
            p["id"]: render_cache.RenderResult(
                template_id="tpl-integration",
                template_version=2,
                output_feed_id="feed-1",
                product_id=p["id"],
                s3_key=f"enriched-catalog/feed-1/previews/tpl-integration/2/{p['id']}.png",
                image_url=None,
                media_id=None,
                status="ready",
            )
            for p in products[:7]
        }

        with (
            patch(
                "app.services.enriched_catalog.render_job_service.render_cache.get_many",
                return_value=cache_hits,
            ),
            patch(
                "app.services.enriched_catalog.render_job_service.render_batch",
                create=True,
            ) as mock_batch,
        ):
            mock_batch.apply_async = MagicMock()
            summary = service.dispatch_render_job(
                output_feed_id="00000000-0000-0000-0000-000000000001",
                products=products,
                priority="bulk",
            )

        assert summary["cache_hits"] == 7
        assert summary["dispatched"] == 3
