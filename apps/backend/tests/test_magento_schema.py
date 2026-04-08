"""Tests for the Magento 2 OAuth 1.0a schema, config helpers, and credential service.

Covers:
* ``app.integrations.magento.config`` — base URL validation (scheme + host
  rules, trailing-slash normalisation) and store code validation.
* ``app.integrations.magento.schemas`` — ``MagentoSourceCreate`` input
  validation + ``MagentoSourceResponse.from_source_and_credentials`` masking.
* ``app.integrations.magento.service`` — the four-credential upsert/get/delete
  helpers, exercised against an in-memory fake of
  ``integration_secrets_store``.
* ``FeedSourceCreate`` / ``FeedSourceResponse`` — backwards-compat with the
  new ``magento_base_url`` / ``magento_store_code`` fields (defaults to None,
  existing Shopify/CSV rows unaffected).

No database or network: the secrets store is monkey-patched in-process.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from pydantic import ValidationError

from app.integrations.magento import config as magento_config
from app.integrations.magento import schemas as magento_schemas
from app.integrations.magento import service as magento_service
from app.services.feed_management.models import (
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceResponse,
    FeedSourceType,
)
from app.services.integration_secrets_store import IntegrationSecretValue


_NOW = datetime(2026, 4, 7, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------


class ValidateBaseUrlTests(unittest.TestCase):
    def test_https_url_normalises_and_strips_trailing_slash(self) -> None:
        self.assertEqual(
            magento_config.validate_magento_base_url("https://store.example.com/"),
            "https://store.example.com",
        )

    def test_https_url_preserves_subpath(self) -> None:
        self.assertEqual(
            magento_config.validate_magento_base_url("https://example.com/shop/"),
            "https://example.com/shop",
        )

    def test_http_localhost_dev_store_accepted(self) -> None:
        self.assertEqual(
            magento_config.validate_magento_base_url("http://localhost:8080"),
            "http://localhost:8080",
        )

    def test_http_test_tld_dev_store_accepted(self) -> None:
        self.assertEqual(
            magento_config.validate_magento_base_url("http://magento.test"),
            "http://magento.test",
        )

    def test_http_production_domain_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_base_url("http://store.example.com")

    def test_missing_scheme_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_base_url("store.example.com")

    def test_empty_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_base_url("   ")

    def test_ftp_scheme_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_base_url("ftp://store.example.com")

    def test_missing_host_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_base_url("https://")


class ValidateStoreCodeTests(unittest.TestCase):
    def test_none_defaults_to_default(self) -> None:
        self.assertEqual(magento_config.validate_magento_store_code(None), "default")

    def test_empty_defaults_to_default(self) -> None:
        self.assertEqual(magento_config.validate_magento_store_code("  "), "default")

    def test_valid_alnum_underscore(self) -> None:
        self.assertEqual(magento_config.validate_magento_store_code("en_store_1"), "en_store_1")

    def test_valid_hyphen(self) -> None:
        self.assertEqual(magento_config.validate_magento_store_code("us-store"), "us-store")

    def test_leading_hyphen_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_store_code("-bad")

    def test_space_rejected(self) -> None:
        with self.assertRaises(ValueError):
            magento_config.validate_magento_store_code("bad store")


class ApiBaseUrlTests(unittest.TestCase):
    def test_returns_versioned_rest_endpoint(self) -> None:
        self.assertEqual(
            magento_config.get_magento_api_base_url("https://store.example.com/"),
            "https://store.example.com/rest/default/V1",
        )

    def test_honours_custom_store_code(self) -> None:
        self.assertEqual(
            magento_config.get_magento_api_base_url("https://store.example.com", store_code="en"),
            "https://store.example.com/rest/en/V1",
        )


# ---------------------------------------------------------------------------
# schemas.py
# ---------------------------------------------------------------------------


class MaskSecretTests(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(magento_schemas.mask_secret(""), "")
        self.assertEqual(magento_schemas.mask_secret(None), "")

    def test_short_value_fully_masked(self) -> None:
        self.assertEqual(magento_schemas.mask_secret("abc"), "***")
        self.assertEqual(magento_schemas.mask_secret("12345678"), "********")

    def test_long_value_keeps_last_four(self) -> None:
        self.assertEqual(magento_schemas.mask_secret("consumer_key_abcd1234"), "****1234")


class MagentoSourceCreateTests(unittest.TestCase):
    def _valid_payload(self, **overrides):
        base = dict(
            source_name="Main Magento Store",
            magento_base_url="https://magento.example.com/",
            consumer_key="ck_abcdef1234567890",
            consumer_secret="cs_abcdef1234567890",
            access_token="at_abcdef1234567890",
            access_token_secret="ats_abcdef1234567890",
            magento_store_code="default",
            catalog_type="product",
            catalog_variant="physical_products",
        )
        base.update(overrides)
        return base

    def test_happy_path(self) -> None:
        model = magento_schemas.MagentoSourceCreate(**self._valid_payload())
        self.assertEqual(model.source_name, "Main Magento Store")
        self.assertEqual(model.normalised_base_url(), "https://magento.example.com")
        self.assertEqual(model.magento_store_code, "default")
        # SecretStr protects secrets from accidental repr leaks
        self.assertNotIn("abcdef", repr(model.consumer_secret))
        self.assertNotIn("abcdef", repr(model.access_token_secret))

    def test_rejects_invalid_base_url(self) -> None:
        with self.assertRaises(ValidationError):
            magento_schemas.MagentoSourceCreate(**self._valid_payload(magento_base_url="not-a-url"))

    def test_rejects_http_production_base_url(self) -> None:
        with self.assertRaises(ValidationError):
            magento_schemas.MagentoSourceCreate(
                **self._valid_payload(magento_base_url="http://magento.example.com")
            )

    def test_accepts_http_localhost(self) -> None:
        model = magento_schemas.MagentoSourceCreate(
            **self._valid_payload(magento_base_url="http://localhost:8080")
        )
        self.assertEqual(str(model.magento_base_url).rstrip("/"), "http://localhost:8080")

    def test_store_code_defaults_when_missing(self) -> None:
        payload = self._valid_payload()
        payload.pop("magento_store_code")
        model = magento_schemas.MagentoSourceCreate(**payload)
        self.assertEqual(model.magento_store_code, "default")

    def test_store_code_custom(self) -> None:
        model = magento_schemas.MagentoSourceCreate(**self._valid_payload(magento_store_code="en_store"))
        self.assertEqual(model.magento_store_code, "en_store")

    def test_rejects_invalid_store_code(self) -> None:
        with self.assertRaises(ValidationError):
            magento_schemas.MagentoSourceCreate(**self._valid_payload(magento_store_code="bad store"))

    def test_rejects_empty_source_name(self) -> None:
        with self.assertRaises(ValidationError):
            magento_schemas.MagentoSourceCreate(**self._valid_payload(source_name=""))

    def test_rejects_empty_consumer_key(self) -> None:
        with self.assertRaises(ValidationError):
            magento_schemas.MagentoSourceCreate(**self._valid_payload(consumer_key=""))

    def test_dump_credentials_returns_plaintext_dict(self) -> None:
        model = magento_schemas.MagentoSourceCreate(**self._valid_payload())
        creds = model.dump_credentials()
        self.assertEqual(
            set(creds.keys()),
            {"consumer_key", "consumer_secret", "access_token", "access_token_secret"},
        )
        self.assertEqual(creds["consumer_secret"], "cs_abcdef1234567890")
        self.assertEqual(creds["access_token_secret"], "ats_abcdef1234567890")


class MagentoSourceResponseTests(unittest.TestCase):
    def test_masks_all_four_secrets(self) -> None:
        resp = magento_schemas.MagentoSourceResponse.from_source_and_credentials(
            source_id="src-1",
            subaccount_id=42,
            source_name="Main Magento Store",
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
            catalog_type="product",
            catalog_variant="physical_products",
            connection_status="connected",
            credentials={
                "consumer_key": "ck_1234567890abcd",
                "consumer_secret": "cs_1234567890abcd",
                "access_token": "at_1234567890abcd",
                "access_token_secret": "ats_1234567890abcd",
            },
        )
        self.assertTrue(resp.has_credentials)
        self.assertEqual(resp.consumer_key_masked, "****abcd")
        self.assertEqual(resp.consumer_secret_masked, "****abcd")
        self.assertEqual(resp.access_token_masked, "****abcd")
        self.assertEqual(resp.access_token_secret_masked, "****abcd")

    def test_no_credentials_flags_has_credentials_false(self) -> None:
        resp = magento_schemas.MagentoSourceResponse.from_source_and_credentials(
            source_id="src-2",
            subaccount_id=42,
            source_name="Pending",
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
            catalog_type="product",
            catalog_variant="physical_products",
            connection_status="pending",
            credentials=None,
        )
        self.assertFalse(resp.has_credentials)
        self.assertEqual(resp.consumer_key_masked, "")
        self.assertEqual(resp.access_token_secret_masked, "")

    def test_response_dict_never_contains_raw_secrets(self) -> None:
        resp = magento_schemas.MagentoSourceResponse.from_source_and_credentials(
            source_id="src-3",
            subaccount_id=42,
            source_name="Main",
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
            catalog_type="product",
            catalog_variant="physical_products",
            connection_status="connected",
            credentials={
                "consumer_key": "ck_RAW_VALUE_1234567890",
                "consumer_secret": "cs_RAW_VALUE_1234567890",
                "access_token": "at_RAW_VALUE_1234567890",
                "access_token_secret": "ats_RAW_VALUE_1234567890",
            },
        )
        dumped = resp.model_dump()
        for raw in (
            "ck_RAW_VALUE_1234567890",
            "cs_RAW_VALUE_1234567890",
            "at_RAW_VALUE_1234567890",
            "ats_RAW_VALUE_1234567890",
        ):
            for value in dumped.values():
                self.assertNotEqual(value, raw)


# ---------------------------------------------------------------------------
# service.py
# ---------------------------------------------------------------------------


class _FakeSecretsStore:
    """In-memory stand-in for ``integration_secrets_store`` with the same API."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str], str] = {}

    def upsert_secret(self, *, provider: str, secret_key: str, value: str, scope: str) -> None:
        self._data[(provider, secret_key, scope)] = value

    def get_secret(self, *, provider: str, secret_key: str, scope: str):
        value = self._data.get((provider, secret_key, scope))
        if value is None:
            return None
        return IntegrationSecretValue(
            provider=provider,
            secret_key=secret_key,
            scope=scope,
            value=value,
            updated_at=_NOW,
        )

    def delete_secret(self, *, provider: str, secret_key: str, scope: str) -> None:
        self._data.pop((provider, secret_key, scope), None)


class StoreMagentoCredentialsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = _FakeSecretsStore()
        self._patch = patch.object(magento_service, "integration_secrets_store", self.fake)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()

    def test_store_and_get_round_trip(self) -> None:
        magento_service.store_magento_credentials(
            source_id="src-42",
            consumer_key="ck_ONE",
            consumer_secret="cs_TWO",
            access_token="at_THREE",
            access_token_secret="ats_FOUR",
        )
        creds = magento_service.get_magento_credentials("src-42")
        self.assertEqual(
            creds,
            {
                "consumer_key": "ck_ONE",
                "consumer_secret": "cs_TWO",
                "access_token": "at_THREE",
                "access_token_secret": "ats_FOUR",
            },
        )

    def test_get_returns_none_when_any_key_missing(self) -> None:
        self.fake.upsert_secret(provider="magento", secret_key="consumer_key", value="ck", scope="src-1")
        self.fake.upsert_secret(provider="magento", secret_key="consumer_secret", value="cs", scope="src-1")
        # access_token and access_token_secret are absent → None
        self.assertIsNone(magento_service.get_magento_credentials("src-1"))

    def test_store_rejects_empty_credentials(self) -> None:
        with self.assertRaises(ValueError):
            magento_service.store_magento_credentials(
                source_id="src-1",
                consumer_key="ck",
                consumer_secret="cs",
                access_token="at",
                access_token_secret="",
            )

    def test_store_rejects_empty_source_id(self) -> None:
        with self.assertRaises(ValueError):
            magento_service.store_magento_credentials(
                source_id="",
                consumer_key="ck",
                consumer_secret="cs",
                access_token="at",
                access_token_secret="ats",
            )

    def test_delete_removes_all_four_keys(self) -> None:
        magento_service.store_magento_credentials(
            source_id="src-7",
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )
        self.assertIsNotNone(magento_service.get_magento_credentials("src-7"))
        magento_service.delete_magento_credentials("src-7")
        self.assertIsNone(magento_service.get_magento_credentials("src-7"))

    def test_delete_is_idempotent(self) -> None:
        magento_service.delete_magento_credentials("src-missing")  # does not raise

    def test_two_sources_same_subaccount_dont_collide(self) -> None:
        magento_service.store_magento_credentials(
            source_id="src-A",
            consumer_key="ckA",
            consumer_secret="csA",
            access_token="atA",
            access_token_secret="atsA",
        )
        magento_service.store_magento_credentials(
            source_id="src-B",
            consumer_key="ckB",
            consumer_secret="csB",
            access_token="atB",
            access_token_secret="atsB",
        )
        self.assertEqual(magento_service.get_magento_credentials("src-A")["consumer_key"], "ckA")
        self.assertEqual(magento_service.get_magento_credentials("src-B")["consumer_key"], "ckB")


