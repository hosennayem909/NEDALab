from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

Role = Literal["admin", "researcher", "viewer"]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    role: Role = "viewer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- Profile ----

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=72)


class PasswordResetIn(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=6, max_length=72)
    confirm_password: str = Field(min_length=6, max_length=72)


class ProfileStats(BaseModel):
    datasets: int
    models: int
    workspaces: int
    account_age_days: int


class ProfileOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    created_at: datetime
    stats: ProfileStats
