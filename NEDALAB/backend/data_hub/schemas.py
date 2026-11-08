from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Literal, Any


class DatasetOut(BaseModel):
    id: int
    user_email: EmailStr
    filename: str
    row_count: int
    column_count: int
    status: str
    cleaned_path: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PreviewColumn(BaseModel):
    name: str
    dtype: str
    null_count: int
    unique_count: int


class PreviewOut(BaseModel):
    columns: list[PreviewColumn]
    rows: list[dict]
    total_rows: int
    preview_rows: int


class StatsOut(BaseModel):
    numeric: dict
    total_rows: int
    total_columns: int


# ---- Cleaning ----

PresetType = Literal["minimal", "standard", "aggressive", "custom"]
DuplicateStrategy = Literal["keep", "drop_all"]
MissingStrategy = Literal["keep", "drop_rows", "drop_columns", "auto", "mean", "median", "mode", "zero", "ffill", "bfill"]
OutlierStrategy = Literal["keep", "iqr", "zscore"]
StringStrategy = Literal["keep", "trim", "trim_lower"]


class CleanConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    preset: PresetType = "standard"
    drop_empty_rows: bool = True
    duplicates: DuplicateStrategy = "drop_all"
    missing: MissingStrategy = "auto"
    outliers: OutlierStrategy = "keep"
    strings: StringStrategy = "trim"


class CleaningPreviewOut(BaseModel):
    columns: list[PreviewColumn]
    rows: list[dict]
    total_rows: int
    preview_rows: int
    report: dict


class CleaningReportOut(BaseModel):
    dataset_id: int
    preset: str
    config: dict
    log: list[str]
    stats_before: dict
    stats_after: dict
    rows_removed: int
    columns_removed: int
    missing_filled: int
    created_at: datetime


# ---- Aggregation ----

FrequencyType = Literal["day", "week", "month"]
MethodType = Literal["sum", "mean", "count", "max", "min", "median"]


class ColumnInfoOut(BaseModel):
    all_columns: list[str]
    date_columns: list[str]
    numeric_columns: list[str]


class AggregateConfig(BaseModel):
    date_column: str
    value_columns: list[str]
    frequency: FrequencyType = "month"
    method: MethodType = "sum"


class AggregatePreviewOut(BaseModel):
    columns: list[PreviewColumn]
    rows: list[dict]
    total_rows: int
    preview_rows: int
    report: dict


class AggregateSaveOut(BaseModel):
    dataset: DatasetOut
    report: dict


# ---- Analytics ----

class AnalyticsOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    activity: list[dict]
    model_distribution: list[dict]
    growth: list[dict]
    best_models: list[dict]
    totals: dict


class CustomerAnalysisIn(BaseModel):
    customer_column: str = Field(min_length=1)
    date_column: str = Field(min_length=1)
    monetary_column: str = Field(min_length=1)
    transaction_column: str | None = None