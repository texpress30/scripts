from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.email_notifications import (
    AgencyEmailNotificationDetailResponse,
    AgencyEmailNotificationListItem,
    AgencyEmailNotificationListResponse,
    AgencyEmailNotificationUpsertRequest,
)
from app.services.auth import AuthUser
from app.services.email_notifications import EffectiveEmailNotification, email_notifications_service

router = APIRouter(prefix="/agency/email-notifications", tags=["email_notifications"])


def _enforce_agency_admin(user: AuthUser) -> None:
    enforce_action_scope(user=user, action="clients:create", scope="agency")


def _serialize_notification(item: EffectiveEmailNotification) -> AgencyEmailNotificationDetailResponse:
    return AgencyEmailNotificationDetailResponse(
        key=item.key,
        label=item.label,
        description=item.description,
        channel=item.channel,
        scope=item.scope,
        template_key=item.template_key,
        enabled=item.enabled,
        default_enabled=item.default_enabled,
        is_overridden=item.is_overridden,
        updated_at=item.updated_at,
    )


@router.get("", response_model=AgencyEmailNotificationListResponse)
def list_agency_email_notifications(user: AuthUser = Depends(get_current_user)) -> AgencyEmailNotificationListResponse:
    _enforce_agency_admin(user)
    items = [
        AgencyEmailNotificationListItem(
            key=item.key,
            label=item.label,
            description=item.description,
            channel=item.channel,
            scope=item.scope,
            template_key=item.template_key,
            enabled=item.enabled,
            is_overridden=item.is_overridden,
            updated_at=item.updated_at,
        )
        for item in email_notifications_service.list_effective_notifications()
    ]
    return AgencyEmailNotificationListResponse(items=items)


@router.get("/{notification_key}", response_model=AgencyEmailNotificationDetailResponse)
def get_agency_email_notification_detail(
    notification_key: str,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailNotificationDetailResponse:
    _enforce_agency_admin(user)
    item = email_notifications_service.get_effective_notification(notification_key=notification_key)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification inexistent")
    return _serialize_notification(item)


@router.put("/{notification_key}", response_model=AgencyEmailNotificationDetailResponse)
def upsert_agency_email_notification(
    notification_key: str,
    payload: AgencyEmailNotificationUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailNotificationDetailResponse:
    _enforce_agency_admin(user)
    try:
        item = email_notifications_service.save_override(notification_key=notification_key, enabled=payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification inexistent")
    return _serialize_notification(item)


@router.post("/{notification_key}/reset", response_model=AgencyEmailNotificationDetailResponse)
def reset_agency_email_notification(
    notification_key: str,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailNotificationDetailResponse:
    _enforce_agency_admin(user)
    item = email_notifications_service.reset_override(notification_key=notification_key)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification inexistent")
    return _serialize_notification(item)
