from pydantic import BaseModel, Field


class TeamMemberItem(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    extension: str
    user_type: str
    user_role: str
    location: str
    subaccount: str


class TeamMemberListResponse(BaseModel):
    items: list[TeamMemberItem]
    total: int
    page: int
    page_size: int


class CreateTeamMemberRequest(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone: str = ""
    extension: str = ""
    user_type: str = "agency"
    user_role: str = "member"
    location: str = "România"
    subaccount: str = "Toate"
    password: str | None = None


class TeamMemberResponse(BaseModel):
    item: TeamMemberItem


class TeamSubaccountOptionItem(BaseModel):
    id: int
    name: str
    label: str


class TeamSubaccountOptionsResponse(BaseModel):
    items: list[TeamSubaccountOptionItem]
