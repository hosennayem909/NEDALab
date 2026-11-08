"""SQLAlchemy models for the Data Hub domain.

This module keeps the dataset, cleaning-report, and aggregation records in one
place so the rest of the backend can import a single, stable API.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from core.database import Base

DEFAULT_DATASET_STATUS: Final[str] = "processed"
DEFAULT_CLEANING_PRESET: Final[str] = "standard"

__all__ = ["Dataset", "CleaningReport", "Aggregation"]


class Dataset(Base):
    """Represents an uploaded or generated dataset managed by the platform."""

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(180), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    row_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    status = Column(String(30), default=DEFAULT_DATASET_STATUS)
    cleaned_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CleaningReport(Base):
    """Stores the cleaning configuration and metrics for a dataset."""

    __tablename__ = "cleaning_reports"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preset = Column(String(30), nullable=False, default=DEFAULT_CLEANING_PRESET)
    config_json = Column(Text, nullable=False)
    log_json = Column(Text, nullable=False)
    stats_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Aggregation(Base):
    """Records a dataset aggregation job and its resulting dataset."""

    __tablename__ = "aggregations"

    id = Column(Integer, primary_key=True, index=True)
    source_dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result_dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date_column = Column(String(150), nullable=False)
    value_columns_json = Column(Text, nullable=False)
    frequency = Column(String(10), nullable=False)
    method = Column(String(20), nullable=False)
    report_json = Column(Text, nullable=False)
    created_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
