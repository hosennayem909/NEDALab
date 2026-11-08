from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from core.database import Base


class RegressionModel(Base):
    __tablename__ = "regression_models"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    model_type = Column(String(30), nullable=False, default="ols")
    dependent_var = Column(String(150), nullable=False)
    independent_vars_json = Column(Text, nullable=False)
    params_json = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False)
    diagnostics_json = Column(Text, nullable=True)
    trained_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
