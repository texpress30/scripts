from pydantic import BaseModel, Field


class TeamMemberItem(BaseModel):
    id: int
    membership_id: int | None = None
    user_id: int | None = None
    first_name: str
    last_name: str
    email: str
    phone: str
    extension: str
    user_type: str
    user_role: str
    location: str
    subaccount: str
    module_keys: list[str] = Field(default_factory=list)


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
    module_keys: list[str] | None = None


class TeamMemberResponse(BaseModel):
    item: TeamMemberItem


class TeamSubaccountOptionItem(BaseModel):
    id: int
    name: str
    label: str


class TeamSubaccountOptionsResponse(BaseModel):
    items: list[TeamSubaccountOptionItem]


class SubaccountTeamMemberItem(BaseModel):
    membership_id: int
    user_id: int
    display_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    extension: str
    role_key: str
    role_label: str
    source_scope: str
    source_label: str
    is_active: bool
    is_inherited: bool
    module_keys: list[str] = Field(default_factory=list)


class SubaccountTeamMemberListResponse(BaseModel):
    items: list[SubaccountTeamMemberItem]
    total: int
    page: int
    page_size: int
    subaccount_id: int


class CreateSubaccountTeamMemberRequest(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone: str = ""
    extension: str = ""
    user_role: str = "subaccount_user"
    password: str | None = None
    module_keys: list[str] | None = None


class SubaccountTeamMemberResponse(BaseModel):
    item: SubaccountTeamMemberItem


class TeamMemberInviteResponse(BaseModel):
    message: str


class TeamModuleCatalogItem(BaseModel):
    key: str
    label: str
    order: int
    scope: str


class TeamModuleCatalogResponse(BaseModel):
    items: list[TeamModuleCatalogItem]


class TeamGrantableModuleItem(BaseModel):
    key: str
    label: str
    order: int
    grantable: bool


class TeamGrantableModulesResponse(BaseModel):
    items: list[TeamGrantableModuleItem]


class TeamSubaccountMyAccessResponse(BaseModel):
    subaccount_id: int
    role: str
    module_keys: list[str] = Field(default_factory=list)
    source_scope: str = "subaccount"
    access_scope: str = "subaccount"
    unrestricted_modules: bool = False
