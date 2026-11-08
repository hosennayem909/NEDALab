from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class LineIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    x_col: str
    y_cols: list[str] = Field(min_length=1)
    agg: str = "sum"


class BarIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    x_col: str
    y_col: str
    agg: str = "sum"
    top_n: Optional[int] = None


class ScatterIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    x_col: str
    y_col: str
    color_col: Optional[str] = None


class HistogramIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    col: str
    bins: int = Field(ge=5, le=200, default=30)


class BoxIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    col: str
    group_col: Optional[str] = None


class PieIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    category_col: str
    value_col: Optional[str] = None
    top_n: int = Field(ge=2, le=50, default=10)


class HeatmapIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    cols: list[str] = Field(min_length=2)
