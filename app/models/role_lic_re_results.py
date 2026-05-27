from sqlalchemy import Column, String, Integer, ForeignKey, Float
from app.models.database import Base


class LicenseOptimizationResult(Base):
    __tablename__ = "Z_FUE_OPT_RESULTS"

    RESULT_ID = Column(Integer, primary_key=True, autoincrement=True)
    REQ_ID= Column(String, ForeignKey("Z_FUE_OPT_REQUESTS.req_id"), nullable=False)
    ROLE_ID= Column(String,nullable=False)
    ROLE_DESCRIPTION= Column(String,nullable=False)
    AUTHORIZATION_OBJECT=Column(String,nullable=False)
    FIELD=Column(String,nullable=False)
    VALUE=Column(String,nullable=False)
    LICENSE_REDUCIBLE=Column(String,nullable=False)
    INSIGHTS=Column(String,nullable=False)
    RECOMMENDATIONS=Column(String)
    EXPLANATIONS=Column(String)

class _OptSimResult:
    """
    One row per reducible role — simulated FUE impact after AI-suggested reductions.
    """
    RESULT_ID = Column(Integer, primary_key=True, autoincrement=True)
    REQUEST_ID            = Column(String, index=True)
    AGR_NAME              = Column(String, nullable=False, index=True)
    ORIGINAL_ROLE_LICENSE = Column(String)
    SIMULATED_ROLE_LICENSE= Column(String)
    REDUCIBILITY          = Column(String)   # 'Full' | 'Partial'
    USERS_AFFECTED        = Column(Integer)
    ORIGINAL_FUE          = Column(Float)
    SIMULATED_FUE         = Column(Float)
    FUE_SAVED             = Column(Float)