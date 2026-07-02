
"""
optimize_router.py
~~~~~~~~~~~~~~~~~~
Exposes the following endpoints under /optimize:

  GET  /optimize/license          — initiate optimisation (returns request_id immediately)
  GET  /optimize/requests         — list all past requests
  GET  /optimize/results/{req_id} — fetch AI analysis rows for a request
  GET  /optimize/sim-results/{req_id} — fetch FUE simulation rows for a request
  GET  /optimize/license-types    — distinct license tiers available for a system
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logger import setup_logger
from app.models.database import get_db
from app.models.request_array import RequestArray
from app.models.Opt_results import LicenseOptimizationResult, create_opt_sim_result_model
from app.service.license_optimizer_service import (
    create_optimization_request_immediately,
    get_all_requests_service,
    get_distinct_license_types_service,
    process_optimization_in_background,
)

router = APIRouter(prefix="/optimize", tags=["License Optimization"])
logger = setup_logger("app_logger")


# ---------------------------------------------------------------------------
# GET /optimize/license  — start optimisation job
# ---------------------------------------------------------------------------
@router.get("/license")
async def optimize_license_endpoint(
    background_tasks: BackgroundTasks,
    system_id: str = Query(..., description="System identifier (e.g. 'S4H_PRD')"),
    target_license: str = Query(
        "GB Advanced Use",
        description="License tier to analyse (e.g. 'GB Advanced Use')",
    ),
    sap_system_info: str = Query(
        "S4 HANA OnPremise 1909",
        description="Free-text SAP system context passed to the AI",
    ),
    role_names: Optional[List[str]] = Query(
        None,
        description="Specific roles to analyse; omit to analyse all roles under target_license",
    ),
    ratio_threshold: Optional[int] = Query(
        None,
        description="Optional AGR_RATIO first-part ceiling filter",
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Initiates an AI-powered SAP role licence optimisation job.
    Returns immediately with a ``request_id``; processing continues in the background.
    Poll ``GET /optimize/results/{request_id}`` to retrieve results once the status
    shown by ``GET /optimize/requests`` changes to **COMPLETED**.
    """
    logger.info(
        f"Optimisation request received — system='{system_id}', "
        f"target_license='{target_license}', roles={role_names or 'ALL'}"
    )

    if not system_id:
        raise HTTPException(status_code=400, detail="system_id is required.")

    try:
        request_id = await create_optimization_request_immediately(db, system_id)
        logger.info(f"Request '{request_id}' created — queuing background task.")

        background_tasks.add_task(
            process_optimization_in_background,
            system_name      = system_id,
            request_id       = request_id,
            target_license   = target_license,
            sap_system_info  = sap_system_info,
            role_names       = role_names,
            ratio_threshold  = ratio_threshold,
        )

        return {
            "message":    "Optimisation request initiated successfully",
            "request_id": request_id,
            "status":     "IN_PROGRESS",
            "system_id":  system_id,
        }

    except Exception as exc:
        logger.error(f"Failed to initiate optimisation request: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate optimisation request: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /optimize/requests  — list all requests
# ---------------------------------------------------------------------------
@router.get("/requests")
async def get_all_requests(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns all optimisation requests ordered by most-recent first."""
    logger.info("Request received — list all optimisation requests.")
    try:
        requests = await get_all_requests_service(db)
        logger.info(f"Returning {len(requests)} request(s).")
        return [
            {
                "req_id":      r.req_id,
                "system_name": r.SYSTEM_NAME,
                "status":      r.STATUS,
                "timestamp":   r.TIMESTAMP.isoformat() if r.TIMESTAMP else None,
                "error_message": getattr(r, "ERROR_MESSAGE", None),
            }
            for r in requests
        ]
    except Exception as exc:
        logger.error(f"get_all_requests error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /optimize/results/{req_id}  — AI analysis rows
# ---------------------------------------------------------------------------
@router.get("/results/{req_id}")
def get_results_by_request_id(
    req_id: str,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns the per-auth-object AI analysis for a completed optimisation request.
    Includes enhanced fields: description, possibleValues, relevantTransactionCodes.
    """
    logger.info(f"Fetching AI results for req_id='{req_id}'.")
    try:
        rows = (
            db.query(LicenseOptimizationResult)
            .filter(LicenseOptimizationResult.REQ_ID == req_id)
            .all()
        )
        if not rows:
            logger.warning(f"No AI results found for req_id='{req_id}'.")
        else:
            logger.info(f"Found {len(rows)} AI result row(s) for req_id='{req_id}'.")

        return [
            {
                "result_id":               r.RESULT_ID,
                "req_id":                  r.REQ_ID,
                "role_id":                 r.ROLE_ID,
                "role_description":        r.ROLE_DESCRIPTION,
                "authorization_object":    r.AUTHORIZATION_OBJECT,
                "field":                   r.FIELD,
                "value":                   r.VALUE,
                "license_reducible":       r.LICENSE_REDUCIBLE,
                "suggested_role_license":  r.SUGGESTED_ROLE_LICENSE,
                "insights":                r.INSIGHTS,
                "recommendations":         r.RECOMMENDATIONS,
                "explanations":            r.EXPLANATIONS,
            }
            for r in rows
        ]

    except Exception as exc:
        logger.error(f"Error fetching results for req_id='{req_id}': {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# GET /optimize/sim-results/{req_id}  — FUE simulation rows
# ---------------------------------------------------------------------------
@router.get("/sim-results/{req_id}")
def get_sim_results_by_request_id(
    req_id: str,
    system_id: str = Query(..., description="System identifier used to resolve the sim-results table"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns per-role FUE simulation rows for fully-reducible roles in a request.
    ``system_id`` is required to locate the correct per-system simulation table.
    """
    logger.info(f"Fetching sim results for req_id='{req_id}', system='{system_id}'.")
    try:
        OptSimResult = create_opt_sim_result_model(system_id)

        rows = (
            db.query(OptSimResult)
            .filter(OptSimResult.REQUEST_ID == req_id)
            .all()
        )

        if not rows:
            logger.warning(f"No sim results found for req_id='{req_id}'.")
        else:
            logger.info(f"Found {len(rows)} sim result row(s) for req_id='{req_id}'.")

        return [
            {
                "sim_id":               r.SIM_ID,
                "request_id":           r.REQUEST_ID,
                "system_name":          r.SYSTEM_NAME,
                "reducible_roles":      r.REDUCIBLE_ROLES,
                "reducible_role_count": r.REDUCIBLE_ROLE_COUNT,
                # --- before ---
                "before_gb_users":      r.BEFORE_GB_USERS,
                "before_gc_users":      r.BEFORE_GC_USERS,
                "before_gd_users":      r.BEFORE_GD_USERS,
                "before_nc_users":      r.BEFORE_NC_USERS,
                "before_total_fue":     r.BEFORE_TOTAL_FUE,
                # --- after ---
                "after_gb_users":       r.AFTER_GB_USERS,
                "after_gc_users":       r.AFTER_GC_USERS,
                "after_gd_users":       r.AFTER_GD_USERS,
                "after_nc_users":       r.AFTER_NC_USERS,
                "after_total_fue":      r.AFTER_TOTAL_FUE,
                # --- impact ---
                "fue_saved":            r.FUE_SAVED,
                "users_impacted":       r.USERS_IMPACTED,
            }
            for r in rows
        ]

    except Exception as exc:
        logger.error(f"Error fetching sim results for req_id='{req_id}': {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# GET /optimize/license-types  — distinct license tiers
# ---------------------------------------------------------------------------
@router.get("/license-types")
async def get_license_types_endpoint(
    system_id: str = Query(..., description="System identifier"),
    db: Session = Depends(get_db),
) -> List[Dict[str, str]]:
    """
    Returns distinct license classification values available for ``system_id``.
    Requires role-license data to have been loaded first.
    """
    logger.info(f"License-types requested for system='{system_id}'.")
    if not system_id:
        raise HTTPException(status_code=400, detail="system_id is required.")
    try:
        licenses = await get_distinct_license_types_service(db, system_id)
        logger.info(f"Returning {len(licenses)} license type(s) for system='{system_id}'.")
        return licenses
    except Exception as exc:
        logger.error(f"Error fetching license types for system='{system_id}': {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")