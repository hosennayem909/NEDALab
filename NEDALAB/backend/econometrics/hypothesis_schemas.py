from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class TTestIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    test_variant: str = "one_sample"  # one_sample, two_sample, paired
    column: Optional[str] = None
    popmean: Optional[float] = None
    group_column: Optional[str] = None
    column_a: Optional[str] = None
    column_b: Optional[str] = None
    equal_var: bool = True


class ANOVAIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column: str
    group_column: str


class ChiSquareIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column_a: str
    column_b: str


class NonParamIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column: str
    group_column: str


class ShapiroIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column: str


class LeveneIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column: str
    group_column: str


class SuiteIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column_a: str
    column_b: Optional[str] = None
    group_column: Optional[str] = None
    popmean: Optional[float] = None


class CorrelationIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column_a: str
    column_b: str


class TukeyHSDIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    column: str
    group_column: str