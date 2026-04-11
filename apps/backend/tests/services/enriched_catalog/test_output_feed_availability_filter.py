"""Unit tests for the stock/availability filter in ``_fetch_products``.

The filter is the hook that keeps out-of-stock products out of published
feeds by default. We only exercise the pure predicate here; the MongoDB
path is covered by integration tests.
"""

from __future__ import annotations

from app.services.enriched_catalog.output_feed_service import _is_product_unavailable


class TestUnavailablePredicate:
    def test_in_stock_product_kept(self):
        assert (
            _is_product_unavailable({"availability": "in_stock", "inventory_quantity": 5})
            is False
        )

    def test_out_of_stock_string_excluded(self):
        assert _is_product_unavailable({"availability": "out_of_stock"}) is True

    def test_discontinued_excluded(self):
        assert _is_product_unavailable({"availability": "discontinued"}) is True

    def test_zero_inventory_excluded(self):
        assert _is_product_unavailable({"inventory_quantity": 0}) is True

    def test_negative_inventory_excluded(self):
        assert _is_product_unavailable({"inventory_quantity": -3}) is True

    def test_missing_inventory_kept(self):
        # Defensive: connectors that don't report stock shouldn't have their
        # products silently dropped.
        assert _is_product_unavailable({"title": "Shoe"}) is False

    def test_availability_with_spaces_normalized(self):
        assert _is_product_unavailable({"availability": "out of stock"}) is True

    def test_non_dict_input_kept(self):
        assert _is_product_unavailable("not a dict") is False  # type: ignore[arg-type]
