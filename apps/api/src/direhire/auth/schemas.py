from pydantic import BaseModel


class SessionRead(BaseModel):
    role: str
    plan: str
