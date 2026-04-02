from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.services.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/woocommerce", tags=["integrations-woocommerce"])


class WooCommerceTestConnectionRequest(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str


@router.post("/test-connection")
async def test_connection(payload: WooCommerceTestConnectionRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    from app.services.feed_management.connectors.woocommerce_connector import WooCommerceConnector

    logger.info(
        "WooCommerce test-connection request: store_url=%s, key_prefix=%s",
        payload.store_url,
        payload.consumer_key[:8] + "..." if len(payload.consumer_key) > 8 else payload.consumer_key,
    )

    connector = WooCommerceConnector(
        config={"store_url": payload.store_url},
        credentials={"consumer_key": payload.consumer_key, "consumer_secret": payload.consumer_secret},
    )
    result = await connector.test_connection()

    if not result.success:
        logger.warning(
            "WooCommerce test-connection failed: store_url=%s, message=%s",
            payload.store_url,
            result.message,
        )
    else:
        logger.info(
            "WooCommerce test-connection success: store_url=%s, products=%s",
            payload.store_url,
            (result.details or {}).get("products_count", "?"),
        )

    return {
        "success": result.success,
        "message": result.message,
        **(result.details or {}),
    }
