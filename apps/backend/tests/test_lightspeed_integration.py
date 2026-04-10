"""Tests for the dedicated Lightspeed eCom integration.

Covers:

* ``app.integrations.lightspeed.config`` — region / shop-id validation,
  region constants.
* ``app.integrations.lightspeed.router`` — full CRUD cycle exercised
  through direct endpoint calls with monkey-patched repo + service.
  No credential storage assertions — Lightspeed stores only non-sensitive
  config metadata (shop_id, shop_language, shop_region) in the JSONB
  config column.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.integrations.lightspeed.config import (
    LIGHTSPEED_REGIONS,
    validate_shop_id,
    validate_shop_region,
)
from app.integrations.lightspeed import router as ls_router
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)


_NOW = datetime(2026, 4, 10, tzinfo=timezone.utc)
_SOURCE_ID = "ls-src-001"
_SUBACCOUNT_ID = 42


def _set_env() -> None:
    os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")
    os.environ.setdefault("FF_FEED_MANAGEMENT_ENABLED", "1")


def _make_source(
    *,
    config: dict | None = None,
) -> FeedSourceResponse:
    return FeedSourceResponse(
        id=_SOURCE_ID,
        subaccount_id=_SUBACCOUNT_ID,
        source_type=FeedSourceType.lightspeed,
        name="Test Lightspeed Store",
        config=config or {
            "store_url": "https://store.example.com",
            "extra": {
                "shop_id": "12345",
                "shop_language": "en",
                "shop_region": "eu1",
            },
        },
        credentials_secret_id=None,
        is_active=True,
        connection_status="pending",
        last_connection_check=None,
        last_error=None,
        has_token=False,
        token_scopes=None,
        last_import_at=None,
        last_sync_at=None,
        product_count=0,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_user():
    from app.services.auth import AuthUser
    return AuthUser(
        email="admin@example.com",
        role="agency_admin",
        user_id=1,
        is_env_admin=True,
    )


# ---------------------------------------------------------------------------
# config.py — validation
# ---------------------------------------------------------------------------


class LightspeedConfigTests(unittest.TestCase):

    def test_regions_tuple(self) -> None:
        self.assertEqual(LIGHTSPEED_REGIONS, ("eu1", "us1"))

    def test_validate_shop_id_strips_whitespace(self) -> None:
        self.assertEqual(validate_shop_id("  12345  "), "12345")

    def test_validate_shop_id_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_shop_id("")
        with self.assertRaises(ValueError):
            validate_shop_id("   ")

    def test_validate_shop_region_accepts_valid(self) -> None:
        self.assertEqual(validate_shop_region("eu1"), "eu1")
        self.assertEqual(validate_shop_region("us1"), "us1")
        self.assertEqual(validate_shop_region("EU1"), "eu1")

    def test_validate_shop_region_rejects_invalid(self) -> None:
        with self.assertRaises(ValueError):
            validate_shop_region("ap1")
        with self.assertRaises(ValueError):
            validate_shop_region("")


# ---------------------------------------------------------------------------
# router.py — CRUD cycle
# ---------------------------------------------------------------------------


class LightspeedRouterCrudTests(unittest.TestCase):

    def setUp(self) -> None:
        _set_env()

    def _find_endpoint(self, path_suffix: str, method: str, *, exact: bool = False):
        for r in ls_router.router.routes:
            full_path = getattr(r, "path", "")
            match = (full_path == path_suffix) if exact else full_path.endswith(path_suffix)
            if match and method in (
                getattr(r, "methods", set()) or set()
            ):
                return r.endpoint
        raise AssertionError(
            f"Endpoint not found: {path_suffix} {method}"
        )

    def test_create_source(self) -> None:
        source = _make_source()
        payload = ls_router.LightspeedSourceCreateRequest(
            source_name="My Lightspeed Store",
            store_url="https://store.example.com",
            shop_id="12345",
            shop_language="en",
            shop_region="eu1",
        )
        with patch.object(
            ls_router._source_repo, "create", return_value=source
        ):
            create_endpoint = self._find_endpoint("/sources", "POST")
            response = create_endpoint(
                payload=payload,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(response.platform, "lightspeed")
        self.assertEqual(response.source_name, "Test Lightspeed Store")
        self.assertEqual(response.store_url, "https://store.example.com")
        self.assertEqual(response.shop_id, "12345")
        self.assertEqual(response.shop_language, "en")
        self.assertEqual(response.shop_region, "eu1")

    def test_create_rejects_invalid_region(self) -> None:
        from fastapi import HTTPException

        payload = ls_router.LightspeedSourceCreateRequest(
            source_name="My Store",
            store_url="https://store.example.com",
            shop_id="12345",
            shop_language="en",
            shop_region="ap1",
        )
        create_endpoint = self._find_endpoint("/sources", "POST")
        with self.assertRaises(HTTPException) as ctx:
            create_endpoint(
                payload=payload,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid shop region", ctx.exception.detail)

    def test_create_rejects_empty_shop_id(self) -> None:
        from fastapi import HTTPException

        payload = ls_router.LightspeedSourceCreateRequest(
            source_name="My Store",
            store_url="https://store.example.com",
            shop_id="   ",
            shop_language="en",
            shop_region="eu1",
        )
        create_endpoint = self._find_endpoint("/sources", "POST")
        with self.assertRaises(HTTPException) as ctx:
            create_endpoint(
                payload=payload,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Shop ID is required", ctx.exception.detail)

    def test_list_sources_filters_by_type(self) -> None:
        ls_source = _make_source()
        shopify_source = FeedSourceResponse(
            id="other-src",
            subaccount_id=_SUBACCOUNT_ID,
            source_type=FeedSourceType.shopify,
            name="Shopify Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            connection_status="connected",
            created_at=_NOW,
            updated_at=_NOW,
        )
        with patch.object(
            ls_router._source_repo,
            "get_by_subaccount",
            return_value=[ls_source, shopify_source],
        ):
            list_endpoint = self._find_endpoint("/sources", "GET")
            result = list_endpoint(
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].platform, "lightspeed")

    def test_get_source(self) -> None:
        source = _make_source()
        with patch.object(
            ls_router._source_repo, "get_by_id", return_value=source
        ):
            get_endpoint = self._find_endpoint("/sources/{source_id}", "GET")
            response = get_endpoint(
                source_id=_SOURCE_ID,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(response.source_id, _SOURCE_ID)
        self.assertEqual(response.shop_id, "12345")

    def test_get_source_cross_tenant_returns_404(self) -> None:
        from fastapi import HTTPException

        source = _make_source()
        with patch.object(
            ls_router._source_repo, "get_by_id", return_value=source
        ):
            get_endpoint = self._find_endpoint("/sources/{source_id}", "GET")
            with self.assertRaises(HTTPException) as ctx:
                get_endpoint(
                    source_id=_SOURCE_ID,
                    subaccount_id=999,  # wrong subaccount
                    user=_make_user(),
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_source(self) -> None:
        source = _make_source()
        with patch.object(
            ls_router._source_repo, "get_by_id", return_value=source
        ), patch.object(
            ls_router._source_repo, "delete"
        ) as mock_delete:
            delete_endpoint = self._find_endpoint(
                "/sources/{source_id}", "DELETE"
            )
            result = delete_endpoint(
                source_id=_SOURCE_ID,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["id"], _SOURCE_ID)
        mock_delete.assert_called_once_with(_SOURCE_ID)

    def test_test_connection_pre_save(self) -> None:
        with patch(
            "app.integrations.lightspeed.router.probe_store_url",
            return_value={
                "success": True,
                "message": "Store URL is reachable.",
                "details": {"status_code": 200},
            },
        ):
            endpoint = self._find_endpoint("/integrations/lightspeed/test-connection", "POST", exact=True)
            response = endpoint(
                store_url="https://store.example.com",
                user=_make_user(),
            )

        self.assertTrue(response.success)

    def test_config_jsonb_round_trip(self) -> None:
        """Verify shop_id / language / region survive the config → response mapping."""
        source = _make_source(
            config={
                "store_url": "https://myshop.com",
                "extra": {
                    "shop_id": "99999",
                    "shop_language": "nl",
                    "shop_region": "us1",
                },
            },
        )
        response = ls_router._source_to_response(source)
        self.assertEqual(response.shop_id, "99999")
        self.assertEqual(response.shop_language, "nl")
        self.assertEqual(response.shop_region, "us1")
        self.assertEqual(response.store_url, "https://myshop.com")


if __name__ == "__main__":
    unittest.main()
