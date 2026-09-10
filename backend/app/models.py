from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from datetime import datetime
from .database import Base

class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    original_filepath = Column(String, nullable=False)
    current_filepath = Column(String, nullable=False)
    width_mm = Column(Float, default=100.0)
    height_mm = Column(Float, default=100.0)
    status = Column(String, default="UPLOADED") # UPLOADED, CLEAN, CUT_READY, ERROR
    checker_results = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)