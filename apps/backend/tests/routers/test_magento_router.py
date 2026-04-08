"""Tests for the Magento FastAPI router (``app.api.integrations.magento``).

The router is exercised by calling the endpoint functions directly — no
``TestClient``/HTTP layer — mirroring the pattern in
``tests/routers/test_feed_sources_shopify.py``. ``FeedSourceRepository``
and ``magento_service`` are monkey-patched in-process so these tests run
hermetically (no database, no network).
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from app.api.integrations import magento as magento_api
from app.integrations.magento.exceptions import (
    MagentoAuthError,
    MagentoConnectionError,
)
from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import FeedSourceResponse, FeedSourceType


_NOW = datetime(2026, 4, 7, tzinfo=timezone.utc)
_ADMIN = AuthUser(email="admin@example.com", role="agency_admin")


def _magento_source(**overrides: Any) -> FeedSourceResponse:
    base = dict(
        id="src-magento-1",
        subaccount_id=42,
        source_type=FeedSourceType.magento,
        name="Main Magento",
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
    base.update(overrides)
    return FeedSourceResponse(**base)


def _valid_create_payload(**overrides: Any):
    base = dict(
        source_name="Main Magento",
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
    from app.integrations.magento.schemas import MagentoSourceCreate

    return MagentoSourceCreate(**base)


def _enable_ff():
    return patch.object(magento_api, "_enforce_feature_flag", lambda: None)


def _skip_auth():
    return patch.object(magento_api, "enforce_subaccount_action", lambda **kw: None)


def _skip_agency_auth():
    return patch.object(magento_api, "enforce_action_scope", lambda **kw: None)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# POST /sources
# ---------------------------------------------------------------------------


class CreateMagentoSourceTests(unittest.TestCase):
    def test_create_happy_path_masks_credentials_in_response(self) -> None:
        created = _magento_source(connection_status="pending")

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "create", return_value=created
        ), patch.object(
            magento_api.magento_service, "store_magento_credentials"
        ) as mock_store:
            result = magento_api.create_magento_source(
                payload=_valid_create_payload(),
                subaccount_id=42,
                user=_ADMIN,
            )

        mock_store.assert_called_once()
        self.assertEqual(result.id, "src-magento-1")
        self.assertEqual(result.subaccount_id, 42)
        self.assertEqual(result.magento_base_url, "https://magento.example.com")
        self.assertEqual(result.magento_store_code, "default")
        self.assertTrue(result.has_credentials)
        # Masking happens at response construction — the raw values must
        # NEVER appear in the response.
        self.assertEqual(result.consumer_key_masked, "****7890")
        self.assertEqual(result.consumer_secret_masked, "****7890")
        self.assertEqual(result.access_token_masked, "****7890")
        self.assertEqual(result.access_token_secret_masked, "****7890")

    def test_create_with_duplicate_raises_409(self) -> None:
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo,
            "create",
            side_effect=FeedSourceAlreadyExistsError(
                "https://magento.example.com[default]", 42
            ),
        ):
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.create_magento_source(
                    payload=_valid_create_payload(),
                    subaccount_id=42,
                    user=_ADMIN,
                )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_create_rolls_back_source_when_credential_store_fails(self) -> None:
        created = _magento_source()

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "create", return_value=created
        ), patch.object(
            magento_api._source_repo, "delete"
        ) as mock_delete, patch.object(
            magento_api.magento_service,
            "store_magento_credentials",
            side_effect=RuntimeError("encrypt failed"),
        ):
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.create_magento_source(
                    payload=_valid_create_payload(),
                    subaccount_id=42,
                    user=_ADMIN,
                )
        self.assertEqual(ctx.exception.status_code, 500)
        mock_delete.assert_called_once_with("src-magento-1")


# ---------------------------------------------------------------------------
# GET /sources + GET /sources/{id}
# ---------------------------------------------------------------------------


class ListAndGetTests(unittest.TestCase):
    def test_list_filters_to_magento_sources_only(self) -> None:
        magento = _magento_source()
        shopify = FeedSourceResponse(
            id="src-shop-1",
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="Shopify Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            catalog_type="product",
            catalog_variant="physical_products",
            connection_status="connected",
            created_at=_NOW,
            updated_at=_NOW,
        )

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo,
            "get_by_subaccount",
            return_value=[magento, shopify],
        ):
            result = magento_api.list_magento_sources(subaccount_id=42, user=_ADMIN)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "src-magento-1")

    def test_get_returns_source(self) -> None:
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ):
            result = magento_api.get_magento_source(
                source_id="src-magento-1", subaccount_id=42, user=_ADMIN
            )
        self.assertEqual(result.id, "src-magento-1")
        self.assertFalse(result.has_credentials)  # no creds fetched on read

    def test_get_not_found_returns_404(self) -> None:
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo,
            "get_by_id",
            side_effect=FeedSourceNotFoundError("missing"),
        ):
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.get_magento_source(
                    source_id="missing", subaccount_id=42, user=_ADMIN
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_wrong_subaccount_returns_404_not_403(self) -> None:
        """Cross-tenant lookups must surface as 404 so we never leak the
        existence of another subaccount's source."""
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo,
            "get_by_id",
            return_value=_magento_source(subaccount_id=99),
        ):
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.get_magento_source(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_non_magento_source_returns_404(self) -> None:
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo,
            "get_by_id",
            return_value=_magento_source(source_type=FeedSourceType.shopify),
        ):
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.get_magento_source(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
        self.assertEqual(ctx.exception.status_code, 404)


# ---------------------------------------------------------------------------
# PUT /sources/{id}
# ---------------------------------------------------------------------------


class UpdateTests(unittest.TestCase):
    def test_partial_update_only_touches_name(self) -> None:
        src = _magento_source()
        updated = _magento_source(name="Renamed Store")

        captured: dict[str, Any] = {}

        def _fake_update(source_id, payload):
            captured["payload"] = payload
            return updated

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=src
        ), patch.object(
            magento_api._source_repo, "update", side_effect=_fake_update
        ), patch.object(
            magento_api.magento_service, "store_magento_credentials"
        ) as mock_store:
            result = magento_api.update_magento_source(
                source_id="src-magento-1",
                payload=magento_api.MagentoSourceUpdateRequest(source_name="Renamed Store"),
                subaccount_id=42,
                user=_ADMIN,
            )

        mock_store.assert_not_called()
        self.assertEqual(result.source_name, "Renamed Store")
        # Ensure nothing else was mutated
        payload = captured["payload"]
        self.assertEqual(payload.name, "Renamed Store")
        self.assertIsNone(payload.catalog_type)
        self.assertIsNone(payload.magento_base_url)
        self.assertIsNone(payload.magento_store_code)

    def test_credential_rotation_merges_with_existing_and_re_encrypts(self) -> None:
        src = _magento_source()
        existing = {
            "consumer_key": "ck_old",
            "consumer_secret": "cs_old",
            "access_token": "at_old",
            "access_token_secret": "ats_old",
        }

        captured: dict[str, Any] = {}

        def _fake_store(**kwargs):
            captured.update(kwargs)

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=src
        ), patch.object(
            magento_api.magento_service, "get_magento_credentials", return_value=existing
        ), patch.object(
            magento_api.magento_service,
            "store_magento_credentials",
            side_effect=_fake_store,
        ):
            payload = magento_api.MagentoSourceUpdateRequest(
                consumer_key="ck_new",
                access_token="at_new",
            )
            magento_api.update_magento_source(
                source_id="src-magento-1",
                payload=payload,
                subaccount_id=42,
                user=_ADMIN,
            )

        # New values rotated in, untouched values preserved
        self.assertEqual(captured["consumer_key"], "ck_new")
        self.assertEqual(captured["access_token"], "at_new")
        self.assertEqual(captured["consumer_secret"], "cs_old")
        self.assertEqual(captured["access_token_secret"], "ats_old")

    def test_invalid_base_url_returns_400(self) -> None:
        src = _magento_source()
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=src
        ):
            # HttpUrl at the Pydantic level still accepts http; the stricter
            # production rule is enforced inside the handler.
            with self.assertRaises(magento_api.HTTPException) as ctx:
                magento_api.update_magento_source(
                    source_id="src-magento-1",
                    payload=magento_api.MagentoSourceUpdateRequest(
                        magento_base_url="http://magento.example.com",
                    ),
                    subaccount_id=42,
                    user=_ADMIN,
                )
        self.assertEqual(ctx.exception.status_code, 400)


