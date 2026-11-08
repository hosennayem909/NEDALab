from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


MatchType = Literal["fuzzy", "exact", "contains", "regex"]


class EntityRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    standard_value: str = Field(min_length=1, max_length=500)
    keywords: list[str] = Field(min_length=1)
    match_threshold: int = Field(ge=50, le=100, default=80)
    match_type: MatchType = "fuzzy"
    column_hint: str | None = None
    case_sensitive: bool = False
    active: bool = True


class EntityRuleUpdate(BaseModel):
    name: str | None = None
    standard_value: str | None = None
    keywords: list[str] | None = None
    match_threshold: int | None = Field(default=None, ge=50, le=100)
    match_type: MatchType | None = None
    column_hint: str | None = None
    case_sensitive: bool | None = None
    active: bool | None = None


class EntityRuleOut(BaseModel):
    id: int
    name: str
    standard_value: str
    keywords: list[str]
    match_threshold: int
    match_type: str
    column_hint: str | None = None
    case_sensitive: bool
    active: bool
    created_at: datetime


class TestMatchIn(BaseModel):
    values: list[str]
    rules: list[EntityRuleCreate] | None = None


class TestMatchResult(BaseModel):
    original: str
    matched: bool
    standard_value: str | None = None
    matched_keyword: str | None = None
    score: float = 0.0
    rule_name: str | None = None


class TestMatchOut(BaseModel):
    total: int
    matched_count: int
    results: list[TestMatchResult]


class ApplyMappingIn(BaseModel):
    dataset_id: int
    column: str
    save_as_new: bool = True
    output_name: str | None = None


class ApplyMappingOut(BaseModel):
    dataset_id: int
    column: str
    total_rows: int
    changed_rows: int
    mapping_summary: list[dict]
    output_dataset_id: int
    output_filename: str
