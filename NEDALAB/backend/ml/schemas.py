from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Literal, Any


TaskType = Literal["classification", "regression"]


class TrainIn(BaseModel):
    dataset_id: int
    target_column: str = Field(min_length=1, max_length=150)
    feature_columns: list[str] = Field(min_length=1)
    task_type: TaskType = "classification"
    algorithm: str = "random_forest"
    test_size: float = Field(ge=0.1, le=0.5, default=0.2)
    random_state: int = 42
    name: Optional[str] = None


class ModelOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    dataset_id: int
    name: str
    task_type: str
    algorithm: str
    target_column: str
    feature_columns_json: str
    hyperparams_json: Optional[str] = None
    metrics_json: str
    feature_importance_json: Optional[str] = None
    split_config_json: Optional[str] = None
    model_path: Optional[str] = None
    training_samples: int
    trained_by: str
    created_at: datetime


class TrainResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    name: str
    task_type: str
    algorithm: str
    target_column: str
    feature_columns: list[str]
    n_train: int
    n_test: int
    n_features: int
    metrics: dict
    feature_importance: list[dict]
    confusion_matrix: Optional[list[list[int]]] = None
    classification_report: Optional[dict] = None


# ============ ML Advanced Evaluation ============

class MLCrossValIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    algorithm: str
    task_type: str = "classification"
    n_folds: int = Field(ge=2, le=10, default=5)


class MLROCCurveIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    algorithm: str
    task_type: str = "classification"


class MLLearningCurveIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    algorithm: str
    task_type: str = "classification"
    n_folds: int = Field(ge=2, le=10, default=5)


class MLDiagnosticsIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    algorithm: str


# ============ ML Prediction ============

class SinglePredictIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_data: dict


class SinglePredictOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="allow")

    task_type: str
    raw_prediction: Any
    label: Optional[str] = None
    prediction: Optional[float] = None
    probabilities: Optional[list[float]] = None


class BatchPredictOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    n_rows: int
    stats: dict
    preview: list[dict]


# ============ Unsupervised Learning ============

class KMeansIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=1)
    n_clusters: int = Field(ge=2, le=20, default=3)
    sample_size: int = Field(ge=100, le=20000, default=5000)


class DBSCANIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=1)
    eps: float = Field(gt=0, default=0.5)
    min_samples: int = Field(ge=2, default=5)
    sample_size: int = Field(ge=100, le=20000, default=5000)


class PCAIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=2)
    n_components: Optional[int] = None
    sample_size: int = Field(ge=100, le=20000, default=5000)


class AnomalyIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    columns: list[str] = Field(min_length=1)
    contamination: float = Field(gt=0, le=0.5, default=0.05)
    sample_size: int = Field(ge=100, le=20000, default=10000)


# ============ ML Tuning + SHAP ============

class TuneIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: int
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    algorithm: str
    task_type: str = "classification"
    method: str = "grid"  # grid | random
    n_iter: int = Field(ge=5, le=100, default=20)
    cv_folds: int = Field(ge=2, le=10, default=5)


class ShapIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: int
    max_samples: int = Field(ge=10, le=500, default=100)
