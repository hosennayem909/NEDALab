from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from core.database import Base


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    parent_version_id = Column(Integer, ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True)
    snapshot_path = Column(String(500), nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)
    change_type = Column(String(50), nullable=False)
    change_description = Column(Text, nullable=True)
    change_details_json = Column(Text, nullable=True)
    created_by = Column(String(180), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
