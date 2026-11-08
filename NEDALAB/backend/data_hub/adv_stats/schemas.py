from pydantic import BaseModel, Field
from typing import Literal


TransformMethod = Literal["winsorize", "log", "sqrt", "boxcox"]
FillMethod = Literal["ffill", "bfill", "zero", "mean"]
TSFrequency = Literal["day", "week", "month"]


class TransformPreviewIn(BaseModel):
    column: str
    method: TransformMethod
    lower_pct: float = 1.0
    upper_pct: float = 99.0


class TransformPreviewOut(BaseModel):
    column: str
    method: str
    meta: dict
    before: dict | None = None
    after: dict | None = None


class TransformApplyIn(BaseModel):
    column: str
    method: TransformMethod
    lower_pct: float = 1.0
    upper_pct: float = 99.0
    save_as_new: bool = True


class TimeSeriesAnalyzeOut(BaseModel):
    gaps: dict
    stationarity: dict
    value_column: str


class TimeSeriesFillIn(BaseModel):
    date_column: str
    frequency: TSFrequency = "day"
    method: FillMethod = "ffill"
    value_columns: list[str] | None = None


class DifferenceIn(BaseModel):
    column: str
    order: int = Field(ge=1, le=3, default=1)
    save_as_new: bool = True


class TransformApplyOut(BaseModel):
    output_dataset_id: int
    output_filename: str
    column: str
    method: str
    meta: dict
