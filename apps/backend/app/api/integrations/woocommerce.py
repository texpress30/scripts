from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.services.auth import AuthUser

router = APIRouter(prefix="/integrations/woocommerce", tags=["integrations-woocommerce"])


class WooCommerceTestConnectionRequest(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str


@router.post("/test-connection")
async def test_connection(payload: WooCommerceTestConnectionRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    from app.services.feed_management.connectors.woocommerce_connector import WooCommerceConnector

    connector = WooCommerceConnector(
        config={"store_url": payload.store_url},
        credentials={"consumer_key": payload.consumer_key, "consumer_secret": payload.consumer_secret},
    )
    result = await connector.test_connection()
    return {
        "success": result.success,
        "message": result.message,
        **(result.details or {}),
    }
