from __future__ import annotations

from typing import Any

from app.services.enriched_catalog.repository import treatment_repository


class EnrichedFeedResult:
    def __init__(self, output_feed_id: str, entries: list[dict[str, Any]]) -> None:
        self.output_feed_id = output_feed_id
        self.entries = entries
        self.total = len(entries)

    def to_dict(self) -> dict[str, Any]:
        return {"output_feed_id": self.output_feed_id, "total": self.total, "entries": self.entries}


class EnrichedFeedGenerator:
    """Generates an enriched feed by matching products to treatments.

    Actual image rendering is NOT done here — this prepares
    the feed data structure (JSON) with template assignments.
    """

    def __init__(self, treatment_repo=None) -> None:
        self._treatment_repo = treatment_repo or treatment_repository

    def generate_feed(self, output_feed_id: str, products: list[dict[str, Any]]) -> EnrichedFeedResult:
        entries: list[dict[str, Any]] = []
        for product in products:
            product_id = str(product.get("id") or product.get("product_id") or "")
            treatment = self._treatment_repo.get_matching_treatment(output_feed_id, product)
            entry: dict[str, Any] = {
                "product_id": product_id,
                "product_data": product,
                "template_id": None,
                "treatment_id": None,
            }
            if treatment is not None:
                entry["template_id"] = treatment.get("template_id")
                entry["treatment_id"] = treatment.get("id")
            entries.append(entry)
        return EnrichedFeedResult(output_feed_id=output_feed_id, entries=entries)


enriched_feed_generator = EnrichedFeedGenerator()
