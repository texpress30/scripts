from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.ai_assistant import ai_assistant_service
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.recommendations import recommendations_service

router = APIRouter(prefix="/ai", tags=["ai"])


class RecommendationReviewRequest(BaseModel):
    action: Literal["approve", "dismiss", "snooze"]
    snooze_days: int = 3


@router.get("/recommendations/{client_id}")
def campaign_recommendation(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="recommendations:list", scope="subaccount")
        rate_limiter_service.check(f"ai:{user.email}", limit=15, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    generated = recommendations_service.generate_recommendations(client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="ai.recommendation.generate",
        resource=f"client:{client_id}",
        details={"count": len(generated), "source": "rules+llm"},
    )
    return {"client_id": client_id, "items": generated}


@router.get("/recommendations/{client_id}/list")
def list_recommendations(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="recommendations:list", scope="subaccount")
        rate_limiter_service.check(f"ai_list:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    return {"client_id": client_id, "items": recommendations_service.list_recommendations(client_id)}


@router.post("/recommendations/{client_id}/{recommendation_id}/review")
def review_recommendation(
    client_id: int,
    recommendation_id: int,
    payload: RecommendationReviewRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="recommendations:review", scope="subaccount")
        rate_limiter_service.check(f"ai_review:{user.email}", limit=60, window_seconds=60)
        updated = recommendations_service.review_recommendation(
            client_id=client_id,
            recommendation_id=recommendation_id,
            action=payload.action,
            actor=user.email,
            snooze_days=payload.snooze_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action=f"ai.recommendation.{payload.action}",
        resource=f"recommendation:{recommendation_id}",
        details={"client_id": client_id, "status": updated["status"]},
    )
    return updated


@router.get("/recommendations/{client_id}/actions")
def list_recommendation_actions(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="recommendations:list", scope="subaccount")
    return {"client_id": client_id, "items": recommendations_service.list_actions(client_id)}


@router.get("/recommendations/{client_id}/impact-report")
def recommendation_impact_report(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="recommendations:list", scope="subaccount")
    return recommendations_service.get_impact_report(client_id)


@router.get("/legacy/{client_id}")
def legacy_text_recommendation(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="recommendations:list", scope="subaccount")
    return ai_assistant_service.generate_recommendation(client_id)