class MaskMagentoCredentialsTests(unittest.TestCase):
    def test_masks_all_four_keys(self) -> None:
        masked = magento_service.mask_magento_credentials(
            {
                "consumer_key": "ck_abcdef1234",
                "consumer_secret": "cs_abcdef1234",
                "access_token": "at_abcdef1234",
                "access_token_secret": "ats_abcdef1234",
            }
        )
        self.assertEqual(masked["consumer_key"], "****1234")
        self.assertEqual(masked["consumer_secret"], "****1234")
        self.assertEqual(masked["access_token"], "****1234")
        self.assertEqual(masked["access_token_secret"], "****1234")

    def test_none_yields_empty_strings(self) -> None:
        masked = magento_service.mask_magento_credentials(None)
        self.assertEqual(
            masked,
            {"consumer_key": "", "consumer_secret": "", "access_token": "", "access_token_secret": ""},
        )


# ---------------------------------------------------------------------------
# Backwards-compat with the generic FeedSource models
# ---------------------------------------------------------------------------


class FeedSourceModelCompatTests(unittest.TestCase):
    def test_feed_source_create_defaults_magento_fields_to_none(self) -> None:
        payload = FeedSourceCreate(
            subaccount_id=1,
            source_type=FeedSourceType.csv,
            name="A CSV feed",
            config=FeedSourceConfig(file_url="https://example.com/p.csv"),
        )
        self.assertIsNone(payload.magento_base_url)
        self.assertIsNone(payload.magento_store_code)

    def test_feed_source_create_accepts_magento_fields(self) -> None:
        payload = FeedSourceCreate(
            subaccount_id=1,
            source_type=FeedSourceType.magento,
            name="Magento 1",
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
        )
        self.assertEqual(payload.magento_base_url, "https://magento.example.com")
        self.assertEqual(payload.magento_store_code, "default")

    def test_feed_source_response_accepts_magento_fields(self) -> None:
        resp = FeedSourceResponse(
            id="src-1",
            subaccount_id=1,
            source_type=FeedSourceType.magento,
            name="Magento",
            config={},
            credentials_secret_id=None,
            is_active=True,
            catalog_type="product",
            catalog_variant="physical_products",
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
            connection_status="pending",
            created_at=_NOW,
            updated_at=_NOW,
        )
        self.assertEqual(resp.magento_base_url, "https://magento.example.com")
        self.assertEqual(resp.magento_store_code, "default")

    def test_feed_source_config_carries_magento_fields_in_extra(self) -> None:
        cfg = FeedSourceConfig(
            magento_base_url="https://magento.example.com",
            magento_store_code="en",
        )
        dumped = cfg.model_dump()
        self.assertEqual(dumped["magento_base_url"], "https://magento.example.com")
        self.assertEqual(dumped["magento_store_code"], "en")


if __name__ == "__main__":
    unittest.main()
