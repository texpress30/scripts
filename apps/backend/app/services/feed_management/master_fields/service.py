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
    target: CatalogField,
    source_field_names: list[str],
) -> str | None:
    """Find the best matching source field for a target catalog field."""
    if not source_field_names:
        return None

    t_norm = _normalize(target.name)
    candidates: dict[str, str] = {_normalize(s): s for s in source_field_names}

    # 1. Exact match
    if t_norm in candidates:
        return candidates[t_norm]

    # 2. Google attribute match (e.g. source has "g:title" or "g_title")
    if target.google_attribute:
        g_norm = _normalize(target.google_attribute)
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

    # Catalog schema fields
    catalog_fields = get_catalog_fields(catalog_type)

    # Source fields from MongoDB
    source_fields, _scanned = get_source_fields(source_id)
    source_field_names = [f["field"] for f in source_fields]

    # Build suggestions for unmapped required/optional fields
    suggestions: list[dict[str, Any]] = []
    for cf in catalog_fields:
        if cf.name in mapped_targets:
            continue
        suggested = _suggest_source_field(cf, source_field_names)
        suggestions.append({
            "target_field": cf.name,
            "display_name": cf.display_name,
            "description": cf.description,
            "field_type": cf.field_type.value,
            "required": cf.required,
            "category": cf.category,
            "suggested_source_field": suggested,
            "enum_values": cf.enum_values,
            "google_attribute": cf.google_attribute,
            "facebook_attribute": cf.facebook_attribute,
        })

    return {
        "source_id": source_id,
        "source_name": source.name,
        "catalog_type": catalog_type,
        "mappings": [m.model_dump() for m in existing],
        "suggestions": suggestions,
        "source_fields": source_fields,
        "mapped_count": len(existing),
        "total_schema_fields": len(catalog_fields),
    }
