from __future__ import annotations

import re
from typing import Any

from app.services.enriched_catalog.exceptions import TemplateNotFoundError
from app.services.enriched_catalog.repository import creative_template_repository

_BINDING_RE = re.compile(r"\{\{(\w+)\}\}")


class TemplateService:
    def __init__(self, repo=None) -> None:
        self._repo = repo or creative_template_repository

    def get_template(self, template_id: str) -> dict[str, Any]:
        template = self._repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(template_id)
        return template

    def create_template(self, subaccount_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return self._repo.create(subaccount_id, data)

    def duplicate_template(self, template_id: str, new_name: str) -> dict[str, Any]:
        result = self._repo.duplicate(template_id, new_name)
        if result is None:
            raise TemplateNotFoundError(template_id)
        return result

    def preview_template(self, template_id: str, product_data: dict[str, Any]) -> dict[str, Any]:
        template = self.get_template(template_id)
        rendered_elements: list[dict[str, Any]] = []
        for element in list(template.get("elements") or []):
            entry = dict(element) if isinstance(element, dict) else element
            binding = entry.get("dynamic_binding") if isinstance(entry, dict) else None
            if binding:
                match = _BINDING_RE.search(str(binding))
                if match:
                    field_name = match.group(1)
                    if field_name in product_data:
                        entry["resolved_value"] = str(product_data[field_name])
            rendered_elements.append(entry)
        return {"template_id": template_id, "rendered_elements": rendered_elements}

    def validate_dynamic_bindings(self, template_id: str, available_fields: list[str]) -> list[dict[str, str]]:
        template = self.get_template(template_id)
        errors: list[dict[str, str]] = []
        for element in list(template.get("elements") or []):
            if not isinstance(element, dict):
                continue
            binding = element.get("dynamic_binding")
            if not binding:
                continue
            match = _BINDING_RE.search(str(binding))
            if match:
                field_name = match.group(1)
                if field_name not in available_fields:
                    errors.append({"field": field_name, "binding": str(binding), "error": f"Field '{field_name}' not found in available fields"})
        return errors


template_service = TemplateService()
