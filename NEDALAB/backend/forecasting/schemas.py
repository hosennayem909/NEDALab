from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Literal, Any

ModelType = Literal[
    "linear",
    "moving_average",
    "arima",
    "polynomial",
    "exponential_smoothing",
]


class TrainIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dataset_id: int
    target_column: str = Field(min_length=1, max_length=150)
    model_type: ModelType = "linear"
    name: str | None = None


class ModelOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    dataset_id: int
    name: str
    model_type: str
    target_column: str
    params_json: str | None = None
    metrics_json: str | None = None
    trained_by: str
    created_at: datetime


class PredictIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    horizon: int = Field(ge=1, le=365)


class PredictOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    horizon: int
    predictions: list[float]
    model_type: str
    metrics: dict[str, Any]
