"""AI-powered alias suggestions using Anthropic Claude API."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
]

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 2000


def _get_default_model() -> str:
    try:
        import os
        m = os.getenv("AI_SUGGESTION_MODEL", _DEFAULT_MODEL)
        return m if m in ALLOWED_MODELS else _DEFAULT_MODEL
    except Exception:
        return _DEFAULT_MODEL


def _resolve_model(model: str | None) -> str:
    if model and model in ALLOWED_MODELS:
        return model
    return _get_default_model()


def is_ai_enabled() -> bool:
    try:
        from app.core.config import load_settings
        s = load_settings()
        return bool(s.anthropic_api_key) and s.ai_alias_suggestions_enabled
    except Exception:
        return False


def get_ai_status() -> dict[str, Any]:
    return {
        "enabled": is_ai_enabled(),
        "model": _get_default_model(),
        "models_available": ALLOWED_MODELS,
    }


def _call_claude(system: str, user_content: str, model: str | None = None) -> str | None:
    """Low-level Claude API call. Returns raw text or None on failure."""
    if not is_ai_enabled():
        return None
    try:
        from anthropic import Anthropic
        from app.core.config import load_settings

        resolved = _resolve_model(model)
        timeout = 30.0 if resolved == "claude-opus-4-6" else 15.0

        client = Anthropic(api_key=load_settings().anthropic_api_key, timeout=timeout)
        response = client.messages.create(
            model=resolved,
            max_tokens=_MAX_TOKENS,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text.strip()
    except Exception:
        logger.warning("Claude API call failed", exc_info=True)
        return None


def _parse_json_response(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, IndexError):
        return []


# ---------------------------------------------------------------------------
# Import-time alias suggestions (new fields vs existing)
# ---------------------------------------------------------------------------

def suggest_aliases(
    new_fields: list[dict[str, Any]],
    existing_fields: list[dict[str, Any]],
    catalog_type: str,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Identify semantic matches between new import fields and existing canonical fields."""
    if not new_fields or not existing_fields:
        return []

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

    raw = _call_claude(
        system=(
            "You are a data field matching expert for product feed catalogs. "
            "Identify when two field names from different platforms refer to the same concept. "
            "Be conservative — only suggest matches when confident."
        ),
        user_content=f"""Catalog type: {catalog_type}

EXISTING CANONICAL FIELDS:
{existing_summary}

NEW FIELDS FROM IMPORT:
{new_summary}

Rules:
1. Only match fields that represent the SAME concept
2. Do NOT match merely similar fields (price ≠ sale_price)
3. Skip fields with the exact same field_key
4. Consider data_type compatibility

Respond ONLY with a JSON array:
[{{"new_field_key": "...", "canonical_key": "...", "confidence": "high", "reason": "..."}}]
If no matches: []""",
        model=model,
    )

    suggestions = _parse_json_response(raw)
    existing_keys = {f["field_key"] for f in existing_fields}

    valid = []
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

    logger.info("AI suggested %d aliases (import) for %s", len(valid), catalog_type)
    return valid


# ---------------------------------------------------------------------------
# Analyze existing fields for duplicates
# ---------------------------------------------------------------------------

def analyze_existing_fields(
    all_fields: list[dict[str, Any]],
    existing_aliases: list[dict[str, Any]],
    catalog_type: str,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Scan existing superset fields for duplicate groups."""
    if not all_fields:
        return []

    fields_summary = json.dumps(
        [{"field_key": f["field_key"], "display_name": f.get("display_name", ""),
          "data_type": f.get("data_type", "string"),
          "channels": [c["channel_slug"] for c in f.get("channels", [])] if isinstance(f.get("channels"), list) else []}
         for f in all_fields],
        indent=2,
    )
    aliases_summary = json.dumps(
        [{"canonical_key": a.get("canonical_key", ""), "alias_key": a.get("alias_key", "")}
         for a in existing_aliases],
        indent=2,
    )

    raw = _call_claude(
        system=(
            "You are a data field deduplication expert for product feed catalogs. "
            "Identify when multiple field names represent the same concept and should be merged."
        ),
        user_content=f"""Catalog type: {catalog_type}

ALL FIELDS IN SUPERSET:
{fields_summary}

EXISTING ALIASES (skip these):
{aliases_summary}

Rules:
1. Group fields that are semantically identical
2. Do NOT group merely similar fields (price ≠ sale_price)
3. Skip fields already covered by existing aliases
4. Prefer shorter, more generic name as canonical
5. Consider which field has more channels as tiebreaker

Respond ONLY with a JSON array:
[{{"canonical_key": "...", "duplicates": ["field1", "field2"], "confidence": "high", "reason": "..."}}]
If no duplicates: []""",
        model=model,
    )

    suggestions = _parse_json_response(raw)
    field_keys = {f["field_key"] for f in all_fields}
    alias_pairs = {(a.get("canonical_key", ""), a.get("alias_key", "")) for a in existing_aliases}

    valid = []
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        if s.get("confidence") not in ("high", "medium"):
            continue
        canonical = str(s.get("canonical_key", ""))
        dupes = s.get("duplicates", [])
        if not isinstance(dupes, list) or len(dupes) < 2:
            continue
        # All duplicates must exist as fields
        if not all(d in field_keys for d in dupes):
            continue
        # Skip if already aliased
        new_aliases = [d for d in dupes if d != canonical and (canonical, d) not in alias_pairs]
        if not new_aliases:
            continue

        valid.append({
            "canonical_key": canonical,
            "duplicates": dupes,
            "confidence": s["confidence"],
            "reason": str(s.get("reason", "")),
        })

    logger.info("AI found %d duplicate groups (analyze) for %s", len(valid), catalog_type)
    return valid
