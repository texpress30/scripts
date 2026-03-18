from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.email_templates import (
    AgencyEmailTemplateDetailResponse,
    AgencyEmailTemplateListItem,
    AgencyEmailTemplateListResponse,
    AgencyEmailTemplatePreviewRequest,
    AgencyEmailTemplatePreviewResponse,
    AgencyEmailTemplateTestSendRequest,
    AgencyEmailTemplateTestSendResponse,
    AgencyEmailTemplateUpsertRequest,
)
from app.services.auth import AuthUser
from app.services.email_templates import EffectiveEmailTemplate, email_templates_service
from app.services.mailgun_service import MailgunIntegrationError

router = APIRouter(prefix="/agency/email-templates", tags=["email_templates"])


def _enforce_agency_admin(user: AuthUser) -> None:
    enforce_action_scope(user=user, action="clients:create", scope="agency")


def _serialize_template(item: EffectiveEmailTemplate) -> AgencyEmailTemplateDetailResponse:
    return AgencyEmailTemplateDetailResponse(
        key=item.key,
        label=item.label,
        description=item.description,
        subject=item.subject,
        text_body=item.text_body,
        html_body=item.html_body,
        available_variables=list(item.available_variables),
        scope=item.scope,
        enabled=item.enabled,
        is_overridden=item.is_overridden,
        updated_at=item.updated_at,
    )


@router.get("", response_model=AgencyEmailTemplateListResponse)
def list_agency_email_templates(user: AuthUser = Depends(get_current_user)) -> AgencyEmailTemplateListResponse:
    _enforce_agency_admin(user)
    items = [
        AgencyEmailTemplateListItem(
            key=item.key,
            label=item.label,
            description=item.description,
            scope=item.scope,
            enabled=item.enabled,
            is_overridden=item.is_overridden,
            updated_at=item.updated_at,
        )
        for item in email_templates_service.list_effective_templates()
    ]
    return AgencyEmailTemplateListResponse(items=items)


@router.get("/{template_key}", response_model=AgencyEmailTemplateDetailResponse)
def get_agency_email_template_detail(
    template_key: str,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplateDetailResponse:
    _enforce_agency_admin(user)
    item = email_templates_service.get_effective_template(template_key=template_key)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")
    return _serialize_template(item)


@router.put("/{template_key}", response_model=AgencyEmailTemplateDetailResponse)
def upsert_agency_email_template(
    template_key: str,
    payload: AgencyEmailTemplateUpsertRequest,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplateDetailResponse:
    _enforce_agency_admin(user)
    try:
        item = email_templates_service.save_override(
            template_key=template_key,
            subject=payload.subject,
            text_body=payload.text_body,
            html_body=payload.html_body,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")
    return _serialize_template(item)


@router.post("/{template_key}/reset", response_model=AgencyEmailTemplateDetailResponse)
def reset_agency_email_template(
    template_key: str,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplateDetailResponse:
    _enforce_agency_admin(user)
    item = email_templates_service.reset_override(template_key=template_key)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")
    return _serialize_template(item)


@router.post("/{template_key}/preview", response_model=AgencyEmailTemplatePreviewResponse)
def preview_agency_email_template(
    template_key: str,
    payload: AgencyEmailTemplatePreviewRequest,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplatePreviewResponse:
    _enforce_agency_admin(user)
    preview = email_templates_service.render_template_preview(
        template_key=template_key,
        subject=payload.subject,
        text_body=payload.text_body,
        html_body=payload.html_body,
    )
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")
    return AgencyEmailTemplatePreviewResponse(
        key=preview.key,
        rendered_subject=preview.rendered_subject,
        rendered_text_body=preview.rendered_text_body,
        rendered_html_body=preview.rendered_html_body,
        sample_variables=preview.sample_variables,
        is_overridden=preview.is_overridden,
    )


@router.post("/{template_key}/test-send", response_model=AgencyEmailTemplateTestSendResponse)
def test_send_agency_email_template(
    template_key: str,
    payload: AgencyEmailTemplateTestSendRequest,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplateTestSendResponse:
    _enforce_agency_admin(user)
    try:
        result = email_templates_service.send_template_test_email(
            template_key=template_key,
            to_email=payload.to_email,
            subject=payload.subject,
            text_body=payload.text_body,
            html_body=payload.html_body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MailgunIntegrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")

    return AgencyEmailTemplateTestSendResponse(
        key=result.key,
        to_email=result.to_email,
        accepted=result.accepted,
        delivery_status=result.delivery_status,
        rendered_subject=result.rendered_subject,
        provider_message=result.provider_message,
        provider_id=result.provider_id,
    )
