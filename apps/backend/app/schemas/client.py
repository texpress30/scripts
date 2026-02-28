from pydantic import BaseModel

class CreateClientRequest(BaseModel):
    name: str

class AttachGoogleAccountRequest(BaseModel):
    customer_id: str

class DetachGoogleAccountRequest(BaseModel):
    customer_id: str

class UpdateClientProfileRequest(BaseModel):
    name: str | None = None
    client_logo_url: str | None = None
    client_type: str | None = None
    account_manager: str | None = None
    currency: str | None = None
    platform: str | None = None
    account_id: str | None = None
