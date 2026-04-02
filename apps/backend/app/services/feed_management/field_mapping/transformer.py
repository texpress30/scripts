"""Field transformation engine.

Applies a set of mapping rules to a raw product dict, producing a
transformed dict that matches the target catalog schema.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.feed_management.catalog_schemas import (
    CatalogType,
    get_required_fields,
    validate_mapping_completeness,
)
from app.services.feed_management.field_mapping.models import (
    FieldMappingRuleResponse,
    TransformationType,
)

logger = logging.getLogger(__name__)


class FieldTransformer:
    """Stateless transformer: call *apply_mapping* for each product."""

    def apply_mapping(
        self,
        product: dict[str, Any],
        rules: list[FieldMappingRuleResponse],
    ) -> dict[str, Any]:
        """Transform *product* according to *rules*, returning a new dict."""
        result: dict[str, Any] = {}
        for rule in sorted(rules, key=lambda r: r.sort_order):
            try:
                value = self._apply_rule(product, rule)
                if value is not None:
                    result[rule.target_field] = value
            except Exception:
                logger.debug(
                    "Rule %s (%s -> %s) failed for product",
                    rule.id, rule.source_field, rule.target_field,
                    exc_info=True,
                )
        return result

    def validate_output(
        self,
        transformed: dict[str, Any],
        catalog_type: CatalogType,
    ) -> dict[str, Any]:
        """Validate a transformed product against the catalog schema."""
        mapped_fields = list(transformed.keys())
        return validate_mapping_completeness(catalog_type, mapped_fields)

    # ------------------------------------------------------------------
    # Transformation implementations
    # ------------------------------------------------------------------

    def _apply_rule(
        self,
        product: dict[str, Any],
        rule: FieldMappingRuleResponse,
    ) -> Any:
        tt = rule.transformation_type
        cfg = rule.transformation_config or {}
        raw = self._resolve_source(product, rule.source_field)

        if tt == TransformationType.direct:
            return raw

        if tt == TransformationType.static:
            return cfg.get("value")

        if tt == TransformationType.template:
            return self._transform_template(product, cfg)

        if tt == TransformationType.concatenate:
            return self._transform_concatenate(product, cfg)

        if tt == TransformationType.uppercase:
            return str(raw).upper() if raw is not None else None

        if tt == TransformationType.lowercase:
            return str(raw).lower() if raw is not None else None

        if tt == TransformationType.prefix:
            prefix = cfg.get("prefix", "")
            return f"{prefix}{raw}" if raw is not None else None

        if tt == TransformationType.suffix:
            suffix = cfg.get("suffix", "")
            return f"{raw}{suffix}" if raw is not None else None

        if tt == TransformationType.replace:
            return self._transform_replace(raw, cfg)

        if tt == TransformationType.truncate:
            max_len = int(cfg.get("max_length", 150))
            if raw is None:
                return None
            text = str(raw)
            return text[:max_len] if len(text) > max_len else text

        if tt == TransformationType.conditional:
            return self._transform_conditional(product, raw, cfg)

        return raw

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_source(product: dict[str, Any], source_field: str | None) -> Any:
        """Resolve a dotted source_field path from product data.

        Supports nested access: ``data.title``, ``data.images.0``.
        """
        if not source_field:
            return None
        parts = source_field.split(".")
        current: Any = product
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    @staticmethod
    def _transform_template(product: dict[str, Any], cfg: dict[str, Any]) -> str | None:
        """Interpolate ``{field}`` placeholders in a template string."""
        tpl: str = cfg.get("template", "")
        if not tpl:
            return None

        def _replacer(m: re.Match) -> str:
            key = m.group(1)
            val = FieldTransformer._resolve_source(product, key)
            return str(val) if val is not None else ""

        return re.sub(r"\{([^}]+)\}", _replacer, tpl)

    @staticmethod
    def _transform_concatenate(product: dict[str, Any], cfg: dict[str, Any]) -> str | None:
        """Concatenate multiple source fields with a separator."""
        fields: list[str] = cfg.get("fields", [])
        separator: str = cfg.get("separator", " ")
        parts = []
        for f in fields:
            val = FieldTransformer._resolve_source(product, f)
            if val is not None:
                parts.append(str(val))
        return separator.join(parts) if parts else None

    @staticmethod
    def _transform_replace(raw: Any, cfg: dict[str, Any]) -> str | None:
        if raw is None:
            return None
        search: str = cfg.get("search", "")
        replacement: str = cfg.get("replacement", "")
        if not search:
            return str(raw)
        return str(raw).replace(search, replacement)

    @staticmethod
    def _transform_conditional(
        product: dict[str, Any],
        raw: Any,
        cfg: dict[str, Any],
    ) -> Any:
        """Simple conditional: if source matches *condition_value*, use
        *then_value*, else *else_value*.
        """
        condition_field = cfg.get("condition_field")
        condition_value = cfg.get("condition_value")
        then_value = cfg.get("then_value")
        else_value = cfg.get("else_value")

        check = FieldTransformer._resolve_source(product, condition_field) if condition_field else raw
        if str(check) == str(condition_value):
            return then_value
        return else_value


field_transformer = FieldTransformer()
