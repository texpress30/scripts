from pydantic import BaseModel


class AgencyEmailTemplateListItem(BaseModel):
    key: str
    label: str
    description: str
    scope: str


class AgencyEmailTemplateListResponse(BaseModel):
    items: list[AgencyEmailTemplateListItem]


class AgencyEmailTemplateDetailResponse(BaseModel):
    key: str
    label: str
    description: str
    default_subject: str
    default_text_body: str
    default_html_body: str
    available_variables: list[str]
    scope: str
