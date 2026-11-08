from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class ImputeIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    method: str = "knn"  # knn | mice | interpolate
    columns: Optional[list[str]] = None
    n_neighbors: int = Field(ge=2, le=20, default=5)
    max_iter: int = Field(ge=1, le=30, default=10)
    output_name: Optional[str] = None
