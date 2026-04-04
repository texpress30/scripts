from __future__ import annotations

import logging
from typing import Any

from app.services.feed_management.catalog_field_schemas import (
    CatalogField,
    get_catalog_fields,
)
from app.services.feed_management.master_fields.models import (
    MasterFieldMappingResponse,
    MappingType,
)
from app.services.feed_management.master_fields.repository import (
    master_field_mapping_repository,
)
from app.services.feed_management.products_repository import feed_products_repository
from app.services.feed_management.repository import FeedSourceRepository

logger = logging.getLogger(__name__)

_source_repo = FeedSourceRepository()


# ---------------------------------------------------------------------------
# Target field resolution — DB-first, hardcoded fallback
# ---------------------------------------------------------------------------

def _get_target_fields(catalog_type: str, canonical_only: bool = True) -> list[dict[str, Any]]:
    """Return target field definitions from the schema registry (DB).

    When *canonical_only* is True (default), only canonical fields are
    returned — duplicates/aliases are excluded so users map once per concept.

    Falls back to the hardcoded ``catalog_field_schemas.py`` when the
    registry has no rows for the given *catalog_type*.
    """
    try:
        from app.services.feed_management.schema_registry.repository import (
            schema_registry_repository,
        )
        db_fields = schema_registry_repository.list_fields(
            catalog_type, canonical_only=canonical_only,
        )
    except Exception:
        logger.debug("Schema registry query failed, using hardcoded fallback", exc_info=True)
        db_fields = []

    if db_fields:
        return db_fields

    # Fallback to hardcoded definitions
    logger.warning(
        "Using hardcoded fields for catalog_type=%s, no schema registry data found",
        catalog_type,
    )
    hardcoded = get_catalog_fields(catalog_type)
    return [
        {
            "id": None,
            "field_key": cf.name,
            "display_name": cf.display_name,
            "description": cf.description,
            "data_type": cf.field_type.value,
            "allowed_values": cf.enum_values,
            "format_pattern": None,
            "example_value": None,
            "is_system": cf.name in {"id", "title", "description", "link", "price", "image_link"},
            "is_required": cf.required,
            "channels": [],
            "sort_order": 0,
            "category": cf.category,
            "google_attribute": cf.google_attribute,
            "facebook_attribute": cf.facebook_attribute,
        }
        for cf in hardcoded
    ]


# ---------------------------------------------------------------------------
# Source field extraction
# ---------------------------------------------------------------------------

def get_source_fields(source_id: str) -> tuple[list[dict[str, Any]], int]:
    """Return all unique fields discovered across up to 100 MongoDB products.

    Returns ``(fields, products_scanned)``.
    """
    fields, scanned = feed_products_repository.get_all_unique_fields(
        source_id, sample_limit=100,
    )
    return fields, scanned


# ---------------------------------------------------------------------------
# Auto-suggestion engine
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    """Normalize a field name for fuzzy comparison."""
    return name.lower().replace("-", "_").replace(" ", "_")


def _suggest_source_field(
    target: dict[str, Any],
    source_field_names: list[str],
) -> str | None:
    """Find the best matching source field for a target field dict."""
    if not source_field_names:
        return None

    t_norm = _normalize(target["field_key"])
    candidates: dict[str, str] = {_normalize(s): s for s in source_field_names}

    # 1. Exact match
    if t_norm in candidates:
        return candidates[t_norm]

    # 2. Google attribute match (e.g. source has "g:title" or "g_title")
    google_attr = target.get("google_attribute")
    if google_attr:
        g_norm = _normalize(google_attr)
        g_clean = g_norm.replace("g:", "").replace("g_", "")
        for c_norm, c_orig in candidates.items():
            if c_norm == g_norm or c_norm == g_clean:
                return c_orig

    # 3. Target name contained in source field (product_title -> title)
    for c_norm, c_orig in candidates.items():
        if t_norm in c_norm:
            return c_orig

    # 4. Source field contained in target (title -> product_title)
    for c_norm, c_orig in candidates.items():
        if c_norm in t_norm and len(c_norm) >= 3:
            return c_orig

    return None


# ---------------------------------------------------------------------------
# AI-powered mapping suggestions
# ---------------------------------------------------------------------------

