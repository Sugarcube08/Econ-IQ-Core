import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from core.models.auth_models import UserRole


class OTPRequestSchema(BaseModel):
    email: EmailStr


class OTPVerifySchema(BaseModel):
    email: EmailStr
    otp: str
    device_id: str | None = None


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequestSchema(BaseModel):
    refresh_token: str
    device_id: str | None = None


class UserResponseSchema(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    is_superuser: bool
    permissions: list[str]
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreateSchema(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.VIEWER


class UserUpdateSchema(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserListResponseData(BaseModel):
    users: list[UserResponseSchema]


class APIKeyCreateSchema(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=list)


class APIKeyResponseSchema(BaseModel):
    id: uuid.UUID
    key_prefix: str
    name: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreateResponseSchema(APIKeyResponseSchema):
    raw_key: str
