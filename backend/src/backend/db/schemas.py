import uuid

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    banner_id: str | None = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MeResponse(BaseModel):
    user: UserResponse


class ResetPasswordRequest(BaseModel):
    email: str


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    postgres: str
    banner: str
