"""
opt_results.py
~~~~~~~~~~~~~~
Two tables per optimisation run:

  Z_FUE_OPT_RESULTS          (static, shared)
    One row per (role, auth-object, field) returned by the AI.

  Z_FUE_{SYSTEM}_OPT_SIM_RESULT  (dynamic, per-system)
    One summary row per request — system-wide FUE before/after the AI
    suggestions are applied, plus per-tier user counts.
"""

import re

from sqlalchemy import Column, String, Integer, Float, ForeignKey
from app.models.database import Base, engine
from app.core.logger import setup_logger

logger = setup_logger("app_logger")


# ---------------------------------------------------------------------------
# Static: AI analysis result rows
# ---------------------------------------------------------------------------

class LicenseOptimizationResult(Base):
    """
    One row per (role, auth-object, field) tuple returned by the AI.
    LICENSE_REDUCIBLE values: 'Yes' | 'No' | 'May Be'
    SUGGESTED_ROLE_LICENSE: role-level license suggested by AI (one per role,
        duplicated across every row for that role for easy querying).
    """
    __tablename__ = "Z_FUE_OPT_RESULTS"

    RESULT_ID              = Column(Integer, primary_key=True, autoincrement=True)
    REQ_ID                 = Column(String, ForeignKey("Z_FUE_OPT_REQUESTS.req_id"), nullable=False)
    ROLE_ID                = Column(String, nullable=False)
    ROLE_DESCRIPTION       = Column(String, nullable=False)
    AUTHORIZATION_OBJECT   = Column(String, nullable=False)
    FIELD                  = Column(String, nullable=False)
    VALUE                  = Column(String, nullable=False)
    LICENSE_REDUCIBLE      = Column(String, nullable=False)   # Yes | No | May Be
    SUGGESTED_ROLE_LICENSE = Column(String)                   # AI role-level suggestion
    INSIGHTS               = Column(String, nullable=False)
    RECOMMENDATIONS        = Column(String)
    EXPLANATIONS           = Column(String)


# ---------------------------------------------------------------------------
# Dynamic: per-system simulation summary
# ---------------------------------------------------------------------------

def _clean(name: str) -> str:
    return re.sub(r'\W+', '', name.replace(' ', '_')).upper()


def get_opt_sim_result_tablename(system_name: str) -> str:
    return f"Z_FUE_{_clean(system_name)}_OPT_SIM_RESULT"


class _OptSimResult:
    """
    One row per request — system-wide FUE simulation summary.

    BEFORE columns reflect the current state (all roles at their existing
    RoleLicSummary license).

    AFTER columns reflect the simulated state where reducible roles have
    been switched to the AI-suggested license; all other roles stay the same.

    User's final license = most-restrictive license across all their roles.
    """
    SIM_ID = Column(Integer, primary_key=True, autoincrement=True)

    # ---- identity ----
    REQUEST_ID  = Column(String, index=True, nullable=False)
    SYSTEM_NAME = Column(String, nullable=False)

    # ---- roles changed ----
    REDUCIBLE_ROLES      = Column(String)   # comma-separated list of reduced role names
    REDUCIBLE_ROLE_COUNT = Column(Integer)  # how many roles were reduced

    # ---- system-wide user counts BEFORE optimisation ----
    BEFORE_GB_USERS = Column(Integer)   # users whose final license = GB Advanced Use
    BEFORE_GC_USERS = Column(Integer)   # users whose final license = GC Core Use
    BEFORE_GD_USERS = Column(Integer)   # users whose final license = GD Self-Service Use
    BEFORE_NC_USERS = Column(Integer)   # users Not Classified
    BEFORE_TOTAL_FUE = Column(Float)    # sum of FUE weights across all users

    # ---- system-wide user counts AFTER optimisation ----
    AFTER_GB_USERS  = Column(Integer)
    AFTER_GC_USERS  = Column(Integer)
    AFTER_GD_USERS  = Column(Integer)
    AFTER_NC_USERS  = Column(Integer)
    AFTER_TOTAL_FUE = Column(Float)

    # ---- impact ----
    FUE_SAVED       = Column(Float)     # BEFORE_TOTAL_FUE - AFTER_TOTAL_FUE
    USERS_IMPACTED  = Column(Integer)   # users whose license tier actually changed


_sim_cache: dict = {}


def create_opt_sim_result_model(system_name: str):
    """Returns (and caches) the dynamic ORM model for the per-system sim table."""
    table_name = get_opt_sim_result_tablename(system_name)
    if table_name in _sim_cache:
        return _sim_cache[table_name]

    logger.info(f"Creating OptSimResult model for '{table_name}'.")
    model = type(
        f"Z_FUE_{_clean(system_name)}OptSimResult",
        (_OptSimResult, Base),
        {"__tablename__": table_name, "__table_args__": {"extend_existing": True}},
    )
    _sim_cache[table_name] = model
    return model