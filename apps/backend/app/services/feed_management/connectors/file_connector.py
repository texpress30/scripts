from __future__ import annotations

import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, AsyncIterator

import requests

from app.core.config import load_settings
from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_CSV_DELIMITER = ","
_SUPPORTED_ENCODINGS = ("utf-8", "latin-1", "cp1252")


def _resolve_basic_auth(
    credentials: dict[str, str] | None,
) -> tuple[str, str] | None:
    """Return ``(username, password)`` when both are set, else ``None``.

    Accepts the credential bag the connector is instantiated with
    (either from the wizard's create-source payload or from the
    per-source entry in ``integration_secrets`` — see
    ``app/integrations/file_source/service.py``). Both fields must be
    present for auth to kick in; an empty string on either side means
    "no auth" so a half-configured source falls back to the public
    fetch path instead of sending a broken ``Authorization`` header.
    """
    if not credentials:
        return None
    username = str(credentials.get("username") or "").strip()
    password = str(credentials.get("password") or "").strip()
    if not username or not password:
        return None
    return (username, password)


def _fetch_remote_content(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
) -> bytes:
    """Fetch a remote URL and return the raw bytes.

    When ``auth`` is supplied, ``requests`` stitches the
    ``Authorization: Basic ...`` header automatically. Otherwise the
    request goes out unauthenticated (the pre-Basic-Auth behaviour).
    """
    timeout = load_settings().storage_media_remote_fetch_timeout_seconds
    resp = requests.get(url, timeout=timeout, auth=auth)
    resp.raise_for_status()
    return resp.content


def _decode_bytes(raw: bytes) -> str:
    for encoding in _SUPPORTED_ENCODINGS:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode("utf-8", errors="replace")


def _read_source(
    config: dict[str, Any],
    *,
    auth: tuple[str, str] | None = None,
) -> str:
    file_url = config.get("file_url") or ""
    if file_url.startswith(("http://", "https://")):
        return _decode_bytes(_fetch_remote_content(file_url, auth=auth))
    with open(file_url, "rb") as fh:
        return _decode_bytes(fh.read())


class FileConnector(BaseConnector):
    """Connector for file-based feeds: CSV, JSON, XML.

    Optional HTTP Basic Auth credentials flow in via the shared
    ``BaseConnector`` ``credentials`` kwarg. When both ``username`` and
    ``password`` are set, :func:`_fetch_remote_content` sends an
    ``Authorization: Basic`` header automatically — otherwise the URL
    is fetched unauthenticated, preserving backwards compatibility
    with every existing public feed.
    """

    def _basic_auth(self) -> tuple[str, str] | None:
        return _resolve_basic_auth(self.credentials)

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        file_url = self.config.get("file_url") or ""
        if not file_url:
            errors.append("file_url is required")
        file_type = self.config.get("file_type", "csv")
        if file_type not in ("csv", "json", "xml"):
            errors.append(f"Unsupported file_type: {file_type}")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            content = _read_source(self.config, auth=self._basic_auth())
            return ConnectionTestResult(success=True, message="File is accessible", details={"content_length": len(content)})
        except Exception as exc:
            return ConnectionTestResult(success=False, message=str(exc))

    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        content = _read_source(self.config, auth=self._basic_auth())
        file_type = self.config.get("file_type", "csv")
        if file_type == "csv":
            async for product in self._parse_csv(content):
                yield product
        elif file_type == "json":
            async for product in self._parse_json(content):
                yield product
        elif file_type == "xml":
            async for product in self._parse_xml(content):
                yield product

    async def get_product_count(self) -> int:
        count = 0
        async for _ in self.fetch_products():
            count += 1
        return count

    async def _parse_csv(self, content: str) -> AsyncIterator[ProductData]:
        delimiter = self.config.get("delimiter") or _DEFAULT_CSV_DELIMITER
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        for idx, row in enumerate(reader):
            yield _row_to_product(row, fallback_id=str(idx))

    async def _parse_json(self, content: str) -> AsyncIterator[ProductData]:
        data = json.loads(content)
        items = data if isinstance(data, list) else data.get("products", data.get("items", []))
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                yield _row_to_product(item, fallback_id=str(idx))

    async def _parse_xml(self, content: str) -> AsyncIterator[ProductData]:
        root_tag = self.config.get("extra", {}).get("xml_item_tag", "product")
        root = ET.fromstring(content)
        for idx, elem in enumerate(root.iter(root_tag)):
            row = {child.tag: (child.text or "") for child in elem}
            yield _row_to_product(row, fallback_id=str(idx))


def _row_to_product(row: dict[str, Any], *, fallback_id: str) -> ProductData:
    def _get(keys: list[str], default: str = "") -> str:
        for k in keys:
            val = row.get(k)
            if val is not None and str(val).strip():
                return str(val).strip()
        return default

    def _get_float(keys: list[str], default: float = 0.0) -> float:
        raw = _get(keys)
        if not raw:
            return default
        try:
            return float(raw.replace(",", "."))
        except (ValueError, TypeError):
            return default

    def _get_int(keys: list[str], default: int = 0) -> int:
        raw = _get(keys)
        if not raw:
            return default
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return default

    images_raw = _get(["images", "image_url", "image", "image_link"])
    images = [img.strip() for img in images_raw.split(",") if img.strip()] if images_raw else []

    tags_raw = _get(["tags", "labels", "categories"])
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    compare_raw = _get(["compare_at_price", "compare_price", "original_price", "sale_price"])
    compare_at_price = float(compare_raw.replace(",", ".")) if compare_raw else None

    # Preserve all original fields as raw_data
    raw = {k: v for k, v in row.items() if v is not None and str(v).strip()}

    return ProductData(
        id=_get(["id", "product_id", "sku", "item_id"]) or fallback_id,
        title=_get(["title", "name", "product_name", "product_title"]),
        description=_get(["description", "body_html", "short_description", "body"]),
        price=_get_float(["price", "regular_price", "unit_price"]),
        compare_at_price=compare_at_price,
        currency=_get(["currency", "price_currency"], default="USD"),
        images=images,
        variants=[],
        category=_get(["category", "product_type", "type", "product_category"]),
        tags=tags,
        inventory_quantity=_get_int(["inventory_quantity", "quantity", "stock", "stock_quantity"]),
        sku=_get(["sku", "item_sku", "variant_sku"]),
        url=_get(["url", "link", "product_url", "handle"]),
        raw_data=raw,
    )
