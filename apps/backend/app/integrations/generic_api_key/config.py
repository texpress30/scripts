"""Per-platform metadata for the generic API-key integration.

Each :class:`PlatformDefinition` describes one of the six "URL + API key"
e-commerce platforms we support without a dedicated connector. The
shared CRUD router (``router.py``) and service layer
(``service.py``) read these definitions to build the right endpoint
prefix, validate the platform identifier, and decide whether the
platform exposes a secondary API secret field.

Adding a 7th platform = one new entry in :data:`PLATFORM_DEFINITIONS`
plus a single ``app.include_router(...)`` line in ``main.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.services.feed_management.models import FeedSourceType


@dataclass(frozen=True)
class PlatformDefinition:
    """Metadata for one generic-API-key e-commerce platform.

    Fields
    ------
    key:
        Lowercase identifier — matches the URL prefix
        (``/integrations/{key}/sources``) and the
        :class:`FeedSourceType` enum value.
    display_name:
        Human-readable name shown in audit log entries and error
        messages. The frontend pulls a separate copy from
        ``SourceTypeSelector.tsx`` for the wizard cards (so we don't
        couple frontend strings to backend code).
    feed_source_type:
        The :class:`FeedSourceType` enum value persisted on the
        ``feed_sources`` row.
    has_api_secret:
        Some platforms only need an API key (PrestaShop, Volusion);
        others mint a key+secret pair (Shopware, Lightspeed). The
        boolean drives both schema validation and the optional ``secret``
        column in :func:`service.store_credentials`.
    api_key_label / api_secret_label:
        Display labels (Romanian) used in error messages.
    """

    key: str
    display_name: str
    feed_source_type: FeedSourceType
    has_api_secret: bool = False
    api_key_label: str = "API Key"
    api_secret_label: str = "API Secret"
    extra: dict[str, Any] = field(default_factory=dict)


PLATFORM_DEFINITIONS: dict[str, PlatformDefinition] = {
    "prestashop": PlatformDefinition(
        key="prestashop",
        display_name="PrestaShop",
        feed_source_type=FeedSourceType.prestashop,
        has_api_secret=False,
        api_key_label="Webservice Key",
    ),
    "opencart": PlatformDefinition(
        key="opencart",
        display_name="OpenCart",
        feed_source_type=FeedSourceType.opencart,
        has_api_secret=False,
        api_key_label="Store Key",
    ),
    "shopware": PlatformDefinition(
        key="shopware",
        display_name="Shopware",
        feed_source_type=FeedSourceType.shopware,
        has_api_secret=True,
        api_key_label="Integration Access Key",
        api_secret_label="Integration Secret Key",
    ),
    "volusion": PlatformDefinition(
        key="volusion",
        display_name="Volusion",
        feed_source_type=FeedSourceType.volusion,
        has_api_secret=False,
        api_key_label="API Key",
    ),
    "cart_storefront": PlatformDefinition(
        key="cart_storefront",
        display_name="Cart Storefront",
        feed_source_type=FeedSourceType.cart_storefront,
        has_api_secret=False,
        api_key_label="Authorization Token",
    ),
}


def get_platform(key: str) -> PlatformDefinition:
    """Look up a platform definition or raise ``ValueError``."""
    cleaned = (key or "").strip().lower()
    if cleaned not in PLATFORM_DEFINITIONS:
        raise ValueError(
            f"Unknown generic-API-key platform: {key!r}. "
            f"Known: {', '.join(sorted(PLATFORM_DEFINITIONS))}"
        )
    return PLATFORM_DEFINITIONS[cleaned]


def validate_store_url(raw: str) -> str:
    """Validate + normalise a store URL.

    Returns ``scheme://host[:port][/path]`` with no trailing slash, or
    raises ``ValueError`` for inputs that aren't a real http(s) URL.
    """
    if not raw or not raw.strip():
        raise ValueError("Store URL is required")

    cleaned = raw.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid store URL scheme: {parsed.scheme!r} (expected http or https)"
        )
    if not parsed.netloc:
        raise ValueError(f"Invalid store URL (missing host): {raw!r}")

    path = (parsed.path or "").rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"
