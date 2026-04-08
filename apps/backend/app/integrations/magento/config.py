"""Magento 2 Feed Integration configuration (OAuth 1.0a Integration tokens)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_BASE_URL_SCHEMES = {"https", "http"}
_STORE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$", re.IGNORECASE)

DEFAULT_STORE_CODE = "default"
DEFAULT_API_VERSION = "V1"


def validate_magento_base_url(raw: str) -> str:
    """Validate and normalise a Magento base URL.

    Returns the cleaned URL (``scheme://host[:port][/subpath]``, no trailing
    slash) or raises ``ValueError``. Requires ``https`` in production but
    accepts ``http`` for local dev stores (``*.test``, ``localhost``).
    """
    if not raw or not raw.strip():
        raise ValueError("Magento base URL is required")

    cleaned = raw.strip()
    parsed = urlparse(cleaned)

    if parsed.scheme not in _BASE_URL_SCHEMES:
        raise ValueError(
            f"Invalid Magento base URL scheme: {parsed.scheme!r} (expected http or https)"
        )

    if not parsed.netloc:
        raise ValueError(f"Invalid Magento base URL (missing host): {raw!r}")

    host = parsed.hostname or ""
    if parsed.scheme == "http" and not (
        host in ("localhost", "127.0.0.1")
        or host.endswith(".test")
        or host.endswith(".local")
    ):
        raise ValueError("HTTP is only allowed for localhost/.test/.local dev stores")

    # Strip trailing slash from path so downstream URL joins are predictable.
    path = (parsed.path or "").rstrip("/")
    netloc = parsed.netloc
    return f"{parsed.scheme}://{netloc}{path}"


def validate_magento_store_code(raw: str | None) -> str:
    """Validate a Magento store code (`default`, `en`, `us_store_1`, etc.)."""
    value = (raw or "").strip() or DEFAULT_STORE_CODE
    if not _STORE_CODE_RE.match(value):
        raise ValueError(
            f"Invalid Magento store code {value!r}: must match [a-z0-9][a-z0-9_-]*"
        )
    return value


def get_magento_api_base_url(base_url: str, *, store_code: str = DEFAULT_STORE_CODE) -> str:
    """Return the versioned REST endpoint for a Magento store.

    Example: ``https://store.example.com/rest/default/V1``
    """
    clean = validate_magento_base_url(base_url)
    code = validate_magento_store_code(store_code)
    return f"{clean}/rest/{code}/{DEFAULT_API_VERSION}"
