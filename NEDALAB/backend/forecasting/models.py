from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from core.database import Base


class ForecastModel(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    model_type = Column(String(50), nullable=False)
    target_column = Column(String(150), nullable=False)
    params_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    trained_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    horizon = Column(Integer, nullable=False)
    predictions_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
