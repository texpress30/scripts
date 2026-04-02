"""Catalog schemas define the target fields for each catalog type.

Each advertising channel (Google Shopping, Meta Catalog, TikTok) may have
slight variations, but the base schema per catalog type is shared.
"""

from __future__ import annotations

import enum
from typing import Any


class CatalogType(str, enum.Enum):
    product = "product"
    vehicle = "vehicle"
    vehicle_offer = "vehicle_offer"
    home_listing = "home_listing"
    hotel = "hotel"
    hotel_room = "hotel_room"
    flight = "flight"
    trip = "trip"
    media = "media"


# ---------------------------------------------------------------------------
# Schema definitions per catalog type
# ---------------------------------------------------------------------------

CATALOG_SCHEMAS: dict[CatalogType, dict[str, list[dict[str, Any]]]] = {
    # ------------------------------------------------------------------
    CatalogType.product: {
        "required": [
            {"field": "id", "type": "string", "description": "Unique product ID"},
            {"field": "title", "type": "string", "description": "Product title", "max_length": 150},
            {"field": "description", "type": "string", "description": "Product description"},
            {"field": "link", "type": "url", "description": "Product page URL"},
            {"field": "image_link", "type": "url", "description": "Main product image"},
            {"field": "price", "type": "price", "description": "Product price with currency"},
            {"field": "availability", "type": "enum", "values": ["in_stock", "out_of_stock", "preorder"]},
        ],
        "optional": [
            {"field": "brand", "type": "string", "description": "Product brand"},
            {"field": "gtin", "type": "string", "description": "Global Trade Item Number"},
            {"field": "mpn", "type": "string", "description": "Manufacturer Part Number"},
            {"field": "condition", "type": "enum", "values": ["new", "refurbished", "used"]},
            {"field": "sale_price", "type": "price", "description": "Sale price"},
            {"field": "product_type", "type": "string", "description": "Category path"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
            {"field": "color", "type": "string", "description": "Product color"},
            {"field": "size", "type": "string", "description": "Product size"},
            {"field": "material", "type": "string", "description": "Product material"},
            {"field": "gender", "type": "enum", "values": ["male", "female", "unisex"]},
            {"field": "age_group", "type": "enum", "values": ["newborn", "infant", "toddler", "kids", "adult"]},
            {"field": "shipping_weight", "type": "string", "description": "Shipping weight with unit"},
            {"field": "custom_label_0", "type": "string", "description": "Custom label 0"},
            {"field": "custom_label_1", "type": "string", "description": "Custom label 1"},
            {"field": "custom_label_2", "type": "string", "description": "Custom label 2"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.vehicle: {
        "required": [
            {"field": "vehicle_id", "type": "string", "description": "Unique vehicle ID"},
            {"field": "title", "type": "string", "description": "Vehicle title"},
            {"field": "make", "type": "string", "description": "Manufacturer (BMW, Audi, etc.)"},
            {"field": "model", "type": "string", "description": "Model name"},
            {"field": "year", "type": "integer", "description": "Manufacturing year"},
            {"field": "price", "type": "price", "description": "Vehicle price"},
            {"field": "image_link", "type": "url", "description": "Main vehicle image"},
            {"field": "url", "type": "url", "description": "Vehicle listing URL"},
            {"field": "availability", "type": "enum", "values": ["available", "pending", "sold"]},
        ],
        "optional": [
            {"field": "mileage", "type": "integer", "description": "Mileage in km/miles"},
            {"field": "fuel_type", "type": "enum", "values": ["petrol", "diesel", "electric", "hybrid", "lpg"]},
            {"field": "transmission", "type": "enum", "values": ["automatic", "manual"]},
            {"field": "body_style", "type": "enum", "values": ["sedan", "suv", "hatchback", "coupe", "convertible", "van", "truck"]},
            {"field": "vin", "type": "string", "description": "Vehicle Identification Number"},
            {"field": "exterior_color", "type": "string", "description": "Exterior color"},
            {"field": "interior_color", "type": "string", "description": "Interior color"},
            {"field": "drivetrain", "type": "enum", "values": ["fwd", "rwd", "awd", "4wd"]},
            {"field": "engine", "type": "string", "description": "Engine specs"},
            {"field": "doors", "type": "integer", "description": "Number of doors"},
            {"field": "seats", "type": "integer", "description": "Number of seats"},
            {"field": "description", "type": "string", "description": "Vehicle description"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.vehicle_offer: {
        "required": [
            {"field": "offer_id", "type": "string", "description": "Unique offer ID"},
            {"field": "vehicle_id", "type": "string", "description": "Associated vehicle ID"},
            {"field": "title", "type": "string", "description": "Offer title"},
            {"field": "price", "type": "price", "description": "Offer price"},
            {"field": "url", "type": "url", "description": "Offer URL"},
            {"field": "image_link", "type": "url", "description": "Offer image"},
            {"field": "availability", "type": "enum", "values": ["available", "pending", "sold"]},
        ],
        "optional": [
            {"field": "sale_price", "type": "price", "description": "Discounted price"},
            {"field": "dealer_name", "type": "string", "description": "Dealer name"},
            {"field": "dealer_address", "type": "string", "description": "Dealer address"},
            {"field": "description", "type": "string", "description": "Offer description"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.home_listing: {
        "required": [
            {"field": "home_listing_id", "type": "string", "description": "Unique listing ID"},
            {"field": "name", "type": "string", "description": "Listing title"},
            {"field": "address", "type": "string", "description": "Property address"},
            {"field": "city", "type": "string", "description": "City"},
            {"field": "price", "type": "price", "description": "Listing price"},
            {"field": "image_link", "type": "url", "description": "Main property image"},
            {"field": "url", "type": "url", "description": "Listing URL"},
            {"field": "availability", "type": "enum", "values": ["for_sale", "for_rent", "sold", "rented"]},
        ],
        "optional": [
            {"field": "property_type", "type": "enum", "values": ["apartment", "house", "condo", "land", "commercial"]},
            {"field": "listing_type", "type": "enum", "values": ["sale", "rent"]},
            {"field": "num_beds", "type": "integer", "description": "Number of bedrooms"},
            {"field": "num_baths", "type": "integer", "description": "Number of bathrooms"},
            {"field": "area_size", "type": "number", "description": "Size in sqm/sqft"},
            {"field": "area_unit", "type": "enum", "values": ["sqm", "sqft"]},
            {"field": "year_built", "type": "integer", "description": "Year built"},
            {"field": "parking", "type": "string", "description": "Parking info"},
            {"field": "heating", "type": "string", "description": "Heating type"},
            {"field": "cooling", "type": "string", "description": "Cooling type"},
            {"field": "description", "type": "string", "description": "Property description"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
            {"field": "latitude", "type": "number", "description": "Latitude"},
            {"field": "longitude", "type": "number", "description": "Longitude"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.hotel: {
        "required": [
            {"field": "hotel_id", "type": "string", "description": "Unique hotel ID"},
            {"field": "name", "type": "string", "description": "Hotel name"},
            {"field": "address", "type": "string", "description": "Hotel address"},
            {"field": "city", "type": "string", "description": "City"},
            {"field": "image_link", "type": "url", "description": "Main hotel image"},
            {"field": "url", "type": "url", "description": "Hotel page URL"},
        ],
        "optional": [
            {"field": "star_rating", "type": "number", "description": "1-5 stars"},
            {"field": "brand", "type": "string", "description": "Hotel brand/chain"},
            {"field": "amenities", "type": "list", "description": "List of amenities"},
            {"field": "description", "type": "string", "description": "Hotel description"},
            {"field": "latitude", "type": "number", "description": "Latitude"},
            {"field": "longitude", "type": "number", "description": "Longitude"},
            {"field": "phone", "type": "string", "description": "Phone number"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.hotel_room: {
        "required": [
            {"field": "hotel_id", "type": "string", "description": "Parent hotel ID"},
            {"field": "room_id", "type": "string", "description": "Unique room ID"},
            {"field": "name", "type": "string", "description": "Room name/type"},
            {"field": "price", "type": "price", "description": "Nightly rate"},
            {"field": "url", "type": "url", "description": "Booking URL"},
            {"field": "image_link", "type": "url", "description": "Room image"},
        ],
        "optional": [
            {"field": "description", "type": "string", "description": "Room description"},
            {"field": "max_occupancy", "type": "integer", "description": "Max guests"},
            {"field": "bed_type", "type": "string", "description": "Bed configuration"},
            {"field": "amenities", "type": "list", "description": "Room amenities"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.flight: {
        "required": [
            {"field": "flight_id", "type": "string", "description": "Unique flight ID"},
            {"field": "origin", "type": "string", "description": "Origin airport code"},
            {"field": "destination", "type": "string", "description": "Destination airport code"},
            {"field": "price", "type": "price", "description": "Flight price"},
            {"field": "url", "type": "url", "description": "Booking URL"},
            {"field": "image_link", "type": "url", "description": "Destination image"},
        ],
        "optional": [
            {"field": "airline", "type": "string", "description": "Airline name"},
            {"field": "departure_date", "type": "string", "description": "Departure date"},
            {"field": "return_date", "type": "string", "description": "Return date"},
            {"field": "cabin_class", "type": "enum", "values": ["economy", "premium_economy", "business", "first"]},
            {"field": "description", "type": "string", "description": "Flight description"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.trip: {
        "required": [
            {"field": "trip_id", "type": "string", "description": "Unique trip ID"},
            {"field": "title", "type": "string", "description": "Trip title"},
            {"field": "destination", "type": "string", "description": "Destination"},
            {"field": "price", "type": "price", "description": "Trip price"},
            {"field": "url", "type": "url", "description": "Booking URL"},
            {"field": "image_link", "type": "url", "description": "Trip image"},
        ],
        "optional": [
            {"field": "description", "type": "string", "description": "Trip description"},
            {"field": "duration", "type": "string", "description": "Trip duration"},
            {"field": "start_date", "type": "string", "description": "Start date"},
            {"field": "end_date", "type": "string", "description": "End date"},
            {"field": "additional_image_link", "type": "url", "description": "Additional images"},
        ],
    },
    # ------------------------------------------------------------------
    CatalogType.media: {
        "required": [
            {"field": "media_id", "type": "string", "description": "Unique media ID"},
            {"field": "title", "type": "string", "description": "Media title"},
            {"field": "url", "type": "url", "description": "Media URL"},
            {"field": "image_link", "type": "url", "description": "Thumbnail/poster"},
        ],
        "optional": [
            {"field": "description", "type": "string", "description": "Media description"},
            {"field": "media_type", "type": "enum", "values": ["movie", "tv_show", "music", "podcast", "book", "game"]},
            {"field": "genre", "type": "string", "description": "Genre"},
            {"field": "rating", "type": "string", "description": "Content rating"},
            {"field": "price", "type": "price", "description": "Price"},
            {"field": "availability", "type": "enum", "values": ["available", "preorder", "unavailable"]},
            {"field": "release_date", "type": "string", "description": "Release date"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_catalog_schema(catalog_type: CatalogType) -> dict[str, list[dict[str, Any]]]:
    """Return the full schema (required + optional) for a catalog type."""
    return CATALOG_SCHEMAS.get(catalog_type, CATALOG_SCHEMAS[CatalogType.product])


def get_required_fields(catalog_type: CatalogType) -> list[str]:
    """Return the list of required field names for a catalog type."""
    schema = get_catalog_schema(catalog_type)
    return [f["field"] for f in schema.get("required", [])]


def get_all_fields(catalog_type: CatalogType) -> list[dict[str, Any]]:
    """Return all fields (required + optional) for a catalog type."""
    schema = get_catalog_schema(catalog_type)
    return schema.get("required", []) + schema.get("optional", [])


def validate_mapping_completeness(
    catalog_type: CatalogType,
    mapped_fields: list[str],
) -> dict[str, Any]:
    """Check whether all required fields are mapped.

    Returns a dict with ``is_complete``, ``missing_required``,
    ``mapped_count``, and ``required_count``.
    """
    required = get_required_fields(catalog_type)
    missing = [f for f in required if f not in mapped_fields]
    return {
        "is_complete": len(missing) == 0,
        "missing_required": missing,
        "mapped_count": len(mapped_fields),
        "required_count": len(required),
    }
