from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    name: str


class AttachGoogleAccountRequest(BaseModel):
    customer_id: str


class DetachGoogleAccountRequest(BaseModel):
    customer_id: str


class UpdateClientProfileRequest(BaseModel):
    client_type: str
    account_manager: str
