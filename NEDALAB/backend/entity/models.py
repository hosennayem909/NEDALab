from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from core.database import Base


class EntityRule(Base):
    __tablename__ = "entity_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    standard_value = Column(String(500), nullable=False)
    keywords_json = Column(Text, nullable=False)
    match_threshold = Column(Integer, nullable=False, default=80)
    match_type = Column(String(20), nullable=False, default="fuzzy")
    column_hint = Column(String(150), nullable=True)
    case_sensitive = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
