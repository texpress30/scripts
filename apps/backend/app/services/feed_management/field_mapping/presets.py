"""Built-in mapping presets per (catalog_type, target_channel) combination.

When a user creates a new field mapping they can choose *from_preset=True*
to auto-populate rules based on the standard mapping for their combination.
"""

from __future__ import annotations

from app.services.feed_management.catalog_schemas import CatalogType
from app.services.feed_management.field_mapping.models import (
    FieldMappingRuleCreate,
    TargetChannel,
    TransformationType,
)


def _r(
    target: str,
    source: str | None = None,
    tt: TransformationType = TransformationType.direct,
    required: bool = False,
    order: int = 0,
    **config: object,
) -> FieldMappingRuleCreate:
    return FieldMappingRuleCreate(
        target_field=target,
        source_field=source,
        transformation_type=tt,
        transformation_config=dict(config) if config else {},
        is_required=required,
        sort_order=order,
    )


# -----------------------------------------------------------------------
# Product presets
# -----------------------------------------------------------------------

_PRODUCT_GOOGLE: list[FieldMappingRuleCreate] = [
    _r("id",             "data.id",              required=True, order=0),
    _r("title",          "data.title",           required=True, order=1, tt=TransformationType.truncate, max_length=150),
    _r("description",    "data.description",     required=True, order=2),
    _r("link",           "data.url",             required=True, order=3),
    _r("image_link",     "data.images.0",        required=True, order=4),
    _r("price",          "data.price",           required=True, order=5, tt=TransformationType.template, template="{data.price} {data.currency}"),
    _r("availability",   None,                   required=True, order=6, tt=TransformationType.conditional,
       condition_field="data.inventory_quantity", condition_value="0", then_value="out_of_stock", else_value="in_stock"),
    _r("brand",          "data.category",        order=7),
    _r("condition",      None,                   order=8, tt=TransformationType.static, value="new"),
    _r("product_type",   "data.category",        order=9),
]

_PRODUCT_META: list[FieldMappingRuleCreate] = [
    _r("id",             "data.id",              required=True, order=0),
    _r("title",          "data.title",           required=True, order=1),
    _r("description",    "data.description",     required=True, order=2),
    _r("link",           "data.url",             required=True, order=3),
    _r("image_link",     "data.images.0",        required=True, order=4),
    _r("price",          "data.price",           required=True, order=5, tt=TransformationType.template, template="{data.price} {data.currency}"),
    _r("availability",   None,                   required=True, order=6, tt=TransformationType.conditional,
       condition_field="data.inventory_quantity", condition_value="0", then_value="out of stock", else_value="in stock"),
    _r("brand",          "data.category",        order=7),
    _r("condition",      None,                   order=8, tt=TransformationType.static, value="new"),
]

_PRODUCT_TIKTOK: list[FieldMappingRuleCreate] = [
    _r("id",             "data.id",              required=True, order=0),
    _r("title",          "data.title",           required=True, order=1),
    _r("description",    "data.description",     required=True, order=2),
    _r("link",           "data.url",             required=True, order=3),
    _r("image_link",     "data.images.0",        required=True, order=4),
    _r("price",          "data.price",           required=True, order=5, tt=TransformationType.template, template="{data.price} {data.currency}"),
    _r("availability",   None,                   required=True, order=6, tt=TransformationType.conditional,
       condition_field="data.inventory_quantity", condition_value="0", then_value="out_of_stock", else_value="in_stock"),
]

# -----------------------------------------------------------------------
# Vehicle presets
# -----------------------------------------------------------------------

_VEHICLE_GOOGLE: list[FieldMappingRuleCreate] = [
    _r("vehicle_id",     "data.id",              required=True, order=0),
    _r("title",          "data.title",           required=True, order=1),
    _r("make",           "data.category",        required=True, order=2),
    _r("model",          "data.title",           required=True, order=3),
    _r("year",           "data.sku",             required=True, order=4),
    _r("price",          "data.price",           required=True, order=5, tt=TransformationType.template, template="{data.price} {data.currency}"),
    _r("image_link",     "data.images.0",        required=True, order=6),
    _r("url",            "data.url",             required=True, order=7),
    _r("availability",   None,                   required=True, order=8, tt=TransformationType.static, value="available"),
    _r("mileage",        "data.inventory_quantity", order=9),
    _r("description",    "data.description",     order=10),
]

