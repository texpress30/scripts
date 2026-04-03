"""Template adapters for parsing platform-specific field specification files.

Each adapter takes raw file bytes and returns a standardised list of field
spec dicts ready for upsert into feed_schema_fields / feed_schema_channel_fields.

Supported formats:
- **Meta CSV**: rows 1=metadata, 2=field names, 3=examples
- **XML feed**: generic sample feed (Meta, Google, any RSS)
- **Custom CSV**: our own format with explicit field_key/display_name columns
"""

from __future__ import annotations

import csv
import io
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared types / helpers
# ---------------------------------------------------------------------------

FieldSpec = dict[str, Any]
"""Expected keys: field_key, display_name, description, data_type,
is_required, allowed_values, format_pattern, example_value, channel_field_name"""


def _make_display_name(field_key: str) -> str:
    """Turn 'vehicle_offer_id' into 'Vehicle Offer Id'."""
    clean = re.sub(r"\[\d+\]", "", field_key)
    clean = clean.replace(".", " ").replace("_", " ").replace("-", " ")
    return clean.strip().title()


def _clean_field_key(raw: str) -> str:
    """Turn 'image[0].url' into 'image_0_url'."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_").lower()


def _infer_data_type(field_key: str, example: str | None) -> str:
    fk = field_key.lower()
    if "url" in fk or "link" in fk or "href" in fk:
        return "url"
    if fk in ("price", "amount", "sale_price", "compare_at_price") or "price" in fk or "amount" in fk:
        return "price"
    if fk == "year" or fk == "mileage":
        return "number"
    if "date" in fk or "time" in fk:
        return "date"
    if example:
        ex = example.strip()
        # price pattern: "123.45 USD"
        if re.match(r"^\d+\.?\d*\s+[A-Z]{3}$", ex):
            return "price"
        # pure number
        try:
            float(ex.replace(",", ""))
            return "number"
        except (ValueError, TypeError):
            pass
    return "string"


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(content: bytes, filename: str) -> str:
    """Return one of 'meta_csv', 'xml', 'custom', or raise ValueError."""
    # XML detection
    stripped = content.lstrip()
    if stripped[:1] == b"<" or filename.lower().endswith(".xml"):
        return "xml"

    # CSV detection — decode first line
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    first_line = text.split("\n", 1)[0].strip()

    # Meta CSV: first cells start with "# Required" or "# Optional"
    if first_line.startswith("# Required") or first_line.startswith("# Optional"):
        return "meta_csv"
    # Also check if it's tab-separated Meta
    cells = first_line.split("\t") if "\t" in first_line else first_line.split(",")
    for cell in cells[:3]:
        cell = cell.strip().strip('"')
        if cell.startswith("# Required") or cell.startswith("# Optional"):
            return "meta_csv"

    # Custom CSV: header row contains "field_key"
    headers = {h.strip().strip('"').lower() for h in cells}
    if "field_key" in headers:
        return "custom"

    raise ValueError(
        "Unrecognized template format. Supported: Meta CSV template, "
        "XML feed template, or custom CSV with field_key/display_name columns."
    )


# ---------------------------------------------------------------------------
# Meta CSV adapter
# ---------------------------------------------------------------------------

def parse_meta_csv(content: bytes) -> tuple[list[FieldSpec], list[str]]:
    """Parse Meta Commerce Manager CSV template.

    Returns (fields, warnings).
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Detect delimiter
    first_line = text.split("\n", 1)[0]
    delimiter = "\t" if "\t" in first_line else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)

    if len(rows) < 2:
        raise ValueError("Meta CSV template must have at least 2 rows (metadata + field names)")

    metadata_row = rows[0]
    field_names_row = rows[1]
    example_row = rows[2] if len(rows) > 2 else []

    warnings: list[str] = []
    fields: list[FieldSpec] = []
    seen_keys: set[str] = set()

    for i, raw_name in enumerate(field_names_row):
        raw_name = raw_name.strip()
        if not raw_name:
            continue

        # Parse metadata cell
        meta = metadata_row[i].strip() if i < len(metadata_row) else ""
        is_required = meta.startswith("# Required")
        description: str | None = None
        if "|" in meta:
            desc = meta.split("|", 1)[1].strip()
            if desc and desc != "No field comment specified":
                description = desc

        # Example value
        example = example_row[i].strip() if i < len(example_row) else None
        if example == "":
            example = None

        # Build field_key (clean) and channel_field_name (original)
        field_key = _clean_field_key(raw_name)
        if field_key in seen_keys:
            continue  # skip duplicate bracket expansions
        seen_keys.add(field_key)

        fields.append({
            "field_key": field_key,
            "display_name": _make_display_name(raw_name),
            "description": description,
            "data_type": _infer_data_type(field_key, example),
            "is_required": is_required,
            "allowed_values": None,
            "format_pattern": None,
            "example_value": example,
            "channel_field_name": raw_name,
        })

    return fields, warnings


# ---------------------------------------------------------------------------
# XML adapter
# ---------------------------------------------------------------------------

