from __future__ import annotations

import abc
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


def strip_html(text: str | None) -> str:
    """Remove HTML tags and decode entities, preserving text structure.

    - Replaces block-level closing tags (</p>, </div>, </li>, <br>) with
      newlines so paragraph structure is kept.
    - Strips all remaining HTML tags.
    - Decodes HTML entities (&amp; → &).
    - Normalises whitespace within lines and collapses blank lines.
    """
    if not text:
        return ""
    s = str(text)
    # Block-level breaks → newline
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", s, flags=re.IGNORECASE)
    # Strip remaining tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Decode entities
    s = unescape(s)
    # Normalise inline whitespace (preserve newlines)
    s = re.sub(r"[^\S\n]+", " ", s)
    # Collapse multiple blank lines
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    # Trim each line + global
    s = "\n".join(line.strip() for line in s.splitlines())
    return s.strip()


# ---------------------------------------------------------------------------
# Image flattening
# ---------------------------------------------------------------------------

MAX_FEED_IMAGES = 20

DEFAULT_IMAGE_TAG_RULES: list[dict[str, Any]] = [
    {"range": [0, 0], "tag": "Față"},
    {"range": [1, 1], "tag": "Spate"},
    {"range": [2, 3], "tag": "Lateral"},
    {"default": "Interior"},
]


def flatten_images(raw: dict[str, Any], tag_rules: list[dict[str, Any]] | None = None) -> None:
    """Flatten ``images`` array into indexed ``image_N_url`` + ``image_N_tag`` fields.

    Modifies *raw* in place.  The original ``images`` array is kept intact.
    """
    images = raw.get("images")
    if not images or not isinstance(images, list):
        return

    rules = tag_rules or DEFAULT_IMAGE_TAG_RULES
    default_tag = "Față"
    for rule in rules:
        if "default" in rule:
            default_tag = rule["default"]

    count = 0
    for i, img_url in enumerate(images[:MAX_FEED_IMAGES]):
        if not img_url or not isinstance(img_url, str):
            continue
        raw[f"image_{i}_url"] = img_url
        tag = default_tag
        for rule in rules:
            if "range" in rule:
                start, end = rule["range"]
                if start <= i <= end:
                    tag = rule["tag"]
                    break
        raw[f"image_{i}_tag"] = tag
        count += 1

    raw["image_count"] = count


class ProductVariant(BaseModel):
    sku: str = ""
    title: str = ""
    price: float = 0.0
    compare_at_price: float | None = None
    inventory_quantity: int = 0


class ProductData(BaseModel):
    """Standardised product representation across all platform connectors."""
    id: str
    title: str
    description: str = ""
    price: float = 0.0
    compare_at_price: float | None = None
    currency: str = "USD"
    images: list[str] = Field(default_factory=list)
    variants: list[ProductVariant] = Field(default_factory=list)
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    inventory_quantity: int = 0
    sku: str = ""
    url: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    message: str
    details: dict[str, Any] | None = None


class BaseConnector(abc.ABC):
    """Abstract base class that every feed connector must implement."""

    def __init__(self, config: dict[str, Any], credentials: dict[str, str] | None = None) -> None:
        self.config = config
        self.credentials = credentials or {}

    @abc.abstractmethod
    async def validate_config(self) -> ValidationResult:
        """Validate that the connector config contains all required fields."""

    @abc.abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Test whether the remote source is reachable and credentials are valid."""

    @abc.abstractmethod
    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        """Yield products from the source, optionally only those updated since *since*."""

    @abc.abstractmethod
    async def get_product_count(self) -> int:
        """Return the total number of products available from this source."""
