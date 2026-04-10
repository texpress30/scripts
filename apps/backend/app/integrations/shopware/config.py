"""Shopware platform configuration and validation.

Shopware connections require Store Key, Bridge Endpoint, and API Access
Key — obtained from the Shopware connector extension.  Store Key and
API Access Key are credentials (encrypted at rest), Bridge Endpoint is
a non-sensitive URL stored in config JSONB.
"""

from __future__ import annotations

from app.integrations.generic_api_key.config import validate_store_url  # noqa: F401 — re-export


def validate_bridge_endpoint(raw: str) -> str:
    """Return a trimmed, non-empty Bridge Endpoint or raise ``ValueError``."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("Bridge Endpoint is required")
    return cleaned
