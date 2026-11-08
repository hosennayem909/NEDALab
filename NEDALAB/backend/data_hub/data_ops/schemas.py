from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class FormulaIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    formula: str = Field(min_length=1)
    new_column: str = Field(min_length=1, max_length=150)
    save_as_new: bool = True
    output_name: Optional[str] = None


class JoinIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    left_dataset_id: int
    right_dataset_id: int
    left_key: str
    right_key: str
    join_type: str = "inner"
    output_name: Optional[str] = None
