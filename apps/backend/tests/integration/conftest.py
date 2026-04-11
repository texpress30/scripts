"""Shared fixtures for integration tests.

These tests require the full dev stack (Postgres, Redis, Celery workers,
MinIO/S3, and rembg with the u2net ONNX weights) running locally via
``docker-compose up``. We also honor ``SKIP_INTEGRATION=1`` so CI that
hasn't provisioned the stack can skip the entire directory without
erroring out.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when the stack isn't available.

    We skip unless the user explicitly opted in via ``RUN_INTEGRATION=1`` so
    running ``pytest tests/`` locally doesn't blow up for developers who
    haven't booted Celery.
    """
    if os.environ.get("RUN_INTEGRATION"):
        return
    skip = pytest.mark.skip(
        reason="integration tests require RUN_INTEGRATION=1 and a live docker-compose stack"
    )
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_product_photo(fixtures_dir: Path, tmp_path_factory) -> Path:
    """Return a tiny synthetic product photo (car silhouette on a solid
    background) saved to a temp dir, suitable for feeding rembg.

    We generate it on the fly instead of shipping a binary so the repo stays
    small and the fixture works regardless of the platform.
    """
    from PIL import Image, ImageDraw

    out = tmp_path_factory.mktemp("cutout") / "car.jpg"
    img = Image.new("RGB", (320, 200), (30, 120, 40))  # grass background
    draw = ImageDraw.Draw(img)
    # Very rough "car" — two stacked rectangles so rembg has edges to find.
    draw.rectangle((40, 110, 280, 170), fill=(80, 80, 80))  # body
    draw.rectangle((80, 70, 240, 120), fill=(60, 60, 60))  # cabin
    draw.ellipse((60, 150, 110, 190), fill=(15, 15, 15))  # wheel 1
    draw.ellipse((210, 150, 260, 190), fill=(15, 15, 15))  # wheel 2
    img.save(out, format="JPEG", quality=85)
    return out
