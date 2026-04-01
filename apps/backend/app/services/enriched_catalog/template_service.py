from __future__ import annotations

import re
from typing import Any

from app.services.enriched_catalog.exceptions import (
    InvalidDynamicBindingError,
    TemplateNotFoundError,
)
from app.services.enriched_catalog.repository import (
    creative_template_repository,
)

_DYNAMIC_BINDING_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateService:
    def __init__(self, template_repo=None) -> None:
        self._repo = template_repo or creative_template_repository

    def create_template(self, subaccount_id: int, data: dict[str, Any]) -> dict[str, Any]:
        elements = list(data.get("elements") or [])
        serialized_elements = []
        for el in elements:
            if hasattr(el, "model_dump"):
                serialized_elements.append(el.model_dump())
            elif isinstance(el, dict):
                serialized_elements.append(el)
            else:
                serialized_elements.append(dict(el))
        payload = dict(data)
        payload["elements"] = serialized_elements
        return self._repo.create(subaccount_id, payload)

    def get_template(self, template_id: str) -> dict[str, Any]:
        template = self._repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(template_id)
        return template

    def preview_template(self, template_id: str, sample_product_data: dict[str, Any]) -> dict[str, Any]:
        template = self.get_template(template_id)
        rendered_elements: list[dict[str, Any]] = []
        for element in list(template.get("elements") or []):
            rendered = dict(element)
            binding = rendered.get("dynamic_binding")
            if binding:
                match = _DYNAMIC_BINDING_PATTERN.search(str(binding))
                if match:
                    field_name = match.group(1)
                    rendered["resolved_value"] = str(sample_product_data.get(field_name) or "")
            rendered_elements.append(rendered)
        return {
            "template_id": template["id"],
            "name": template.get("name", ""),
            "canvas_width": template.get("canvas_width", 1080),
            "canvas_height": template.get("canvas_height", 1080),
            "background_color": template.get("background_color", "#FFFFFF"),
            "rendered_elements": rendered_elements,
        }

    def validate_dynamic_bindings(self, template_id: str, available_fields: list[str]) -> list[str]:
        template = self.get_template(template_id)
        errors: list[str] = []
        available_set = set(available_fields)
        for element in list(template.get("elements") or []):
            binding = element.get("dynamic_binding")
            if not binding:
                continue
            match = _DYNAMIC_BINDING_PATTERN.search(str(binding))
            if not match:
                errors.append(f"Invalid binding syntax: {binding}")
                continue
            field_name = match.group(1)
            if field_name not in available_set:
                errors.append(f"Field '{field_name}' not found in feed source")
        return errors

    def duplicate_template(self, template_id: str, new_name: str) -> dict[str, Any]:
        result = self._repo.duplicate(template_id, new_name)
        if result is None:
            raise TemplateNotFoundError(template_id)
        return result


template_service = TemplateService()
