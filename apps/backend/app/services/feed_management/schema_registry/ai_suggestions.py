"""AI-powered alias suggestions using Anthropic Claude API."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 2000
_TIMEOUT = 15.0


def is_ai_enabled() -> bool:
    """Check if AI alias suggestions are available."""
    try:
        from app.core.config import load_settings
        settings = load_settings()
        return bool(settings.anthropic_api_key) and settings.ai_alias_suggestions_enabled
    except Exception:
        return False


def suggest_aliases(
    new_fields: list[dict[str, Any]],
    existing_fields: list[dict[str, Any]],
    catalog_type: str,
) -> list[dict[str, Any]]:
    """Call Claude to identify semantic matches between new and existing fields.

    Returns a list of suggestions:
    [{"new_field_key": "...", "canonical_key": "...", "confidence": "high", "reason": "..."}]

    Returns [] on any failure (AI never blocks import).
    """
    if not is_ai_enabled():
        return []

    if not new_fields or not existing_fields:
        return []

    try:
        from anthropic import Anthropic
        from app.core.config import load_settings

        client = Anthropic(
            api_key=load_settings().anthropic_api_key,
            timeout=_TIMEOUT,
        )

        existing_summary = json.dumps(
            [{"field_key": f["field_key"], "display_name": f.get("display_name", ""),
              "data_type": f.get("data_type", "string")} for f in existing_fields],
            indent=2,
        )
        new_summary = json.dumps(
            [{"field_key": f["field_key"], "display_name": f.get("display_name", ""),
              "data_type": f.get("data_type", "string"),
              "description": f.get("description", "")} for f in new_fields],
            indent=2,
        )

        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            temperature=0,
            system=(
                "You are a data field matching expert for product feed catalogs. "
                "Your job is to identify when two field names from different platforms "
                "(Meta, TikTok, Google, etc.) refer to the same concept. "
                "Be conservative — only suggest matches when you are confident."
            ),
            messages=[{
                "role": "user",
                "content": f"""Catalog type: {catalog_type}

EXISTING CANONICAL FIELDS (already in our system):
{existing_summary}

NEW FIELDS FROM IMPORT (to be matched):
{new_summary}

For each new field, determine if it matches an existing canonical field.
Rules:
1. Only match fields that represent the SAME concept (e.g., "url" = "link", "vehicle_offer_id" = "vehicle_id")
2. Do NOT match fields that are merely similar (e.g., "price" ≠ "sale_price", "exterior_color" ≠ "interior_color")
3. If a new field has the exact same field_key as an existing canonical, skip it (already matched)
4. Consider data_type compatibility: don't match a "number" field with a "url" field

Respond ONLY with a JSON array, no other text:
[{{"new_field_key": "...", "canonical_key": "...", "confidence": "high", "reason": "..."}}]
If no matches found, respond with: []""",
            }],
        )

        raw = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            return []

        # Validate suggestions
        existing_keys = {f["field_key"] for f in existing_fields}
        valid: list[dict[str, Any]] = []
        for s in suggestions:
            if not isinstance(s, dict):
                continue
            if s.get("canonical_key") not in existing_keys:
                continue
            if s.get("confidence") not in ("high", "medium"):
                continue
            valid.append({
                "new_field_key": str(s.get("new_field_key", "")),
                "canonical_key": str(s["canonical_key"]),
                "confidence": s["confidence"],
                "reason": str(s.get("reason", "")),
            })

        logger.info(
            "AI suggested %d aliases for catalog_type=%s (%d new fields, %d existing)",
            len(valid), catalog_type, len(new_fields), len(existing_fields),
        )
        return valid

    except Exception:
        logger.warning("AI alias suggestion failed, returning empty", exc_info=True)
        return []
