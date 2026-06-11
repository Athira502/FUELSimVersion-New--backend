from sqlalchemy import Column, String, Integer, Float, DateTime, func
from app.models.database import Base

class FUEHistory(Base):
    __tablename__ = "Z_FUE_HISTORY"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    SYSTEM_NAME  = Column(String, nullable=False, index=True)
    SNAPSHOT_DATE = Column(DateTime, default=func.now(), nullable=False)
    YEAR_MONTH   = Column(String(7), nullable=False)  # e.g. "2026-06"
    GB_USERS     = Column(Integer, default=0)
    GC_USERS     = Column(Integer, default=0)
    GD_USERS     = Column(Integer, default=0)
    NC_USERS     = Column(Integer, default=0)
    TOTAL_USERS  = Column(Integer, default=0)
    GB_FUE       = Column(Float, default=0)
    GC_FUE       = Column(Float, default=0)
    GD_FUE       = Column(Float, default=0)
    TOTAL_FUE    = Column(Float, default=0)