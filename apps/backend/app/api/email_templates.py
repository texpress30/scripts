from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.email_templates import (
    AgencyEmailTemplateDetailResponse,
    AgencyEmailTemplateListItem,
    AgencyEmailTemplateListResponse,
)
from app.services.auth import AuthUser
from app.services.email_templates import email_templates_service

router = APIRouter(prefix="/agency/email-templates", tags=["email_templates"])


def _enforce_agency_admin(user: AuthUser) -> None:
    enforce_action_scope(user=user, action="clients:create", scope="agency")


@router.get("", response_model=AgencyEmailTemplateListResponse)
def list_agency_email_templates(user: AuthUser = Depends(get_current_user)) -> AgencyEmailTemplateListResponse:
    _enforce_agency_admin(user)
    items = [
        AgencyEmailTemplateListItem(
            key=item.key,
            label=item.label,
            description=item.description,
            scope=item.scope,
        )
        for item in email_templates_service.list_templates()
    ]
    return AgencyEmailTemplateListResponse(items=items)


@router.get("/{template_key}", response_model=AgencyEmailTemplateDetailResponse)
def get_agency_email_template_detail(
    template_key: str,
    user: AuthUser = Depends(get_current_user),
) -> AgencyEmailTemplateDetailResponse:
    _enforce_agency_admin(user)
    item = email_templates_service.get_template(template_key=template_key)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template inexistent")

    return AgencyEmailTemplateDetailResponse(
        key=item.key,
        label=item.label,
        description=item.description,
        default_subject=item.default_subject,
        default_text_body=item.default_text_body,
        default_html_body=item.default_html_body,
        available_variables=list(item.available_variables),
        scope=item.scope,
    )
