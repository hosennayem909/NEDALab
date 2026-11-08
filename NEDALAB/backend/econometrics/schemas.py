from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Any, Optional


class OLSTrainIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dataset_id: int
    dependent_var: str = Field(min_length=1, max_length=150)
    independent_vars: list[str] = Field(min_length=1)
    name: Optional[str] = None
    add_constant: bool = True


class CoefficientRow(BaseModel):
    variable: str
    coef: float
    std_err: float
    t_stat: float
    p_value: float
    ci_lower: float
    ci_upper: float
    significance: str


class ModelOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    dataset_id: int
    name: str
    model_type: str
    dependent_var: str
    independent_vars_json: str
    params_json: str
    metrics_json: str
    diagnostics_json: Optional[str] = None
    trained_by: str
    created_at: datetime


class OLSResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    dependent_var: str
    independent_vars: list[str]
    n_obs: int
    coefficients: list[CoefficientRow]
    r_squared: float
    adj_r_squared: float
    f_statistic: float
    f_pvalue: float
    aic: float
    bic: float
    durbin_watson: float
    residual_stats: dict[str, Any]
    interpretation: dict[str, Any]


# ============ Statistical Tests ============

class CorrelationIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=2)


class VIFIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=2)


class GrangerIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    cause: str
    effect: str
    max_lag: int = Field(ge=1, le=20, default=5)


class DescriptivesIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=1)


class CorrelationOut(BaseModel):
    columns: list[str]
    pearson: dict
    spearman: dict
    high_correlations: list[dict]
    n_obs: int


class VIFOut(BaseModel):
    variables: list[dict]
    high_vif_count: int
    high_vif_vars: list[str]
    n_obs: int


class GrangerOut(BaseModel):
    cause: str
    effect: str
    max_lag: int
    results: list[dict]
    has_causality: bool
    significant_lags: list[int]
    interpretation: str
    n_obs: int


class DescriptivesOut(BaseModel):
    variables: list[dict]
    n_columns: int


# ============ Panel Data ============

class PanelTrainIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    entity_col: str
    time_col: str
    dependent_var: str
    independent_vars: list[str] = Field(min_length=1)
    model_type: str = "fixed"  # fixed | random | pooled
    name: Optional[str] = None


class HausmanIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    entity_col: str
    time_col: str
    dependent_var: str
    independent_vars: list[str] = Field(min_length=1)


# ============ VAR ============

class VARIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    variables: list[str] = Field(min_length=2)
    max_lags: int = Field(ge=1, le=20, default=5)
    lag_order: Optional[int] = None


class IRFIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    variables: list[str] = Field(min_length=2)
    max_lags: int = Field(ge=1, le=20, default=5)
    lag_order: Optional[int] = None
    periods: int = Field(ge=1, le=50, default=10)
    shock_var: Optional[str] = None


class FEVDIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    variables: list[str] = Field(min_length=2)
    max_lags: int = Field(ge=1, le=20, default=5)
    lag_order: Optional[int] = None
    periods: int = Field(ge=1, le=50, default=10)
