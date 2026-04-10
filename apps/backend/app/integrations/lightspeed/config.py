"""Lightspeed eCom platform configuration and validation.

Lightspeed connections require Shop ID, Shop Language, and Shop Region
instead of API credentials.  All three are non-sensitive metadata stored
in the ``feed_sources.config`` JSONB column — no encrypted credential
storage is needed.
"""

from __future__ import annotations

from app.integrations.generic_api_key.config import validate_store_url  # noqa: F401 — re-export

LIGHTSPEED_REGIONS: tuple[str, ...] = ("eu1", "us1")


def validate_shop_id(raw: str) -> str:
    """Return a trimmed, non-empty Shop ID or raise ``ValueError``."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("Shop ID is required")
    return cleaned


def validate_shop_region(raw: str) -> str:
    """Return a valid Lightspeed region or raise ``ValueError``."""
    cleaned = (raw or "").strip().lower()
    if cleaned not in LIGHTSPEED_REGIONS:
        raise ValueError(
            f"Invalid shop region: {raw!r}. Must be one of {', '.join(LIGHTSPEED_REGIONS)}"
        )
    return cleaned
