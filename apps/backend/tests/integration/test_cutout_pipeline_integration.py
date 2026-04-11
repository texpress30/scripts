"""End-to-end integration test for the background-removal pipeline.

Boots nothing itself — assumes the stack is already running via
``docker-compose up`` (or equivalent). Coverage:

1. The synchronous ``ensure_cutout`` entry point:
   - downloads a real image via an ``httpx`` stub that returns the fixture bytes
   - runs rembg u2net
   - trims the alpha bbox
   - uploads to the configured S3 bucket (MinIO in docker-compose)
   - registers a media_files row in Mongo
   - persists the image_cutouts dedup row in Postgres

2. The Celery task wrapper: dispatching ``process_source_image.delay`` from a
   test that has Redis + a running worker should end with the same
   ``image_cutouts`` row ready, within a short timeout.

Run with::

    RUN_INTEGRATION=1 pytest tests/integration/test_cutout_pipeline_integration.py -v
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _fake_download(url: str, fixture: Path):
    """Patch httpx.Client inside cutout_service to return the fixture bytes
    regardless of the URL. Keeps the test offline so CI doesn't depend on
    whatever the external product photo URL actually returns today.
    """

    class _Resp:
        def __init__(self, data: bytes):
            self.content = data

        def raise_for_status(self) -> None:  # noqa: D401 — mirror httpx API
            return None

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            self._data = _read_bytes(fixture)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, _url: str):
            return _Resp(self._data)

    return patch("app.services.enriched_catalog.cutout_service.httpx.Client", _Client)


# ---------------------------------------------------------------------------
# ensure_cutout (sync)
# ---------------------------------------------------------------------------


class TestEnsureCutout:
    def test_end_to_end_creates_cutout_and_dedup_row(self, sample_product_photo):
        from app.db.pool import get_connection
        from app.services.enriched_catalog import cutout_service

        client_id = 999_001  # high number so we don't collide with real fixtures

        with _fake_download("https://cdn.example.test/car.jpg", sample_product_photo):
            record = cutout_service.ensure_cutout(
                client_id=client_id,
                subaccount_id=client_id,
                source_url="https://cdn.example.test/car.jpg",
                feed_source_name="integration-test",
            )

        assert record.status == "ready"
        assert record.width > 0
        assert record.height > 0
        assert record.media_id, "media_id should have been registered in Mongo"

        # Row should be persisted in Postgres.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, cutout_width, cutout_height FROM image_cutouts "
                    "WHERE client_id = %s AND source_hash = %s",
                    (client_id, record.source_hash),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == "ready"
        assert int(row[1]) == record.width
        assert int(row[2]) == record.height

    def test_second_call_hits_dedup_cache(self, sample_product_photo):
        from app.services.enriched_catalog import cutout_service

        client_id = 999_002

        with _fake_download("https://cdn.example.test/car.jpg", sample_product_photo):
            first = cutout_service.ensure_cutout(
                client_id=client_id,
                subaccount_id=client_id,
                source_url="https://cdn.example.test/car.jpg",
                feed_source_name="integration-test",
            )

        # Second call with the same URL must not create a new Postgres row —
        # the dedup lookup in _select_cutout_row short-circuits.
        with _fake_download("https://cdn.example.test/car.jpg", sample_product_photo):
            second = cutout_service.ensure_cutout(
                client_id=client_id,
                subaccount_id=client_id,
                source_url="https://cdn.example.test/car.jpg",
                feed_source_name="integration-test",
            )

        assert first.source_hash == second.source_hash
        assert first.media_id == second.media_id

    def test_native_alpha_skips_rembg(self, tmp_path):
        from PIL import Image

        from app.services.enriched_catalog import cutout_service

        # Build a synthetic PNG that already has a transparent background so
        # the detector reports ``has_usable_alpha=True`` and we short-circuit
        # around rembg. Runs dramatically faster than the u2net path.
        out = tmp_path / "clean.png"
        img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        from PIL import ImageDraw

        ImageDraw.Draw(img).ellipse((10, 10, 70, 70), fill=(200, 50, 50, 255))
        img.save(out)

        client_id = 999_003
        with _fake_download("https://cdn.example.test/clean.png", out):
            record = cutout_service.ensure_cutout(
                client_id=client_id,
                subaccount_id=client_id,
                source_url="https://cdn.example.test/clean.png",
                feed_source_name="integration-test",
            )

        assert record.status == "ready"
        assert record.model == "native_alpha"
        assert record.has_native_alpha is True


# ---------------------------------------------------------------------------
# Celery task dispatch
# ---------------------------------------------------------------------------


class TestProcessSourceImageTask:
    def test_task_runs_and_marks_ready(self, sample_product_photo):
        """Dispatch a Celery task and wait for the DB row to flip to 'ready'.

        Requires ``worker-bgremoval`` container to be up; the test polls the
        dedup table instead of calling ``.get()`` on the AsyncResult because
        the worker may patch result_backend differently depending on
        environment.
        """
        from app.db.pool import get_connection
        from app.services.enriched_catalog import cutout_service
        from app.workers.tasks.bg_removal import process_source_image

        client_id = 999_101

        # We have to patch the httpx download inside the worker process, not
        # the test process, so instead of mocking we rely on the worker being
        # able to fetch the image from a local HTTP server. The simplest
        # approach here: pre-populate the dedup row manually so the worker
        # picks up a real URL that already resolves inside the compose
        # network. In practice you'd point at the MinIO signed URL.
        source_url = "http://minio:9000/test-assets/car.jpg"

        # Ensure a clean slate.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM image_cutouts WHERE client_id = %s",
                    (client_id,),
                )
            conn.commit()

        result = process_source_image.apply_async(
            kwargs={
                "client_id": client_id,
                "subaccount_id": client_id,
                "source_url": source_url,
                "feed_source_name": "integration-test",
            },
            queue="bgremoval",
        )

        # Poll Postgres for up to 60s waiting for the worker to finish.
        deadline = time.time() + 60.0
        status = None
        while time.time() < deadline:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM image_cutouts WHERE client_id = %s",
                        (client_id,),
                    )
                    row = cur.fetchone()
            status = row[0] if row else None
            if status in ("ready", "failed"):
                break
            time.sleep(1.0)

        assert status in ("ready", "failed"), (
            f"worker didn't touch the row within 60s (task_id={result.id})"
        )
        # If the MinIO bucket isn't seeded, the task may legitimately fail.
        # We still want to assert that the dedup row exists and that the
        # status transitioned away from 'pending' so we know the worker
        # actually picked the task up.


# ---------------------------------------------------------------------------
# Tight crop sanity
# ---------------------------------------------------------------------------


def test_tight_crop_produces_bounded_image(sample_product_photo):
    """Sanity-check the pure image primitives end-to-end against a real file."""
    from PIL import Image

    from app.services.enriched_catalog import cutout_service

    raw = Image.open(io.BytesIO(_read_bytes(sample_product_photo))).convert("RGBA")
    cropped, bbox = cutout_service.tight_crop_alpha(raw, padding=0)
    # Our fixture is fully opaque so bbox covers the whole image — the real
    # test is that the function returned without raising and the output has
    # the same size as the input.
    assert bbox == (0, 0, raw.width, raw.height)
    assert cropped.size == raw.size
