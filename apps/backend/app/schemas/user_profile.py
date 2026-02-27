from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    email: str
    first_name: str
    last_name: str
    phone: str
    extension: str
    platform_language: str


class UpdateUserProfileRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str = ""
    extension: str = ""
    platform_language: str = "ro"


class UpdatePasswordRequest(BaseModel):
    current_password: str
    password: str
    confirm_password: str
