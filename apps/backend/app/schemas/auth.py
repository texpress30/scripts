from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ImpersonateRequest(BaseModel):
    email: str
    role: str


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordConfirmResponse(BaseModel):
    message: str
