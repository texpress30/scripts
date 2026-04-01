from __future__ import annotations


class TemplateNotFoundError(Exception):
    def __init__(self, template_id: str) -> None:
        super().__init__(f"Creative template not found: {template_id}")
        self.template_id = template_id


class TreatmentNotFoundError(Exception):
    def __init__(self, treatment_id: str) -> None:
        super().__init__(f"Treatment not found: {treatment_id}")
        self.treatment_id = treatment_id


class InvalidDynamicBindingError(Exception):
    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(f"Invalid dynamic binding '{field_name}': {reason}")
        self.field_name = field_name
        self.reason = reason


class TreatmentFilterError(Exception):
    def __init__(self, filter_field: str, reason: str) -> None:
        super().__init__(f"Treatment filter error on '{filter_field}': {reason}")
        self.filter_field = filter_field
        self.reason = reason
