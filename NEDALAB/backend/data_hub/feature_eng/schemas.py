from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class LagConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    lags: list[int] = Field(default_factory=lambda: [1])


class RollingConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    windows: list[int] = Field(default_factory=lambda: [3])
    stats: list[str] = Field(default_factory=lambda: ["mean"])


class DiffConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    order: int = 1


class InteractionConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    pairs: list[list[str]] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=lambda: ["multiply"])


class PolynomialConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    degrees: list[int] = Field(default_factory=lambda: [2])


class DateConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=lambda: ["year", "month", "day"])


class BinningConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    n_bins: int = Field(ge=2, le=50, default=5)
    strategy: str = "equal_width"


class OneHotConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    max_categories: int = Field(ge=2, le=100, default=20)


class FeatureEngConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    lag: LagConfig = Field(default_factory=LagConfig)
    rolling: RollingConfig = Field(default_factory=RollingConfig)
    diff: DiffConfig = Field(default_factory=DiffConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    polynomial: PolynomialConfig = Field(default_factory=PolynomialConfig)
    date: DateConfig = Field(default_factory=DateConfig)
    binning: BinningConfig = Field(default_factory=BinningConfig)
    onehot: OneHotConfig = Field(default_factory=OneHotConfig)
    save_as_new: bool = True
    output_name: Optional[str] = None
