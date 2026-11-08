from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

WorkspaceRole = Literal["admin", "researcher", "viewer"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)


class WorkspaceOut(BaseModel):
    id: int
    name: str
    slug: str
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MemberAdd(BaseModel):
    email: EmailStr
    role: WorkspaceRole = "viewer"


class MemberOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: EmailStr
    role: WorkspaceRole
    created_at: datetime


class WorkspaceDetail(BaseModel):
    workspace: WorkspaceOut
    members: list[MemberOut]
    my_role: WorkspaceRole | None = None
