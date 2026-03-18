from datetime import datetime

from pydantic import BaseModel


class AgencyEmailTemplateListItem(BaseModel):
    key: str
    label: str
    description: str
    scope: str
    enabled: bool
    is_overridden: bool
    updated_at: datetime | None


class AgencyEmailTemplateListResponse(BaseModel):
    items: list[AgencyEmailTemplateListItem]


class AgencyEmailTemplateDetailResponse(BaseModel):
    key: str
    label: str
    description: str
    subject: str
    text_body: str
    html_body: str
    available_variables: list[str]
    scope: str
    enabled: bool
    is_overridden: bool
    updated_at: datetime | None


class AgencyEmailTemplateUpsertRequest(BaseModel):
    subject: str
    text_body: str
    html_body: str | None = None
    enabled: bool | None = None