# ---------------------------------------------------------------------------
# DELETE /sources/{id}
# ---------------------------------------------------------------------------


class DeleteTests(unittest.TestCase):
    def test_delete_removes_credentials_before_source(self) -> None:
        call_order: list[str] = []

        def _record_delete_creds(source_id):
            call_order.append("credentials")

        def _record_delete_src(source_id):
            call_order.append("source")

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ), patch.object(
            magento_api._source_repo, "delete", side_effect=_record_delete_src
        ), patch.object(
            magento_api.magento_service,
            "delete_magento_credentials",
            side_effect=_record_delete_creds,
        ):
            result = magento_api.delete_magento_source(
                source_id="src-magento-1", subaccount_id=42, user=_ADMIN
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(call_order, ["credentials", "source"])


# ---------------------------------------------------------------------------
# POST /sources/{id}/test-connection
# ---------------------------------------------------------------------------


class TestConnectionForStoredSourceTests(unittest.TestCase):
    def test_success_returns_store_metadata(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            return_value=[
                {
                    "code": "default",
                    "name": "Main Website Store",
                    "base_currency_code": "USD",
                }
            ]
        )

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ), patch.object(
            magento_api.magento_client_module,
            "create_magento_client_from_source",
            return_value=fake_client,
        ), patch.object(
            magento_api._source_repo, "record_connection_check"
        ) as mock_record:
            result = _run(
                magento_api.test_magento_source_connection(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.store_name, "Main Website Store")
        self.assertEqual(result.base_currency, "USD")
        mock_record.assert_called_once()
        _, kwargs = mock_record.call_args
        self.assertTrue(kwargs.get("success"))

    def test_401_returns_invalid_credentials_error(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=MagentoAuthError(
                "Unauthorized", status_code=401, body="bad token"
            )
        )

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ), patch.object(
            magento_api.magento_client_module,
            "create_magento_client_from_source",
            return_value=fake_client,
        ), patch.object(
            magento_api._source_repo, "record_connection_check"
        ):
            result = _run(
                magento_api.test_magento_source_connection(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
            )

        self.assertFalse(result.success)
        self.assertIn("Invalid credentials", result.error or "")

    def test_connection_error_returns_connection_failed_error(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=MagentoConnectionError("DNS failure")
        )

        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ), patch.object(
            magento_api.magento_client_module,
            "create_magento_client_from_source",
            return_value=fake_client,
        ), patch.object(
            magento_api._source_repo, "record_connection_check"
        ):
            result = _run(
                magento_api.test_magento_source_connection(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
            )

        self.assertFalse(result.success)
        self.assertIn("Connection failed", result.error or "")

    def test_missing_credentials_returns_reconnect_error(self) -> None:
        with _enable_ff(), _skip_auth(), patch.object(
            magento_api._source_repo, "get_by_id", return_value=_magento_source()
        ), patch.object(
            magento_api.magento_client_module,
            "create_magento_client_from_source",
            side_effect=MagentoAuthError("No credentials stored"),
        ), patch.object(
            magento_api._source_repo, "record_connection_check"
        ):
            result = _run(
                magento_api.test_magento_source_connection(
                    source_id="src-magento-1", subaccount_id=42, user=_ADMIN
                )
            )

        self.assertFalse(result.success)
        self.assertIn("No credentials stored", result.error or "")


# ---------------------------------------------------------------------------
# POST /test-connection (pre-save)
# ---------------------------------------------------------------------------


class TestConnectionBeforeSaveTests(unittest.TestCase):
    def _valid_payload(self, **overrides: Any):
        base = dict(
            magento_base_url="https://magento.example.com",
            magento_store_code="default",
            consumer_key="ck_abcdef",
            consumer_secret="cs_abcdef",
            access_token="at_abcdef",
            access_token_secret="ats_abcdef",
        )
        base.update(overrides)
        return magento_api.MagentoTestConnectionRequest(**base)

    def test_success_returns_store_metadata(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            return_value=[
                {
                    "code": "default",
                    "name": "Test Store",
                    "base_currency_code": "EUR",
                }
            ]
        )

        with _enable_ff(), _skip_agency_auth(), patch.object(
            magento_api, "MagentoClient", return_value=fake_client
        ):
            result = _run(
                magento_api.test_magento_connection_before_save(
                    payload=self._valid_payload(), user=_ADMIN
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.store_name, "Test Store")
        self.assertEqual(result.base_currency, "EUR")

    def test_bad_credentials_propagate_auth_error(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=MagentoAuthError("Unauthorized", status_code=401)
        )

        with _enable_ff(), _skip_agency_auth(), patch.object(
            magento_api, "MagentoClient", return_value=fake_client
        ):
            result = _run(
                magento_api.test_magento_connection_before_save(
                    payload=self._valid_payload(), user=_ADMIN
                )
            )

        self.assertFalse(result.success)
        self.assertIn("Invalid credentials", result.error or "")

    def test_unreachable_returns_connection_error(self) -> None:
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=MagentoConnectionError("Cannot reach Magento")
        )

        with _enable_ff(), _skip_agency_auth(), patch.object(
            magento_api, "MagentoClient", return_value=fake_client
        ):
            result = _run(
                magento_api.test_magento_connection_before_save(
                    payload=self._valid_payload(), user=_ADMIN
                )
            )

        self.assertFalse(result.success)
        self.assertIn("Connection failed", result.error or "")


if __name__ == "__main__":
    unittest.main()