_VEHICLE_META: list[FieldMappingRuleCreate] = _VEHICLE_GOOGLE  # same base for now

# -----------------------------------------------------------------------
# Home listing presets
# -----------------------------------------------------------------------

_HOME_LISTING_GOOGLE: list[FieldMappingRuleCreate] = [
    _r("home_listing_id", "data.id",             required=True, order=0),
    _r("name",           "data.title",           required=True, order=1),
    _r("address",        "data.description",     required=True, order=2),
    _r("city",           "data.category",        required=True, order=3),
    _r("price",          "data.price",           required=True, order=4, tt=TransformationType.template, template="{data.price} {data.currency}"),
    _r("image_link",     "data.images.0",        required=True, order=5),
    _r("url",            "data.url",             required=True, order=6),
    _r("availability",   None,                   required=True, order=7, tt=TransformationType.static, value="for_sale"),
]

_HOME_LISTING_META: list[FieldMappingRuleCreate] = _HOME_LISTING_GOOGLE

# -----------------------------------------------------------------------
# Hotel presets
# -----------------------------------------------------------------------

_HOTEL_GOOGLE: list[FieldMappingRuleCreate] = [
    _r("hotel_id",       "data.id",              required=True, order=0),
    _r("name",           "data.title",           required=True, order=1),
    _r("address",        "data.description",     required=True, order=2),
    _r("city",           "data.category",        required=True, order=3),
    _r("image_link",     "data.images.0",        required=True, order=4),
    _r("url",            "data.url",             required=True, order=5),
]

# -----------------------------------------------------------------------
# Preset registry
# -----------------------------------------------------------------------

_PRESETS: dict[tuple[CatalogType, TargetChannel], list[FieldMappingRuleCreate]] = {
    # Product
    (CatalogType.product, TargetChannel.google_shopping): _PRODUCT_GOOGLE,
    (CatalogType.product, TargetChannel.meta_catalog):    _PRODUCT_META,
    (CatalogType.product, TargetChannel.tiktok_catalog):  _PRODUCT_TIKTOK,
    (CatalogType.product, TargetChannel.custom):          _PRODUCT_GOOGLE,
    # Vehicle
    (CatalogType.vehicle, TargetChannel.google_shopping): _VEHICLE_GOOGLE,
    (CatalogType.vehicle, TargetChannel.meta_catalog):    _VEHICLE_META,
    (CatalogType.vehicle, TargetChannel.custom):          _VEHICLE_GOOGLE,
    # Home listing
    (CatalogType.home_listing, TargetChannel.google_shopping): _HOME_LISTING_GOOGLE,
    (CatalogType.home_listing, TargetChannel.meta_catalog):    _HOME_LISTING_META,
    (CatalogType.home_listing, TargetChannel.custom):          _HOME_LISTING_GOOGLE,
    # Hotel
    (CatalogType.hotel, TargetChannel.google_shopping): _HOTEL_GOOGLE,
    (CatalogType.hotel, TargetChannel.custom):          _HOTEL_GOOGLE,
}


def get_preset(
    catalog_type: CatalogType,
    channel: TargetChannel,
) -> list[FieldMappingRuleCreate]:
    """Return the preset rules for a (catalog_type, channel) pair.

    Falls back to the ``custom`` channel preset or an empty list.
    """
    key = (catalog_type, channel)
    if key in _PRESETS:
        return _PRESETS[key]
    fallback = (catalog_type, TargetChannel.custom)
    return _PRESETS.get(fallback, [])


def list_available_presets() -> list[dict[str, str]]:
    """Return a list of all available preset keys."""
    return [
        {"catalog_type": ct.value, "target_channel": ch.value}
        for ct, ch in _PRESETS
    ]