def suggest_mappings_ai(
    source_fields: list[dict[str, Any]],
    target_fields: list[dict[str, Any]],
    catalog_type: str,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Use Claude to suggest source→target field mappings.

    Returns a list of ``{target_field, source_field, confidence, reason}``
    dicts.  Returns ``[]`` when AI is disabled or the call fails.
    """
    from app.services.feed_management.schema_registry.ai_suggestions import (
        is_ai_enabled,
        _call_claude,
        _parse_json_response,
    )

    if not is_ai_enabled():
        return []

    # Build compact representations for the prompt
    source_lines = []
    for sf in source_fields[:80]:  # cap to avoid token overflow
        sample = sf.get("sample", "")
        sample_str = f" (sample: {sample})" if sample else ""
        source_lines.append(f"  - {sf['field']}: {sf.get('type', 'string')}{sample_str}")

    target_lines = []
    for tf in target_fields:
        desc = tf.get("description") or tf.get("display_name") or ""
        req = " [REQUIRED]" if tf.get("is_required") else ""
        target_lines.append(f"  - {tf['field_key']}: {desc}{req}")

    system_prompt = (
        f"You are a field mapping expert for {catalog_type} product feeds. "
        "Match source fields from a data source to target feed schema fields. "
        "Return ONLY a JSON array, no explanation."
    )

    user_prompt = (
        f"Source fields (from data source, {len(source_fields)} total):\n"
        + "\n".join(source_lines)
        + f"\n\nTarget fields ({catalog_type} feed schema, {len(target_fields)} total):\n"
        + "\n".join(target_lines)
        + "\n\nFor each target field, find the BEST matching source field. "
        "Consider semantic meaning, not just string similarity. "
        'For example: "meta_brand" matches "make" (vehicle manufacturer), '
        '"meta_kilometraj" matches "mileage", "meta_combustibil" matches "fuel_type".\n\n'
        "Return JSON array:\n"
        '[{"target_field": "make", "source_field": "meta_brand", '
        '"confidence": "high", "reason": "brand/make are synonyms"}]\n\n'
        "Confidence: high (obvious match), medium (likely), low (uncertain).\n"
        "Only include matches you are confident about. Skip fields with no good match."
    )

    raw = _call_claude(system=system_prompt, user_content=user_prompt, model=model)
    suggestions = _parse_json_response(raw)

    # Validate structure
    valid_confidences = {"high", "medium", "low"}
    source_names = {sf["field"] for sf in source_fields}
    target_names = {tf["field_key"] for tf in target_fields}

    validated: list[dict[str, Any]] = []
    for s in suggestions:
        tf = s.get("target_field", "")
        sf = s.get("source_field", "")
        conf = s.get("confidence", "medium")
        if tf in target_names and sf in source_names:
            validated.append({
                "target_field": tf,
                "source_field": sf,
                "confidence": conf if conf in valid_confidences else "medium",
                "reason": str(s.get("reason", "")),
            })

    return validated


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------

def get_mappings_with_suggestions(
    source_id: str,
) -> dict[str, Any]:
    """Return existing mappings + auto-suggestions for unmapped fields."""
    source = _source_repo.get_by_id(source_id)
    catalog_type = source.catalog_type if hasattr(source, "catalog_type") else "product"

    # Existing mappings
    existing = master_field_mapping_repository.get_by_source(source_id)
    mapped_targets = {m.target_field for m in existing}

    # Catalog schema fields — from DB (schema registry) with hardcoded fallback
    target_fields = _get_target_fields(catalog_type)

    # Source fields from MongoDB
    source_fields, _scanned = get_source_fields(source_id)
    source_field_names = [f["field"] for f in source_fields]

    # Build AI suggestions for unmapped fields (if enabled)
    ai_map: dict[str, dict[str, Any]] = {}
    unmapped_targets = [tf for tf in target_fields if tf["field_key"] not in mapped_targets]
    if unmapped_targets:
        ai_results = suggest_mappings_ai(source_fields, unmapped_targets, catalog_type)
        for a in ai_results:
            ai_map[a["target_field"]] = a

    # Build suggestions for unmapped required/optional fields
    suggestions: list[dict[str, Any]] = []
    for tf in target_fields:
        field_key = tf["field_key"]
        if field_key in mapped_targets:
            continue
        fuzzy = _suggest_source_field(tf, source_field_names)
        ai_hit = ai_map.get(field_key)
        # Priority: fuzzy match wins (fast, free); AI fills gaps
        if fuzzy:
            suggested = fuzzy
            suggestion_source = "fuzzy"
        elif ai_hit:
            suggested = ai_hit["source_field"]
            suggestion_source = "ai"
        else:
            suggested = None
            suggestion_source = None
        suggestions.append({
            "target_field": field_key,
            "display_name": tf["display_name"],
            "description": tf.get("description") or "",
            "field_type": tf.get("data_type", "string"),
            "required": tf.get("is_required", False),
            "category": tf.get("category", ""),
            "suggested_source_field": suggested,
            "suggestion_source": suggestion_source,
            "ai_confidence": ai_hit["confidence"] if ai_hit else None,
            "ai_reason": ai_hit["reason"] if ai_hit else None,
            "enum_values": tf.get("allowed_values"),
            "google_attribute": tf.get("google_attribute"),
            "facebook_attribute": tf.get("facebook_attribute"),
            # New fields from schema registry
            "channels": tf.get("channels", []),
            "is_system": tf.get("is_system", False),
            "format_pattern": tf.get("format_pattern"),
            "example_value": tf.get("example_value"),
            # Canonical aggregation fields
            "aliases_count": tf.get("aliases_count", 0),
            "aliases": tf.get("aliases", []),
            "all_channels": tf.get("all_channels", []),
            "channels_count": tf.get("channels_count", 0),
        })

    return {
        "source_id": source_id,
        "source_name": source.name,
        "catalog_type": catalog_type,
        "mappings": [m.model_dump() for m in existing],
        "suggestions": suggestions,
        "source_fields": source_fields,
        "mapped_count": len(existing),
        "total_schema_fields": len(target_fields),
    }