def parse_xml_template(content: bytes) -> tuple[list[FieldSpec], list[str]]:
    """Parse a generic XML sample feed and extract field names from the first item.

    Returns (fields, warnings).
    """
    warnings: list[str] = [
        "XML template does not contain required/optional metadata. "
        "All fields imported as optional."
    ]

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    root = ET.fromstring(text)

    # Find the first repeatable element: <listing>, <item>, <entry>, <product>
    item_tags = {"listing", "item", "entry", "product", "record", "row"}
    first_item: ET.Element | None = None

    # Direct children
    for child in root:
        tag = child.tag.split("}")[-1].lower() if "}" in child.tag else child.tag.lower()
        if tag in item_tags:
            first_item = child
            break

    # One level deeper (e.g., <rss><channel><item>)
    if first_item is None:
        for parent in root:
            for child in parent:
                tag = child.tag.split("}")[-1].lower() if "}" in child.tag else child.tag.lower()
                if tag in item_tags:
                    first_item = child
                    break
            if first_item is not None:
                break

    # Fallback: first element with children
    if first_item is None:
        for child in root.iter():
            if len(child) > 0 and child is not root:
                first_item = child
                break

    if first_item is None:
        raise ValueError("Could not find a repeatable item element in XML")

    def _extract_fields(
        elem: ET.Element, prefix: str = "",
    ) -> list[tuple[str, str, str | None]]:
        """Return (field_key, channel_field_name, example_value) tuples."""
        results: list[tuple[str, str, str | None]] = []
        for child in elem:
            raw_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            # Strip common namespace prefixes
            raw_tag = re.sub(r"^[a-z]:", "", raw_tag)

            full_key = f"{prefix}_{raw_tag}" if prefix else raw_tag
            channel_name = f"{prefix}.{raw_tag}" if prefix else raw_tag

            if len(child) > 0:
                # Nested element — recurse
                results.extend(_extract_fields(child, full_key))
            else:
                example = (child.text or "").strip() or None
                results.append((full_key.lower(), channel_name, example))
        return results

    raw_fields = _extract_fields(first_item)

    fields: list[FieldSpec] = []
    seen: set[str] = set()
    for field_key, channel_name, example in raw_fields:
        clean_key = _clean_field_key(field_key)
        if clean_key in seen:
            continue
        seen.add(clean_key)

        fields.append({
            "field_key": clean_key,
            "display_name": _make_display_name(field_key),
            "description": None,
            "data_type": _infer_data_type(clean_key, example),
            "is_required": False,
            "allowed_values": None,
            "format_pattern": None,
            "example_value": example,
            "channel_field_name": channel_name,
        })

    return fields, warnings


# ---------------------------------------------------------------------------
# Custom CSV adapter (existing format)
# ---------------------------------------------------------------------------

def parse_custom_csv(content: bytes) -> tuple[list[FieldSpec], list[str]]:
    """Parse our custom CSV format with explicit field_key/display_name columns.

    Returns (fields, warnings).
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row")

    normalised = {h.strip().lower(): h for h in reader.fieldnames}
    required_cols = {"field_key", "display_name"}
    missing = required_cols - set(normalised.keys())
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {', '.join(sorted(missing))}. "
            f"Found columns: {', '.join(reader.fieldnames)}"
        )

    fields: list[FieldSpec] = []
    for row in reader:
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        fk = norm.get("field_key", "").strip()
        dn = norm.get("display_name", "").strip()
        if not fk or not dn:
            continue

        data_type = norm.get("data_type", "string").strip() or "string"
        is_req = norm.get("is_required", "false").strip().lower() in ("true", "1", "yes")
        allowed_raw = norm.get("allowed_values", "").strip()
        allowed = [v.strip() for v in allowed_raw.split(",") if v.strip()] if allowed_raw else None

        fields.append({
            "field_key": fk,
            "display_name": dn,
            "description": norm.get("description", "").strip() or None,
            "data_type": data_type,
            "is_required": is_req,
            "allowed_values": allowed,
            "format_pattern": norm.get("format_pattern", "").strip() or None,
            "example_value": norm.get("example_value", "").strip() or None,
            "channel_field_name": norm.get("channel_field_name", "").strip() or fk,
        })

    return fields, []


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def parse_template(
    content: bytes,
    filename: str,
    template_format: str = "auto",
) -> tuple[list[FieldSpec], str, list[str]]:
    """Parse a template file and return (fields, detected_format, warnings).

    *template_format* can be 'auto', 'meta_csv', 'xml', or 'custom'.
    """
    if template_format == "auto":
        fmt = detect_format(content, filename)
    else:
        fmt = template_format

    if fmt == "meta_csv":
        fields, warnings = parse_meta_csv(content)
    elif fmt == "xml":
        fields, warnings = parse_xml_template(content)
    elif fmt == "custom":
        fields, warnings = parse_custom_csv(content)
    else:
        raise ValueError(f"Unknown template format: {fmt}")

    return fields, fmt, warnings
