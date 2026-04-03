"""Rich catalog field schemas with Google/Facebook attribute mappings.

.. deprecated::
    DEPRECATED: This file is used as fallback only.
    Primary source of truth is now the ``feed_schema_fields`` table.
    See migrations 0040 (schema registry DDL) and 0041 (vehicle seed data).
    New fields should be added via CSV import or direct DB inserts.

Each catalog type has a list of ``CatalogField`` entries that describe every
target field — its type, whether it is required, its Google Merchant Center
attribute name, Facebook catalog attribute name, and so on.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel


class FieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    PRICE = "price"  # Format: "123.45 RON"
    URL = "url"
    IMAGE_URL = "image_url"
    ENUM = "enum"  # Valori predefinite
    DATE = "date"
    BOOLEAN = "boolean"


class CatalogField(BaseModel):
    name: str  # ex: "title", "price", "make"
    display_name: str  # ex: "Title", "Price", "Make"
    description: str
    field_type: FieldType
    required: bool
    category: str  # "basic", "identifiers", "detailed", "shipping", "vehicle_specific", etc.
    enum_values: List[str] | None = None  # Pentru FieldType.ENUM
    google_attribute: str | None = None  # Numele atributului în Google (g:title, g:price)
    facebook_attribute: str | None = None  # Numele în Facebook
    example: str | None = None


# ---------------------------------------------------------------------------
# Câmpuri comune pentru TOATE cataloagele
# ---------------------------------------------------------------------------

COMMON_FIELDS: List[CatalogField] = [
    CatalogField(
        name="id",
        display_name="ID",
        description="Unique identifier for the item",
        field_type=FieldType.STRING,
        required=True,
        category="basic",
        google_attribute="g:id",
        facebook_attribute="id",
        example="SKU123",
    ),
    CatalogField(
        name="title",
        display_name="Title",
        description="Title of the item",
        field_type=FieldType.STRING,
        required=True,
        category="basic",
        google_attribute="g:title",
        facebook_attribute="title",
        example="Blue T-Shirt - Size M",
    ),
    CatalogField(
        name="description",
        display_name="Description",
        description="Description of the item",
        field_type=FieldType.STRING,
        required=True,
        category="basic",
        google_attribute="g:description",
        facebook_attribute="description",
    ),
    CatalogField(
        name="link",
        display_name="Link",
        description="URL to the item's page",
        field_type=FieldType.URL,
        required=True,
        category="basic",
        google_attribute="g:link",
        facebook_attribute="link",
    ),
    CatalogField(
        name="image_link",
        display_name="Image Link",
        description="URL of the main image",
        field_type=FieldType.IMAGE_URL,
        required=True,
        category="basic",
        google_attribute="g:image_link",
        facebook_attribute="image_link",
    ),
    CatalogField(
        name="price",
        display_name="Price",
        description="Price of the item",
        field_type=FieldType.PRICE,
        required=True,
        category="basic",
        google_attribute="g:price",
        facebook_attribute="price",
        example="29.99 USD",
    ),
    CatalogField(
        name="availability",
        display_name="Availability",
        description="Stock status",
        field_type=FieldType.ENUM,
        required=True,
        category="basic",
        enum_values=["in_stock", "out_of_stock", "preorder", "backorder"],
        google_attribute="g:availability",
        facebook_attribute="availability",
    ),
]

# ---------------------------------------------------------------------------
# Câmpuri specifice PRODUCT (eCommerce)
# ---------------------------------------------------------------------------

PRODUCT_FIELDS: List[CatalogField] = COMMON_FIELDS + [
    CatalogField(
        name="brand",
        display_name="Brand",
        description="Brand of the product",
        field_type=FieldType.STRING,
        required=False,
        category="identifiers",
        google_attribute="g:brand",
        facebook_attribute="brand",
    ),
    CatalogField(
        name="gtin",
        display_name="GTIN",
        description="Global Trade Item Number (UPC, EAN, ISBN)",
        field_type=FieldType.STRING,
        required=False,
        category="identifiers",
        google_attribute="g:gtin",
    ),
    CatalogField(
        name="mpn",
        display_name="MPN",
        description="Manufacturer Part Number",
        field_type=FieldType.STRING,
        required=False,
        category="identifiers",
        google_attribute="g:mpn",
    ),
    CatalogField(
        name="condition",
        display_name="Condition",
        description="Condition of the product",
        field_type=FieldType.ENUM,
        required=False,
        category="detailed",
        enum_values=["new", "refurbished", "used"],
        google_attribute="g:condition",
        facebook_attribute="condition",
    ),
    CatalogField(
        name="sale_price",
        display_name="Sale Price",
        description="Discounted price",
        field_type=FieldType.PRICE,
        required=False,
        category="pricing",
        google_attribute="g:sale_price",
        facebook_attribute="sale_price",
    ),
    CatalogField(
        name="google_product_category",
        display_name="Google Product Category",
        description="Google's product taxonomy category",
        field_type=FieldType.STRING,
        required=False,
        category="categorization",
        google_attribute="g:google_product_category",
    ),
    CatalogField(
        name="product_type",
        display_name="Product Type",
        description="Your product category",
        field_type=FieldType.STRING,
        required=False,
        category="categorization",
        google_attribute="g:product_type",
        facebook_attribute="product_type",
    ),
    CatalogField(
        name="color",
        display_name="Color",
        description="Color of the product",
        field_type=FieldType.STRING,
        required=False,  # Required for apparel
        category="variants",
        google_attribute="g:color",
        facebook_attribute="color",
    ),
    CatalogField(
        name="size",
        display_name="Size",
        description="Size of the product",
        field_type=FieldType.STRING,
        required=False,  # Required for apparel
        category="variants",
        google_attribute="g:size",
        facebook_attribute="size",
    ),
    CatalogField(
        name="gender",
        display_name="Gender",
        description="Target gender",
        field_type=FieldType.ENUM,
        required=False,
        category="variants",
        enum_values=["male", "female", "unisex"],
        google_attribute="g:gender",
        facebook_attribute="gender",
    ),
    CatalogField(
        name="age_group",
        display_name="Age Group",
        description="Target age group",
        field_type=FieldType.ENUM,
        required=False,
        category="variants",
        enum_values=["newborn", "infant", "toddler", "kids", "adult"],
        google_attribute="g:age_group",
        facebook_attribute="age_group",
    ),
    CatalogField(
        name="material",
        display_name="Material",
        description="Material of the product",
        field_type=FieldType.STRING,
        required=False,
        category="detailed",
        google_attribute="g:material",
    ),
    CatalogField(
        name="pattern",
        display_name="Pattern",
        description="Pattern or print",
        field_type=FieldType.STRING,
        required=False,
        category="detailed",
        google_attribute="g:pattern",
    ),
    CatalogField(
        name="additional_image_link",
        display_name="Additional Images",
        description="Additional product images",
        field_type=FieldType.IMAGE_URL,
        required=False,
        category="media",
        google_attribute="g:additional_image_link",
        facebook_attribute="additional_image_link",
    ),
    CatalogField(
        name="shipping_weight",
        display_name="Shipping Weight",
        description="Weight for shipping calculation",
        field_type=FieldType.STRING,
        required=False,
        category="shipping",
        google_attribute="g:shipping_weight",
        example="2.5 kg",
    ),
]

# ---------------------------------------------------------------------------
# Câmpuri specifice VEHICLE
# ---------------------------------------------------------------------------

VEHICLE_FIELDS: List[CatalogField] = COMMON_FIELDS + [
    CatalogField(
        name="vin",
        display_name="VIN",
        description="Vehicle Identification Number",
        field_type=FieldType.STRING,
        required=True,
        category="identifiers",
        google_attribute="vin",
    ),
    CatalogField(
        name="make",
        display_name="Make",
        description="Vehicle manufacturer (e.g., Toyota, Ford)",
        field_type=FieldType.STRING,
        required=True,
        category="vehicle_basic",
        google_attribute="make",
    ),
    CatalogField(
        name="model",
        display_name="Model",
        description="Vehicle model (e.g., Camry, F-150)",
        field_type=FieldType.STRING,
        required=True,
        category="vehicle_basic",
        google_attribute="model",
    ),
    CatalogField(
        name="year",
        display_name="Year",
        description="Manufacturing year",
        field_type=FieldType.NUMBER,
        required=True,
        category="vehicle_basic",
        google_attribute="year",
        example="2023",
    ),
    CatalogField(
        name="trim",
        display_name="Trim",
        description="Trim level (e.g., SE, Limited)",
        field_type=FieldType.STRING,
        required=False,
        category="vehicle_basic",
        google_attribute="trim",
    ),
    CatalogField(
        name="mileage",
        display_name="Mileage",
        description="Odometer reading",
        field_type=FieldType.STRING,
        required=True,
        category="vehicle_details",
        google_attribute="mileage",
        example="50000 km",
    ),
    CatalogField(
        name="vehicle_condition",
        display_name="Condition",
        description="New or used",
        field_type=FieldType.ENUM,
        required=True,
        category="vehicle_basic",
        enum_values=["new", "used"],
        google_attribute="condition",
    ),
    CatalogField(
        name="fuel_type",
        display_name="Fuel Type",
        description="Type of fuel",
        field_type=FieldType.ENUM,
        required=False,
        category="vehicle_details",
        enum_values=["gasoline", "diesel", "electric", "hybrid", "plugin_hybrid", "lpg"],
        google_attribute="fuel",
    ),
    CatalogField(
        name="transmission",
        display_name="Transmission",
        description="Transmission type",
        field_type=FieldType.ENUM,
        required=False,
        category="vehicle_details",
        enum_values=["automatic", "manual"],
        google_attribute="transmission",
    ),
    CatalogField(
        name="body_style",
        display_name="Body Style",
        description="Vehicle body type",
        field_type=FieldType.ENUM,
        required=False,
        category="vehicle_details",
        enum_values=["sedan", "suv", "truck", "coupe", "convertible", "van", "wagon", "hatchback"],
        google_attribute="body_style",
    ),
    CatalogField(
        name="exterior_color",
        display_name="Exterior Color",
        description="Exterior color",
        field_type=FieldType.STRING,
        required=False,
        category="vehicle_details",
        google_attribute="color",
    ),
    CatalogField(
        name="interior_color",
        display_name="Interior Color",
        description="Interior color",
        field_type=FieldType.STRING,
        required=False,
        category="vehicle_details",
    ),
    CatalogField(
        name="drivetrain",
        display_name="Drivetrain",
        description="Drive system (e.g., AWD, FWD)",
        field_type=FieldType.ENUM,
        required=False,
        category="vehicle_details",
        enum_values=["fwd", "rwd", "awd", "4wd"],
    ),
    CatalogField(
        name="engine",
        display_name="Engine",
        description="Engine specification",
        field_type=FieldType.STRING,
        required=False,
        category="vehicle_details",
        google_attribute="engine",
        example="2.0L 4-cylinder",
    ),
    CatalogField(
        name="store_code",
        display_name="Store Code",
        description="Dealership location code",
        field_type=FieldType.STRING,
        required=True,
        category="dealer",
        google_attribute="store_code",
    ),
    CatalogField(
        name="dealership_name",
        display_name="Dealership Name",
        description="Name of the dealership",
        field_type=FieldType.STRING,
        required=False,
        category="dealer",
        google_attribute="dealership_name",
    ),
]

# ---------------------------------------------------------------------------
# Câmpuri specifice HOTEL
# ---------------------------------------------------------------------------

HOTEL_FIELDS: List[CatalogField] = COMMON_FIELDS + [
    CatalogField(
        name="hotel_id",
        display_name="Hotel ID",
        description="Unique hotel identifier",
        field_type=FieldType.STRING,
        required=True,
        category="identifiers",
    ),
    CatalogField(
        name="destination_id",
        display_name="Destination ID",
        description="Location/destination identifier",
        field_type=FieldType.STRING,
        required=False,
        category="location",
    ),
    CatalogField(
        name="star_rating",
        display_name="Star Rating",
        description="Hotel star rating",
        field_type=FieldType.NUMBER,
        required=False,
        category="details",
        example="4",
    ),
    CatalogField(
        name="address",
        display_name="Address",
        description="Hotel address",
        field_type=FieldType.STRING,
        required=True,
        category="location",
    ),
    CatalogField(
        name="neighborhood",
        display_name="Neighborhood",
        description="Area or neighborhood",
        field_type=FieldType.STRING,
        required=False,
        category="location",
    ),
    CatalogField(
        name="amenities",
        display_name="Amenities",
        description="List of hotel amenities",
        field_type=FieldType.STRING,
        required=False,
        category="details",
    ),
]

# ---------------------------------------------------------------------------
# Câmpuri specifice HOME_LISTING (Real Estate)
# ---------------------------------------------------------------------------

HOME_LISTING_FIELDS: List[CatalogField] = COMMON_FIELDS + [
    CatalogField(
        name="listing_type",
        display_name="Listing Type",
        description="For sale or for rent",
        field_type=FieldType.ENUM,
        required=True,
        category="basic",
        enum_values=["for_sale", "for_rent"],
    ),
    CatalogField(
        name="property_type",
        display_name="Property Type",
        description="Type of property",
        field_type=FieldType.ENUM,
        required=True,
        category="details",
        enum_values=["apartment", "house", "condo", "townhouse", "land", "commercial"],
    ),
    CatalogField(
        name="address",
        display_name="Address",
        description="Property address",
        field_type=FieldType.STRING,
        required=True,
        category="location",
    ),
    CatalogField(
        name="city",
        display_name="City",
        description="City name",
        field_type=FieldType.STRING,
        required=True,
        category="location",
    ),
    CatalogField(
        name="num_beds",
        display_name="Bedrooms",
        description="Number of bedrooms",
        field_type=FieldType.NUMBER,
        required=False,
        category="details",
    ),
    CatalogField(
        name="num_baths",
        display_name="Bathrooms",
        description="Number of bathrooms",
        field_type=FieldType.NUMBER,
        required=False,
        category="details",
    ),
    CatalogField(
        name="area",
        display_name="Area",
        description="Property area in sqm or sqft",
        field_type=FieldType.STRING,
        required=False,
        category="details",
        example="120 sqm",
    ),
    CatalogField(
        name="year_built",
        display_name="Year Built",
        description="Construction year",
        field_type=FieldType.NUMBER,
        required=False,
        category="details",
    ),
]

# ---------------------------------------------------------------------------
# Mapping catalog type -> fields
# ---------------------------------------------------------------------------

CATALOG_FIELD_SCHEMAS: Dict[str, List[CatalogField]] = {
    "product": PRODUCT_FIELDS,
    "vehicle": VEHICLE_FIELDS,
    "vehicle_offer": VEHICLE_FIELDS,  # Same as vehicle
    "hotel": HOTEL_FIELDS,
    "hotel_room": HOTEL_FIELDS,
    "home_listing": HOME_LISTING_FIELDS,
    "flight": COMMON_FIELDS,  # TODO: Add flight-specific fields
    "trip": COMMON_FIELDS,  # TODO: Add trip-specific fields
    "media": COMMON_FIELDS,  # TODO: Add media-specific fields
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_catalog_fields(catalog_type: str) -> List[CatalogField]:
    """Returnează câmpurile pentru un tip de catalog."""
    return CATALOG_FIELD_SCHEMAS.get(catalog_type, COMMON_FIELDS)


def get_required_fields(catalog_type: str) -> List[CatalogField]:
    """Returnează doar câmpurile required pentru un catalog."""
    return [f for f in get_catalog_fields(catalog_type) if f.required]


def get_optional_fields(catalog_type: str) -> List[CatalogField]:
    """Returnează câmpurile opționale pentru un catalog."""
    return [f for f in get_catalog_fields(catalog_type) if not f.required]


def get_fields_by_category(catalog_type: str, category: str) -> List[CatalogField]:
    """Returnează câmpurile dintr-o anumită categorie."""
    return [f for f in get_catalog_fields(catalog_type) if f.category == category]
