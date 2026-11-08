from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


# ============ Advanced Econometrics ============

class IVIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    dependent: str
    endogenous: list[str] = Field(min_length=1)
    instruments: list[str] = Field(min_length=1)
    exogenous: Optional[list[str]] = None


class DiDIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    outcome: str
    treatment_col: str
    time_col: str
    post_period: Optional[str] = None


class JohansenIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    variables: list[str] = Field(min_length=2)
    det_order: int = 0
    k_ar_diff: int = Field(ge=1, le=10, default=1)


class VECMIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    variables: list[str] = Field(min_length=2)
    coint_rank: int = Field(ge=1)
    k_ar_diff: int = Field(ge=1, le=10, default=1)
