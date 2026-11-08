from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task_type: str
    dataset_id: Optional[int] = None
    schedule: str = "daily"  # daily | weekly | monthly | "0 9 * * *"
    config_json: Optional[str] = None
    enabled: bool = True


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    user_id: int
    name: str
    task_type: str
    dataset_id: Optional[int] = None
    schedule: str
    config_json: Optional[str] = None
    enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskRunOut(BaseModel):
    id: int
    task_id: int
    status: str
    message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
