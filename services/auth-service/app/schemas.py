from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── 요청 ───────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, description="8자 이상")
    phone: Optional[str] = Field(None, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ── 응답 ───────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
