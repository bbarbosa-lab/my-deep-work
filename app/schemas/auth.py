from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def strength(cls, v: str) -> str:
        if v.lower() == v or v.upper() == v:
            raise ValueError("Password must mix upper and lower case")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    detail: str
