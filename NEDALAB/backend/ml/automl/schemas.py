from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AutoMLIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    task_type: str = "auto"
    test_size: float = Field(ge=0.1, le=0.5, default=0.2)
    random_state: int = 42
    max_models: int = Field(ge=3, le=10, default=8)
    name: Optional[str] = None


class APIKeyCreateIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: int
    name: Optional[str] = None


class APIKeyOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    model_id: int
    key_prefix: str
    name: Optional[str] = None
    active: bool
    call_count: int
    created_at: str
    last_used_at: Optional[str] = None


class APIKeyCreatedOut(BaseModel):
    """Returned only ONCE on creation with the full key."""
    model_config = ConfigDict(protected_namespaces=())

    id: int
    model_id: int
    api_key: str
    key_prefix: str
    name: Optional[str] = None


class PredictExternalIn(BaseModel):
    """External API prediction input."""
    features: dict


class DriftCheckIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: int
    dataset_id: int  # comparison dataset
