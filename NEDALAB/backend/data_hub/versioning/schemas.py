from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class VersionOut(BaseModel):
    id: int
    dataset_id: int
    version_number: int
    parent_version_id: Optional[int] = None
    row_count: int
    column_count: int
    change_type: str
    change_description: Optional[str] = None
    change_details_json: Optional[str] = None
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class CreateVersionIn(BaseModel):
    dataset_id: int
    change_type: str = "manual_snapshot"
    change_description: Optional[str] = None


class RestoreIn(BaseModel):
    version_id: int
    change_description: Optional[str] = None


class CompareOut(BaseModel):
    version_a: VersionOut
    version_b: VersionOut
    rows_changed: int
    columns_added: list[str]
    columns_removed: list[str]
    columns_common: list[str]
    diff_preview: list[dict]
