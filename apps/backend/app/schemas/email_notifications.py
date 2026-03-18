from datetime import datetime

from pydantic import BaseModel


class AgencyEmailNotificationListItem(BaseModel):
    key: str
    label: str
    description: str
    channel: str
    scope: str
    template_key: str
    enabled: bool
    is_overridden: bool
    updated_at: datetime | None


class AgencyEmailNotificationListResponse(BaseModel):
    items: list[AgencyEmailNotificationListItem]


class AgencyEmailNotificationDetailResponse(BaseModel):
    key: str
    label: str
    description: str
    channel: str
    scope: str
    template_key: str
    enabled: bool
    default_enabled: bool
    is_overridden: bool
    updated_at: datetime | None


class AgencyEmailNotificationUpsertRequest(BaseModel):
    enabled: bool | None = None
