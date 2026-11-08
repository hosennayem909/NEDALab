from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from core.database import Base


class AutoMLRun(Base):
    __tablename__ = "automl_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    task_type = Column(String(20), nullable=False)
    target_column = Column(String(150), nullable=False)
    feature_columns_json = Column(Text, nullable=False)
    config_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="running")
    best_model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="SET NULL"), nullable=True)
    leaderboard_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    total_models_tested = Column(Integer, default=0)
    elapsed_seconds = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(180), nullable=False, index=True)


class ModelAPIKey(Base):
    __tablename__ = "model_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(200), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    call_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="api")  # ui, api, batch
    input_json = Column(Text, nullable=False)
    output_json = Column(Text, nullable=False)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
