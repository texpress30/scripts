from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.creative_workflow import creative_workflow_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service

router = APIRouter(prefix="/creative", tags=["creative-library", "ai-generation", "approvals", "publish"])


class CreateAssetRequest(BaseModel):
    client_id: int
    name: str
    format: str
    dimensions: str
    objective_fit: str
    platform_fit: list[str] = Field(default_factory=list)
    language: str
    brand_tags: list[str] = Field(default_factory=list)
    legal_status: str = "pending"
    approval_status: str = "draft"


class AddVariantRequest(BaseModel):
    headline: str
    body: str
    cta: str
    media: str


class GenerateVariantsRequest(BaseModel):
    count: int = 3


class UpdateApprovalRequest(BaseModel):
    legal_status: str
    approval_status: str


class LinkCampaignRequest(BaseModel):
    campaign_id: int
    ad_set_id: int


class PerformanceScoresRequest(BaseModel):
    performance_scores: dict[str, float]


class PublishRequest(BaseModel):
    channel: str
    variant_id: int | None = None


@router.get("/library/assets")
def list_assets(client_id: int | None = None, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:list", scope="subaccount")
        rate_limiter_service.check(f"creative_list:{user.email}", limit=90, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    return {"items": creative_workflow_service.list_assets(client_id=client_id)}


@router.post("/library/assets")
def create_asset(payload: CreateAssetRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_create:{user.email}", limit=45, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    created = creative_workflow_service.create_asset(
        client_id=payload.client_id,
        name=payload.name,
        format=payload.format,
        dimensions=payload.dimensions,
        objective_fit=payload.objective_fit,
        platform_fit=payload.platform_fit,
        language=payload.language,
        brand_tags=payload.brand_tags,
        legal_status=payload.legal_status,
        approval_status=payload.approval_status,
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="creative_library.create_asset",
        resource=f"client:{payload.client_id}",
        details={"asset_id": created["id"]},
    )
    return created


@router.post("/library/assets/{asset_id}/variants")
def add_variant(asset_id: int, payload: AddVariantRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_variant_add:{user.email}", limit=45, window_seconds=60)
        created = creative_workflow_service.add_variant(asset_id, payload.headline, payload.body, payload.cta, payload.media)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return created


@router.post("/ai-generation/assets/{asset_id}/variants")
def generate_variants(asset_id: int, payload: GenerateVariantsRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_ai_generate:{user.email}", limit=30, window_seconds=60)
        items = creative_workflow_service.generate_variants(asset_id=asset_id, count=max(1, payload.count))
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {"asset_id": asset_id, "items": items}


@router.post("/approvals/assets/{asset_id}")
def update_approval(asset_id: int, payload: UpdateApprovalRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_approve:{user.email}", limit=45, window_seconds=60)
        updated = creative_workflow_service.update_approval(
            asset_id=asset_id,
            legal_status=payload.legal_status,
            approval_status=payload.approval_status,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return updated


@router.post("/library/assets/{asset_id}/links")
def link_campaign(asset_id: int, payload: LinkCampaignRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, int]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_link:{user.email}", limit=45, window_seconds=60)
        link = creative_workflow_service.link_to_campaign(
            asset_id=asset_id,
            campaign_id=payload.campaign_id,
            ad_set_id=payload.ad_set_id,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return link


@router.post("/library/assets/{asset_id}/performance")
def update_performance(asset_id: int, payload: PerformanceScoresRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_perf:{user.email}", limit=45, window_seconds=60)
        updated = creative_workflow_service.set_performance_scores(asset_id, payload.performance_scores)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return updated


@router.post("/publish/assets/{asset_id}/to-channel")
def publish_to_channel(asset_id: int, payload: PublishRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="creative:write", scope="subaccount")
        rate_limiter_service.check(f"creative_publish:{user.email}", limit=20, window_seconds=60)
        publish = creative_workflow_service.publish_to_channel(
            asset_id=asset_id,
            channel=payload.channel,
            variant_id=payload.variant_id,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="creative_publish.to_channel",
        resource=f"asset:{asset_id}",
        details=publish,
    )
    return publish
