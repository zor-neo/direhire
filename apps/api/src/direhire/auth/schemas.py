from pydantic import BaseModel, Field


class SessionRead(BaseModel):
    role: str
    plan: str


class MfaSetupRead(BaseModel):
    secret_code: str
    account_name: str
    issuer: str = "DireHire"


class MfaVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
