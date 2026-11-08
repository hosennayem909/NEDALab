from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from core.database import Base


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    task_type = Column(String(20), nullable=False)
    algorithm = Column(String(50), nullable=False)
    target_column = Column(String(150), nullable=False)
    feature_columns_json = Column(Text, nullable=False)
    hyperparams_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=False)
    feature_importance_json = Column(Text, nullable=True)
    split_config_json = Column(Text, nullable=True)
    model_path = Column(String(500), nullable=True)
    training_samples = Column(Integer, default=0)
    trained_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
