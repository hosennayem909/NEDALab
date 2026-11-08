"""Pydantic schemas for Online Learning."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class OnlineInitIn(BaseModel):
    """Initialize an online learning session."""
    dataset_id: int
    target: str
    features: List[str]
    task: str = "regression"  # "regression" or "classification"
    model: str = "linear"  # "linear", "tree", "forest"


class OnlineStepIn(BaseModel):
    """Feed one new sample and get prediction."""
    session_id: str
    x: Dict[str, Any]
    y: Optional[float] = None
    learn: bool = True


class OnlineBatchIn(BaseModel):
    """Feed multiple samples."""
    session_id: str
    samples: List[Dict[str, Any]]
    learn: bool = True


class OnlineSessionOut(BaseModel):
    """Session info — model_config disables protected namespace check."""
    model_config = ConfigDict(protected_namespaces=())

    session_id: str
    model_name: str
    task: str
    n_samples_seen: int
    metric_name: str
    metric_value: Optional[float] = None
    rolling_metric: Optional[float] = None
    features: List[str]
    target: str