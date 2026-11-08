from pydantic import BaseModel
from typing import Any


class DistributionStats(BaseModel):
    n: int
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q1: float | None = None
    q25: float | None = None
    q75: float | None = None
    q99: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    cv_pct: float | None = None
    shapiro_p: float | None = None
    is_normal: bool | None = None
    skew_interpretation: str | None = None
    error: str | None = None


class OutlierCount(BaseModel):
    count: int
    pct: float | None = None
    threshold: float | None = None
    lower: float | None = None
    upper: float | None = None


class ColumnStats(BaseModel):
    name: str
    distribution: DistributionStats
    outliers_iqr: OutlierCount
    outliers_zscore: OutlierCount
    outliers_mad: OutlierCount


class DataFrameStatsOut(BaseModel):
    total_rows: int
    numeric_columns: int
    columns: list[ColumnStats]
