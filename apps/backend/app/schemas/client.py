from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    name: str
