"""Template adapters for parsing platform-specific field specification files.

Each adapter takes raw file bytes and returns a standardised list of field
spec dicts ready for upsert into feed_schema_fields / feed_schema_channel_fields.

Supported formats:
- **Meta CSV**: rows 1=metadata, 2=field names, 3=examples
- **TikTok CSV**: rows 1=field names, 2=descriptions with Required/Optional, 3=examples
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

    # TikTok CSV: row 1 = field names (no "field_key", no "#"),
    # row 2 = descriptions containing "Required" or "Optional".
    # IMPORTANT: use csv.reader to handle quoted fields with embedded newlines,
    # because TikTok Hotel/Flight templates have multi-line description cells.
    try:
        delimiter = "\t" if "\t" in first_line else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        row1 = next(reader, None)
        row2 = next(reader, None)
        if row1 and row2:
            req_opt_count = sum(
                1 for c in row2
                if re.search(r"\b(required|optional)\b", c.strip(), re.IGNORECASE)
            )
            if req_opt_count >= 3:
                return "tiktok_csv"
    except Exception:
        pass  # CSV parsing failed — fall through to error

    raise ValueError(
        "Unrecognized template format. Supported: Meta CSV template, TikTok CSV template, "
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
# TikTok CSV adapter
# ---------------------------------------------------------------------------

_SUPPORTED_VALUES_RE = re.compile(
    r"Supported values?:\s*(.+?)(?:\.|$)", re.IGNORECASE,
)

_ACCEPTED_VALUES_RE = re.compile(
    r"Accepted values?:\s*(.+?)(?:\.\s|$)", re.IGNORECASE,
)

_RANGE_VALUES_RE = re.compile(
    r"valid values? (?:are )?between (\d+) (?:to|and) (\d+)", re.IGNORECASE,
)


def _extract_supported_values(text: str) -> list[str] | None:
    """Extract allowed values from 'Supported values: A, B, or C' patterns."""
    m = _SUPPORTED_VALUES_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip().rstrip(".")
    # Remove trailing "or" joiner: "A, B, or C" → "A, B, C"
    raw = re.sub(r",?\s+or\s+", ", ", raw)
    values = [v.strip() for v in raw.split(",") if v.strip()]
    return values if values else None


def _extract_accepted_values(rules_text: str) -> list[str] | None:
    """Extract allowed values from TikTok pipe-format Rules section.

    Handles patterns like:
    - "Rules: 1. Accepted values: in stock, out of stock"
    - "Rules: 1. Accepted values: Motel, Hostel, Guest House, ..."
    - "Rules: 1. The valid values are between 1 to 5"
    """
    if not rules_text:
        return None

    # Pattern 1: "Accepted values: ..."
    m = _ACCEPTED_VALUES_RE.search(rules_text)
    if m:
        raw = m.group(1).strip().rstrip(".")
        raw = re.sub(r",?\s+or\s+", ", ", raw)
        values = [v.strip() for v in raw.split(",") if v.strip()]
        if values:
            return values

    # Pattern 2: "valid values are between X to Y"
    m = _RANGE_VALUES_RE.search(rules_text)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if end - start <= 100:  # sanity check
            return [str(i) for i in range(start, end + 1)]

    # Fallback: also try "Supported values:" in rules text
    return _extract_supported_values(rules_text)


def _parse_tiktok_description_cell(
    desc_cell: str,
) -> tuple[bool, str | None, list[str] | None]:
    """Parse a TikTok description cell in either format.

    Format A (Auto-Inventory, dot separator):
      "Required.Description text here"
      "Optional.Description text here"

    Format B (Hotel/Flight/Destination, pipe separator):
      "Required || Description text || Rules: 1. Character limit: 100"
      "Optional || Description text || Rules: 1. Accepted values: in stock, out of stock"

    Returns (is_required, description, allowed_values).
    """
    cell = desc_cell.strip()
    if not cell:
        return False, None, None

    # ── Format B: double pipe separator ──
    if "||" in cell:
        parts = [p.strip() for p in cell.split("||")]
        prefix = parts[0].lower()
        is_required = prefix.startswith("required") and "not required" not in prefix
        description = parts[1] if len(parts) > 1 and parts[1] else None
        rules = parts[2] if len(parts) > 2 else ""
        # Extract allowed_values from the Rules section
        allowed_values = _extract_accepted_values(rules)
        # Also try from description itself (sometimes values are mentioned there)
        if not allowed_values and description:
            allowed_values = _extract_accepted_values(description)
        return is_required, description, allowed_values

    # ── Format A: dot/prefix separator (existing) ──
    cell_lower = cell.lower()

    if cell_lower.startswith("required"):
        is_required = True
    elif cell_lower.startswith("optional"):
        is_required = False
    elif "not required" in cell_lower:
        is_required = False
    elif "required" in cell_lower:
        is_required = True
    else:
        is_required = False

    # Strip "Required." or "Optional." prefix
    description = re.sub(
        r"^(Required|Optional)\s*\.?\s*", "", cell, flags=re.IGNORECASE,
    ).strip() or None

    # Extract allowed values
    allowed_values = _extract_supported_values(cell)
    if not allowed_values:
        allowed_values = _extract_accepted_values(cell)

    return is_required, description, allowed_values


def parse_tiktok_csv(content: bytes) -> tuple[list[FieldSpec], list[str]]:
    """Parse TikTok CSV template (Auto-Inventory, Hotel, Flight, Destination).

    Supports two description formats:
    - Format A (dot separator): "Required.Description text"
    - Format B (pipe separator): "Required || Description || Rules: ..."

    Row 1 = field names, Row 2 = descriptions with Required/Optional, Row 3 = examples.
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
        raise ValueError("TikTok CSV template must have at least 2 rows (field names + descriptions)")

    field_names_row = rows[0]
    desc_row = rows[1]
    example_row = rows[2] if len(rows) > 2 else []

    warnings: list[str] = []
    fields: list[FieldSpec] = []
    seen_keys: set[str] = set()

    # Detect which format variant (for logging)
    sample_cells = [c.strip() for c in desc_row[:5] if c.strip()]
    has_pipes = any("||" in c for c in sample_cells)
    if has_pipes:
        warnings.append("TikTok pipe-separated format detected (Hotel/Flight/Destination).")

    for i, raw_name in enumerate(field_names_row):
        raw_name = raw_name.strip()
        if not raw_name:
            continue

        desc_cell = desc_row[i].strip() if i < len(desc_row) else ""
        is_required, description, allowed_values = _parse_tiktok_description_cell(desc_cell)

        # Example value
        example = example_row[i].strip() if i < len(example_row) else None
        if example == "":
            example = None

        field_key = _clean_field_key(raw_name)
        if field_key in seen_keys:
            continue
        seen_keys.add(field_key)

        fields.append({
            "field_key": field_key,
            "display_name": _make_display_name(raw_name),
            "description": description,
            "data_type": _infer_data_type(field_key, example),
            "is_required": is_required,
            "allowed_values": allowed_values,
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

    *template_format* can be 'auto', 'meta_csv', 'tiktok_csv', 'xml', or 'custom'.
    """
    if template_format == "auto":
        fmt = detect_format(content, filename)
    else:
        fmt = template_format

    if fmt == "meta_csv":
        fields, warnings = parse_meta_csv(content)
    elif fmt == "tiktok_csv":
        fields, warnings = parse_tiktok_csv(content)
    elif fmt == "xml":
        fields, warnings = parse_xml_template(content)
    elif fmt == "custom":
        fields, warnings = parse_custom_csv(content)
    else:
        raise ValueError(f"Unknown template format: {fmt}")

    return fields, fmt, warnings
