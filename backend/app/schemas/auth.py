from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MIN_PASSWORD_LENGTH = 10


def _validate_password(v: str) -> str:
    if len(v) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if v.isdigit() or v.isalpha():
        raise ValueError("Password must mix letters with numbers or symbols")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=120)

    _check = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(max_length=128)

    _check = field_validator("new_password")(_validate_password)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    _check = field_validator("new_password")(_validate_password)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: Optional[str]
    currency: str
    created_at: datetime
    last_login_at: Optional[datetime]


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
