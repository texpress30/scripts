from __future__ import annotations

import logging
from typing import Any

from app.services.feed_management.connectors.base import BaseConnector, ProductData
from app.services.feed_management.exceptions import FeedSourceNotFoundError
from app.services.feed_management.models import (
    FeedImportCreate,
    FeedImportResponse,
    FeedImportStatus,
    FeedSourceResponse,
    FeedSourceType,
)
from app.services.feed_management.products_repository import feed_products_repository
from app.services.feed_management.repository import FeedImportRepository, FeedSourceRepository

logger = logging.getLogger(__name__)

SYNC_BATCH_SIZE = 100


def _get_connector(source: FeedSourceResponse) -> BaseConnector:
    """Factory: return the appropriate connector for the given source type."""
    config = source.config or {}

    if source.source_type in (FeedSourceType.csv, FeedSourceType.json, FeedSourceType.xml):
        from app.services.feed_management.connectors.file_connector import FileConnector

        config.setdefault("file_type", source.source_type.value)
        return FileConnector(config=config)

    if source.source_type == FeedSourceType.shopify:
        from app.services.feed_management.connectors.shopify_connector import ShopifyConnector

        credentials: dict[str, str] = {}
        if source.credentials_secret_id:
            try:
                from app.services.integration_secrets_store import integration_secrets_store

                for key in ("api_key", "api_secret_key", "access_token"):
                    secret = integration_secrets_store.get_secret(
                        provider="shopify",
                        secret_key=key,
                        scope=source.credentials_secret_id,
                    )
                    if secret:
                        credentials[key] = secret.value
            except Exception:
                logger.exception("Failed to load Shopify credentials for source %s", source.id)
        # Fallback: read credentials from config (stored by frontend form)
        if not credentials.get("access_token") and not credentials.get("api_key"):
            for key in ("api_key", "api_secret_key", "access_token"):
                val = config.get(key)
                if val and isinstance(val, str):
                    credentials[key] = val
        return ShopifyConnector(config=config, credentials=credentials)

    if source.source_type == FeedSourceType.woocommerce:
        from app.services.feed_management.connectors.woocommerce_connector import WooCommerceConnector

        logger.info("Loading WooCommerce connector for source %s, config keys: %s", source.id, list(config.keys()))
        woo_credentials: dict[str, str] = {}
        if source.credentials_secret_id:
            try:
                from app.services.integration_secrets_store import integration_secrets_store

                for key in ("consumer_key", "consumer_secret"):
                    secret = integration_secrets_store.get_secret(
                        provider="woocommerce",
                        secret_key=key,
                        scope=source.credentials_secret_id,
                    )
                    if secret:
                        woo_credentials[key] = secret.value
            except Exception:
                logger.exception("Failed to load WooCommerce credentials for source %s", source.id)
        # Fallback: read credentials from config (stored by frontend form)
        if not woo_credentials.get("consumer_key"):
            for config_key, cred_key in [("consumer_key", "consumer_key"), ("api_key", "consumer_key"),
                                          ("consumer_secret", "consumer_secret"), ("api_secret", "consumer_secret")]:
                val = config.get(config_key)
                if val and isinstance(val, str) and not woo_credentials.get(cred_key):
                    woo_credentials[cred_key] = val
        has_key = bool(woo_credentials.get("consumer_key"))
        has_secret = bool(woo_credentials.get("consumer_secret"))
        logger.info("WooCommerce credentials resolved for source %s: key=%s secret=%s", source.id, has_key, has_secret)
        if not has_key or not has_secret:
            logger.warning("WooCommerce source %s has no credentials — sync will likely fail with 401. "
                           "Delete and re-create the source to fix.", source.id)
        return WooCommerceConnector(config=config, credentials=woo_credentials)

    raise ValueError(f"No connector available for source type: {source.source_type}")


class FeedSyncService:
    def __init__(self) -> None:
        self._source_repo = FeedSourceRepository()
        self._import_repo = FeedImportRepository()

    async def run_sync(self, feed_source_id: str) -> FeedImportResponse:
        """Run a full sync for the given feed source.

        1. Look up the source and resolve its connector
        2. Find or create a pending FeedImport record
        3. Iterate products in batches, updating progress
        4. Mark import as completed (or failed)
        """
        source = self._source_repo.get_by_id(feed_source_id)
        connector = _get_connector(source)

        # Find existing pending import or create one
        latest = self._import_repo.get_latest_by_source(feed_source_id)
        if latest and latest.status == FeedImportStatus.pending:
            feed_import = latest
        else:
            feed_import = self._import_repo.create(FeedImportCreate(feed_source_id=feed_source_id))

        # Mark as in progress
        feed_import = self._import_repo.update_status(feed_import.id, status=FeedImportStatus.in_progress)

        imported_count = 0
        total_count = 0
        errors: list[dict[str, Any]] = []
        batch: list[ProductData] = []

        try:
            async for product in connector.fetch_products():
                total_count += 1
                batch.append(product)

                if len(batch) >= SYNC_BATCH_SIZE:
                    try:
                        saved = feed_products_repository.upsert_products_batch(feed_source_id, batch)
                        imported_count += saved
                    except Exception as exc:
                        logger.warning("Batch upsert failed for source %s: %s", feed_source_id, exc)
                        errors.append({"batch_size": len(batch), "error": str(exc)})
                    batch = []

                    feed_import = self._import_repo.update_status(
                        feed_import.id,
                        status=FeedImportStatus.in_progress,
                        total_products=total_count,
                        imported_products=imported_count,
                        errors=errors,
                    )

            # Flush remaining products
            if batch:
                try:
                    saved = feed_products_repository.upsert_products_batch(feed_source_id, batch)
                    imported_count += saved
                except Exception as exc:
                    logger.warning("Final batch upsert failed for source %s: %s", feed_source_id, exc)
                    errors.append({"batch_size": len(batch), "error": str(exc)})

            feed_import = self._import_repo.update_status(
                feed_import.id,
                status=FeedImportStatus.completed,
                total_products=total_count,
                imported_products=imported_count,
                errors=errors,
            )
        except Exception as exc:
            logger.exception("Sync failed for feed source %s", feed_source_id)
            errors.append({"error": str(exc)})
            feed_import = self._import_repo.update_status(
                feed_import.id,
                status=FeedImportStatus.failed,
                total_products=total_count,
                imported_products=imported_count,
                errors=errors,
            )

        return feed_import

    async def run_sync_background(self, feed_source_id: str) -> None:
        """Wrapper for background task execution."""
        try:
            result = await self.run_sync(feed_source_id)
            logger.info(
                "Background sync completed for source %s: status=%s imported=%d/%d",
                feed_source_id,
                result.status,
                result.imported_products,
                result.total_products,
            )
        except Exception:
            logger.exception("Background sync crashed for feed source %s", feed_source_id)


feed_sync_service = FeedSyncService()
