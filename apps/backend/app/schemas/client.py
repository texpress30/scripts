from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    name: str


class AttachGoogleAccountRequest(BaseModel):
    customer_id: str
