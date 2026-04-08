"""Pydantic schemas for the Magento 2 Feed Integration (OAuth 1.0a).

These sit alongside the generic ``FeedSourceCreate`` / ``FeedSourceResponse``
models in ``services/feed_management/models.py`` and provide a narrower,
Magento-specific API surface used by the Add New Source wizard.

Credentials are accepted as ``SecretStr`` on input to avoid accidental
logging, and response models expose only a masked suffix (``"****abcd"``).
The four OAuth 1.0a credentials themselves are persisted encrypted-at-rest
via ``app.services.integration_secrets_store`` (Fernet); this module never
writes plaintext secrets to the ``feed_sources`` row itself.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator

from app.integrations.magento.config import (
    DEFAULT_STORE_CODE,
    validate_magento_base_url,
    validate_magento_store_code,
)


def mask_secret(value: str | None) -> str:
    """Return a masked representation that keeps only the last 4 characters.

    ``None`` or empty strings collapse to ``""``. Short values (< 8 chars)
    are fully masked so we never leak most of a tiny secret.
    """
    if not value:
        return ""
    trimmed = str(value)
    if len(trimmed) <= 8:
        return "*" * len(trimmed)
    return f"****{trimmed[-4:]}"


class MagentoSourceCreate(BaseModel):
    """Request payload for creating a new Magento feed source.

    ``HttpUrl`` performs structural validation (scheme, host); the stricter
    production-vs-dev rules live in :func:`validate_magento_base_url` and
    run inside the ``base_url`` validator.
    """

    source_name: str = Field(min_length=1, max_length=255)
    magento_base_url: HttpUrl
    consumer_key: str = Field(min_length=1)
    consumer_secret: SecretStr
    access_token: str = Field(min_length=1)
    access_token_secret: SecretStr
    magento_store_code: str = Field(default=DEFAULT_STORE_CODE, min_length=1, max_length=100)
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"

    @field_validator("magento_base_url", mode="after")
    @classmethod
    def _validate_base_url(cls, value: HttpUrl) -> HttpUrl:
        validate_magento_base_url(str(value))
        return value

    @field_validator("magento_store_code", mode="before")
    @classmethod
    def _validate_store_code(cls, value: str | None) -> str:
        return validate_magento_store_code(value)

    def normalised_base_url(self) -> str:
        return validate_magento_base_url(str(self.magento_base_url))

    def dump_credentials(self) -> dict[str, str]:
        """Return the four OAuth 1.0a credentials in plaintext form, ready
        to be handed to ``magento_service.store_magento_credentials``."""
        return {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret.get_secret_value(),
            "access_token": self.access_token,
            "access_token_secret": self.access_token_secret.get_secret_value(),
        }


class MagentoSourceResponse(BaseModel):
    """Response payload for a Magento feed source — never returns secrets.

    The four OAuth 1.0a credentials are always masked to the last 4 chars.
    ``has_credentials`` lets the frontend show a "credentials stored" badge
    without needing to fetch the secret values.
    """

    id: str
    subaccount_id: int
    source_name: str
    magento_base_url: str
    magento_store_code: str
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    connection_status: str = "pending"
    has_credentials: bool = False
    consumer_key_masked: str = ""
    consumer_secret_masked: str = ""
    access_token_masked: str = ""
    access_token_secret_masked: str = ""
    last_connection_check: str | None = None
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_source_and_credentials(
        cls,
        *,
        source_id: str,
        subaccount_id: int,
        source_name: str,
        magento_base_url: str,
        magento_store_code: str,
        catalog_type: str,
        catalog_variant: str,
        connection_status: str,
        credentials: dict[str, str] | None,
        last_connection_check: str | None = None,
        last_error: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> "MagentoSourceResponse":
        creds = credentials or {}
        has_creds = bool(
            creds.get("consumer_key")
            and creds.get("consumer_secret")
            and creds.get("access_token")
            and creds.get("access_token_secret")
        )
        return cls(
            id=str(source_id),
            subaccount_id=int(subaccount_id),
            source_name=str(source_name),
            magento_base_url=str(magento_base_url),
            magento_store_code=str(magento_store_code),
            catalog_type=str(catalog_type),
            catalog_variant=str(catalog_variant),
            connection_status=str(connection_status),
            has_credentials=has_creds,
            consumer_key_masked=mask_secret(creds.get("consumer_key")),
            consumer_secret_masked=mask_secret(creds.get("consumer_secret")),
            access_token_masked=mask_secret(creds.get("access_token")),
            access_token_secret_masked=mask_secret(creds.get("access_token_secret")),
            last_connection_check=last_connection_check,
            last_error=last_error,
            created_at=created_at,
            updated_at=updated_at,
        )
