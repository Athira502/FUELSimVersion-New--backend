import math
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.logger import setup_logger
from app.models.database import get_db, SessionLocal
from app.models.dynamic_models import (
    create_role_lic_sim_model,
    create_simulation_result_model,
    create_role_lic_model,
    create_role_lic_summary_model,
    create_user_lic_summary_model,
    ensure_table_exists, create_AGRUSERS_model, create_USR02_model
)
from pydantic import BaseModel

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation"]
)

logger = setup_logger("app_logger")


# Pydantic schemas
class SimulationChangePayload(BaseModel):
    role_name: str
    role_description: str
    object: str
    field: str
    value_low: str
    value_high: str
    action: str  # 'Add', 'Change', 'Remove'
    original_license: str
    new_value_low : Optional[str] = None  # For 'Change' operations
    new_value_high:Optional[str] = None

class SimulationRequest(BaseModel):
    """Wrapper for simulation changes request"""
    changes: List[SimulationChangePayload]


LICENSE_PRIORITY = {
    'GB Advanced Use': 1,
    'GC Core Use': 2,
    'GD Self-Service Use': 3,
    'Not Classified': 999,
}

FUE_FACTORS = {
    'GB Advanced Use': 1.0,
    'GC Core Use': 0.2,
    'GD Self-Service Use': 0.0333,
    'Not Classified': 0.0,
}


# ════════════════════════════════════════════════════════════════════════════
# Initialization: Create and populate simulation table
# ════════════════════════════════════════════════════════════════════════════

# @router.post("/{system_name}/initialize")
# async def initialize_simulation_table(
#         system_name: str,
#         db: Session = Depends(get_db)
# ):
#     """
#     Create simulation table and populate it with current RoleLic data.
#     Call this before running any simulations.
#     """
#     logger.info(f"Initializing simulation table for system '{system_name}'")
#
#     try:
#         # Get models
#         RoleLicModel = create_role_lic_model(system_name)
#         RoleLicSimModel = create_role_lic_sim_model(system_name)
#
#         # Ensure tables exist
#         ensure_table_exists(db.bind, RoleLicModel)
#         ensure_table_exists(db.bind, RoleLicSimModel)
#
#         # Clear existing simulation data
#         deleted_count = db.query(RoleLicSimModel).delete()
#         logger.info(f"Cleared {deleted_count} existing simulation records")
#
#         # Copy all RoleLic data to simulation table
#         source_records = db.query(RoleLicModel).all()
#
#         if not source_records:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"No RoleLic data found for system '{system_name}'. Run Stage 2 computation first."
#             )
#
#         sim_records = []
#         for record in source_records:
#             sim_record = RoleLicSimModel(
#                 AGR_NAME=record.AGR_NAME,
#                 OBJECT=record.OBJECT,
#                 FIELD=record.FIELD,
#                 LOW=record.LOW,
#                 HIGH=record.HIGH,
#                 ORIGINAL_CLASSIFY_LIC=record.CLASSIFY_LIC,
#                 ORIGINAL_MATCH_TYPE=record.MATCH_TYPE,
#                 OPERATION=None,  # No changes yet
#                 NEW_LOW=record.LOW,  # Start with original values
#                 NEW_HIGH=record.HIGH,
#                 SIM_CLASSIFY_LIC=record.CLASSIFY_LIC,  # Start with original license
#                 SIM_MATCH_TYPE=record.MATCH_TYPE
#             )
#             sim_records.append(sim_record)
#
#         db.bulk_save_objects(sim_records)
#         db.commit()
#
#         logger.info(f"Initialized simulation table with {len(sim_records)} records")
#
#         return {
#             "status": "success",
#             "message": f"Simulation table initialized with {len(sim_records)} records",
#             "records_copied": len(sim_records)
#         }
#
#     except Exception as e:
#         db.rollback()
#         logger.error(f"Error initializing simulation table: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))


@router.post("/{system_name}/initialize")
async def initialize_simulation_table(system_name: str, db: Session = Depends(get_db)):
    RoleLicModel = create_role_lic_model(system_name)  # Stage 2
    RoleLicSummaryModel = create_role_lic_summary_model(system_name)  # Stage 3
    RoleLicSimModel = create_role_lic_sim_model(system_name)

    ensure_table_exists(db.bind, RoleLicModel)
    ensure_table_exists(db.bind, RoleLicSimModel)

    deleted_count = db.query(RoleLicSimModel).delete()

    source_records = db.query(RoleLicModel).all()

    # Get Stage 3 summary to cross-check role-level license
    summary_records = {r.AGR_NAME: r for r in db.query(RoleLicSummaryModel).all()}

    sim_records = []
    for record in source_records:
        # Use Stage 3 role-level license as the sim baseline
        # This matches what the dashboard uses
        role_summary = summary_records.get(record.AGR_NAME)

        # Only include roles that exist in Stage 3 summary
        # (excludes roles with no valid license classification)
        if not role_summary:
            continue

        sim_record = RoleLicSimModel(
            AGR_NAME=record.AGR_NAME,
            OBJECT=record.OBJECT,
            FIELD=record.FIELD,
            LOW=record.LOW,
            HIGH=record.HIGH,
            ORIGINAL_CLASSIFY_LIC=record.CLASSIFY_LIC,
            ORIGINAL_MATCH_TYPE=record.MATCH_TYPE,
            OPERATION=None,
            NEW_LOW=record.LOW,
            NEW_HIGH=record.HIGH,
            SIM_CLASSIFY_LIC=record.CLASSIFY_LIC,
            SIM_MATCH_TYPE=record.MATCH_TYPE
        )
        sim_records.append(sim_record)

    db.bulk_save_objects(sim_records)
    db.commit()

    return {
        "status": "success",
        "records_copied": len(sim_records),
        "roles_excluded": len(source_records) - len(sim_records)
    }




# ════════════════════════════════════════════════════════════════════════════
# Get role details for simulation UI
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/roles")
async def get_simulation_roles(
        system_name: str,
        db: Session = Depends(get_db)
):
    """
    Get all roles with their current license classifications for simulation UI.
    """
    logger.info(f"Fetching simulation role list for system '{system_name}'")

    try:
        RoleLicSimModel = create_role_lic_sim_model(system_name)
        RoleLicSummaryModel = create_role_lic_summary_model(system_name)

        # Get role summaries with object counts
        query = text(f"""
            SELECT 
                rls."AGR_NAME",
                rls."TEXT",
                rls."CLASSIFY_LIC",
                rls."TOTAL_OBJ",
                rls."GB_COUNT",
                rls."GC_COUNT",
                rls."GD_COUNT",
                rls."NC_COUNT"
            FROM "{RoleLicSummaryModel.__tablename__}" rls
            ORDER BY rls."AGR_NAME"
        """)

        results = db.execute(query).fetchall()

        return [
            {
                "role_name": row[0],
                "description": row[1],
                "current_license": row[2],
                "total_objects": row[3],
                "gb_count": row[4],
                "gc_count": row[5],
                "gd_count": row[6],
                "nc_count": row[7]
            }
            for row in results
        ]

    except Exception as e:
        logger.error(f"Error fetching simulation roles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{system_name}/roles/{role_name}/details")
async def get_role_simulation_details(
        system_name: str,
        role_name: str,
        db: Session = Depends(get_db)
):
    """
    Get detailed authorization objects for a specific role in simulation context.
    """
    logger.info(f"Fetching simulation details for role '{role_name}' in system '{system_name}'")

    try:
        RoleLicSimModel = create_role_lic_sim_model(system_name)

        records = db.query(RoleLicSimModel).filter(
            RoleLicSimModel.AGR_NAME == role_name
        ).order_by(RoleLicSimModel.OBJECT, RoleLicSimModel.FIELD).all()

        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"Role '{role_name}' not found in simulation table"
            )

        return {
            "role_name": role_name,
            "auth_objects": [
                {
                    "object": rec.OBJECT,
                    "field": rec.FIELD,
                    "value_low": rec.NEW_LOW or rec.LOW,
                    "value_high": rec.NEW_HIGH or rec.HIGH,
                    "original_license": rec.ORIGINAL_CLASSIFY_LIC,
                    "current_license": rec.SIM_CLASSIFY_LIC,
                    "operation": rec.OPERATION,
                    "match_type": rec.SIM_MATCH_TYPE
                }
                for rec in records
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching role details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# Apply simulation changes
# ════════════════════════════════════════════════════════════════════════════

def get_next_simulation_id(db: Session, SimResultModel) -> str:
    """Generate next simulation run ID"""
    logger.debug(f"Generating next simulation ID")

    try:
        latest = db.query(SimResultModel.SIMULATION_RUN_ID).filter(
            SimResultModel.SIMULATION_RUN_ID.like('SIM%')
        ).order_by(SimResultModel.SIMULATION_RUN_ID.desc()).first()

        if latest and latest[0].startswith('SIM'):
            try:
                current_num = int(latest[0][3:], 16)  # Parse hex
                next_num = current_num + 1
                return f"SIM{next_num:08X}"
            except ValueError:
                pass

        return f"SIM{100000:08X}"

    except Exception as e:
        logger.error(f"Error generating simulation ID: {e}")
        return f"SIM{100000:08X}"


@router.post("/{system_name}/apply-changes")
async def apply_simulation_changes(
        system_name: str,
        request: SimulationRequest,  # ← Changed from List[SimulationChangePayload]
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    Apply simulation changes and calculate new FUE in background.
    """
    logger.info(f"Applying {len(request.changes)} simulation changes for system '{system_name}'")

    try:
        SimResultModel = create_simulation_result_model(system_name)
        ensure_table_exists(db.bind, SimResultModel)

        # Generate simulation run ID
        sim_id = get_next_simulation_id(db, SimResultModel)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create initial result records
        for change in request.changes:
            record = SimResultModel(
                SIMULATION_RUN_ID=sim_id,
                TIMESTAMP=timestamp,
                STATUS="In Progress",
                SYSTEM_NAME=system_name,
                ROLE_NAME=change.role_name,
                ROLE_DESCRIPTION=change.role_description,
                OBJECT=change.object,
                FIELD=change.field,
                VALUE_LOW=change.value_low,
                VALUE_HIGH=change.value_high,
                OPERATION=change.action,
                PREV_LICENSE=change.original_license,
                CURRENT_LICENSE=None  # Will be updated
            )
            db.add(record)

        db.commit()
        logger.info(f"Created {len(request.changes)} initial result records for simulation '{sim_id}'")

        # Process changes in background
        background_tasks.add_task(
            process_simulation_sync,
            system_name, sim_id, request.changes
        )

        return {
            "simulation_run_id": sim_id,
            "status": "In Progress",
            "timestamp": timestamp,
            "changes_count": len(request.changes),
            "roles_affected": len({c.role_name for c in request.changes})
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error applying simulation changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# Background Processing (No changes needed here)
# ════════════════════════════════════════════════════════════════════════════

def process_simulation_sync(
        system_name: str,
        sim_id: str,
        changes: List[SimulationChangePayload]
):
    """Synchronous wrapper for background processing"""
    import asyncio
    logger.info(f"Starting background simulation processing for '{sim_id}'")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            process_simulation_background(system_name, sim_id, changes)
        )
    except Exception as e:
        logger.error(f"Error in background simulation: {e}", exc_info=True)
    finally:
        try:
            loop.close()
        except:
            pass


async def process_simulation_background(
        system_name: str,
        sim_id: str,
        changes: List[SimulationChangePayload]
):
    """
    Background task: apply changes to simulation table and recalculate FUE.
    """
    db = SessionLocal()

    try:
        logger.info(f"Processing simulation '{sim_id}' for system '{system_name}'")

        RoleLicSimModel = create_role_lic_sim_model(system_name)
        SimResultModel = create_simulation_result_model(system_name)

        from app.models.client_sys_release_version import ruleSet
        RuleSetModel = ruleSet

        # Build ruleset lookup (same as Stage 2)
        ruleset_map = defaultdict(list)
        for rule in db.query(RuleSetModel).all():
            step = LICENSE_PRIORITY.get(rule.RULE_DESCRIPTION, 999)
            ruleset_map[(rule.AUTHOBJECT, rule.AUTHFIELD)].append({
                'step': step,
                'license': rule.RULE_DESCRIPTION,
                'authvalue': rule.AUTHVALUE,
            })

        # Apply each change to simulation table
        for change in changes:
            # Find the record(s) to modify
            records = db.query(RoleLicSimModel).filter(
                RoleLicSimModel.AGR_NAME == change.role_name,
                RoleLicSimModel.OBJECT == change.object,
                RoleLicSimModel.FIELD == change.field,
                RoleLicSimModel.LOW == change.value_low
            ).all()

            if change.action == "Add":
                # Add new authorization value
                new_record = RoleLicSimModel(
                    AGR_NAME=change.role_name,
                    OBJECT=change.object,
                    FIELD=change.field,
                    LOW=change.new_value_low or change.value_low,
                    HIGH=change.new_value_high or change.value_high,
                    ORIGINAL_CLASSIFY_LIC='Not Classified',
                    ORIGINAL_MATCH_TYPE='No Match',
                    OPERATION='Add',
                    NEW_LOW=change.new_value_low or change.value_low,
                    NEW_HIGH=change.new_value_high or change.value_high,
                    SIM_CLASSIFY_LIC=None,
                    SIM_MATCH_TYPE=None
                )

                # Recalculate license for new record
                new_lic, new_match = recalculate_license(
                    new_record.OBJECT,
                    new_record.FIELD,
                    new_record.NEW_LOW,
                    new_record.NEW_HIGH,
                    ruleset_map
                )
                new_record.SIM_CLASSIFY_LIC = new_lic
                new_record.SIM_MATCH_TYPE = new_match

                db.add(new_record)

            elif change.action == "Change":
                # Modify existing authorization value
                for rec in records:
                    rec.OPERATION = 'Change'
                    rec.NEW_LOW = change.new_value_low or rec.LOW
                    rec.NEW_HIGH = change.new_value_high or rec.HIGH

                    # Recalculate license
                    new_lic, new_match = recalculate_license(
                        rec.OBJECT,
                        rec.FIELD,
                        rec.NEW_LOW,
                        rec.NEW_HIGH,
                        ruleset_map
                    )
                    rec.SIM_CLASSIFY_LIC = new_lic
                    rec.SIM_MATCH_TYPE = new_match

            elif change.action == "Remove":
                # Mark as removed
                for rec in records:
                    rec.OPERATION = 'Remove'
                    rec.SIM_CLASSIFY_LIC = 'Not Classified'
                    rec.SIM_MATCH_TYPE = 'No Match'

        db.commit()
        logger.info(f"Applied all changes to simulation table for '{sim_id}'")

        # Recalculate FUE summary
        fue_results = await calculate_simulation_fue(system_name, db)

        # Update result records with final licenses and FUE
        for change in changes:
            # Get the most restrictive license for this role after simulation
            role_licenses = db.query(RoleLicSimModel).filter(
                RoleLicSimModel.AGR_NAME == change.role_name,
                RoleLicSimModel.OPERATION != 'Remove'
            ).all()

            if role_licenses:
                final_license = min(
                    [r.SIM_CLASSIFY_LIC for r in role_licenses],
                    key=lambda x: LICENSE_PRIORITY.get(x, 999)
                )
            else:
                final_license = 'Not Classified'

            # Update result record
            db.query(SimResultModel).filter(
                SimResultModel.SIMULATION_RUN_ID == sim_id,
                SimResultModel.ROLE_NAME == change.role_name,
                SimResultModel.OBJECT == change.object,
                SimResultModel.FIELD == change.field,
                SimResultModel.VALUE_LOW == change.value_low,
                SimResultModel.STATUS == "In Progress"
            ).update({
                "STATUS": "Completed",
                "CURRENT_LICENSE": final_license,
                "TOTAL_FUE": str(fue_results['total_fue']),
                "GB_FUE": str(fue_results['gb_fue']),
                "GC_FUE": str(fue_results['gc_fue']),
                "GD_FUE": str(fue_results['gd_fue']),
                "TIMESTAMP": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        db.commit()
        logger.info(f"Simulation '{sim_id}' completed successfully")

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing simulation '{sim_id}': {e}", exc_info=True)

        # Mark all as failed
        try:
            db.query(SimResultModel).filter(
                SimResultModel.SIMULATION_RUN_ID == sim_id,
                SimResultModel.STATUS == "In Progress"
            ).update({
                "STATUS": "Failed",
                "TIMESTAMP": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update error status: {update_error}")

    finally:
        db.close()


def recalculate_license(
        auth_object: str,
        auth_field: str,
        value_low: str,
        value_high: str,
        ruleset_map: dict
) -> Tuple[str, str]:
    """
    Recalculate license classification for a single authorization value.
    Uses same logic as Stage 2 compute_rolelic.
    """
    candidate_rules = ruleset_map.get((auth_object, auth_field), [])
    matched = []

    for rule in candidate_rules:
        match_type = evaluate_match(rule['authvalue'], value_low, value_high)
        if match_type is not None:
            matched.append((rule['step'], rule['license'], match_type))

    if matched:
        best = min(matched, key=lambda x: x[0])
        return best[1], best[2]  # license, match_type
    else:
        return 'Not Classified', 'No Match'


def evaluate_match(authvalue: str, low: str, high: str) -> str:
    """Match evaluation logic from Stage 2"""
    if not authvalue:
        return None

    if authvalue == '*':
        return 'Rule Wildcard'

    if low == '*':
        return 'Role Wildcard'

    # No range — exact match only
    if not high or high.strip() == '':
        if low == authvalue:
            return 'Exact Match'
        return None

    # Range match
    if low <= authvalue <= high:
        return 'Range Match'

    return None


# async def calculate_simulation_fue(system_name: str, db: Session) -> Dict[str, Any]:
#     """
#     Calculate FUE based on simulation table.
#     MUST match Stage 5 logic including locked user handling!
#     """
#     logger.info(f"=== STARTING FUE CALCULATION for {system_name} ===")
#
#     try:
#         from sqlalchemy import or_
#         from collections import defaultdict
#
#         RoleLicSimModel = create_role_lic_sim_model(system_name)
#         AGRUsersModel = create_AGRUSERS_model(system_name)
#         USR02Model = create_USR02_model(system_name)  # ← Need this!
#
#         # STEP 1: Get most restrictive license PER ROLE
#         logger.info("STEP 1: Getting most restrictive license per role...")
#
#         sim_records = db.query(RoleLicSimModel).filter(
#             or_(
#                 RoleLicSimModel.OPERATION.is_(None),
#                 RoleLicSimModel.OPERATION != 'Remove'
#             )
#         ).all()
#
#         logger.info(f"Active simulation records: {len(sim_records)}")
#
#         # Group by role and get most restrictive license per role
#         role_licenses = defaultdict(list)
#         for rec in sim_records:
#             if rec.SIM_CLASSIFY_LIC:
#                 role_licenses[rec.AGR_NAME].append(rec.SIM_CLASSIFY_LIC)
#
#         logger.info(f"Unique roles in simulation: {len(role_licenses)}")
#
#         # Get most restrictive license per role
#         role_final_licenses = {}
#         for role, licenses in role_licenses.items():
#             role_final_licenses[role] = min(
#                 licenses,
#                 key=lambda x: LICENSE_PRIORITY.get(x, 999)
#             )
#
#         role_lic_dist = defaultdict(int)
#         for lic in role_final_licenses.values():
#             role_lic_dist[lic] += 1
#         logger.info(f"Role license distribution: {dict(role_lic_dist)}")
#
#         # STEP 2: Map roles to USERS
#         logger.info("STEP 2: Mapping roles to users...")
#
#         user_role_mappings = db.query(AGRUsersModel).all()
#         logger.info(f"Total user-role mappings: {len(user_role_mappings)}")
#
#         if not user_role_mappings:
#             raise Exception("No user-role mappings found")
#
#         # Build user license groups
#         user_licenses = defaultdict(list)
#         for mapping in user_role_mappings:
#             role_license = role_final_licenses.get(
#                 mapping.AGR_NAME,
#                 'Not Classified'
#             )
#             user_licenses[mapping.UNAME].append(role_license)
#
#         logger.info(f"Total users with licenses: {len(user_licenses)}")
#
#         # STEP 3: Build USR02 lookup for locked users
#         logger.info("STEP 3: Checking for locked users...")
#
#         usr02_map = {row.BNAME: row for row in db.query(USR02Model).all()}
#         logger.info(f"USR02 records loaded: {len(usr02_map)}")
#
#         # STEP 4: Get most restrictive license PER USER + apply locked override
#         logger.info("STEP 4: Calculating final user licenses with locked override...")
#
#         license_counts = defaultdict(int)
#         locked_count = 0
#
#         for user, licenses in user_licenses.items():
#             # Get most restrictive license for this user
#             final_lic = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))
#
#             # Apply locked user override (matches Stage 5 logic!)
#             usr = usr02_map.get(user)
#             if usr:
#                 uflag = str(usr.UFLAG).strip() if usr.UFLAG is not None else None
#                 locked = uflag not in ('0', '128', None)
#
#                 if locked:
#                     final_lic = 'Not Classified'  # Override!
#                     locked_count += 1
#
#             license_counts[final_lic] += 1
#
#         logger.info(f"Locked users downgraded to NC: {locked_count}")
#         logger.info(f"User license counts (after locked override): {dict(license_counts)}")
#
#         # STEP 5: Calculate FUE
#         gb_count = license_counts.get('GB Advanced Use', 0)
#         gc_count = license_counts.get('GC Core Use', 0)
#         gd_count = license_counts.get('GD Self-Service Use', 0)
#         nc_count = license_counts.get('Not Classified', 0)
#
#         logger.info(f"Final counts: GB={gb_count}, GC={gc_count}, GD={gd_count}, NC={nc_count}")
#
#         gb_fue = math.ceil(gb_count * FUE_FACTORS['GB Advanced Use'])
#         gc_fue = math.ceil(gc_count * FUE_FACTORS['GC Core Use'])
#         gd_fue = math.ceil(gd_count * FUE_FACTORS['GD Self-Service Use'])
#
#         total_fue = gb_fue + gc_fue + gd_fue
#
#         logger.info(f"=== FINAL FUE ===")
#         logger.info(f"GB: {gb_count} USERS × 1.0 = {gb_fue} FUE")
#         logger.info(f"GC: {gc_count} USERS × 0.2 = {gc_fue} FUE")
#         logger.info(f"GD: {gd_count} USERS × 0.0333 = {gd_fue} FUE")
#         logger.info(f"TOTAL: {total_fue} FUE")
#         logger.info(f"LOCKED: {locked_count} users downgraded to NC")
#
#         return {
#             'total_fue': total_fue,
#             'gb_fue': gb_fue,
#             'gc_fue': gc_fue,
#             'gd_fue': gd_fue,
#             'gb_count': gb_count,
#             'gc_count': gc_count,
#             'gd_count': gd_count,
#             'nc_count': nc_count,
#             'locked_count': locked_count
#         }
#
#     except Exception as e:
#         logger.error(f"ERROR in calculate_simulation_fue: {e}", exc_info=True)
#         raise


async def calculate_simulation_fue(system_name: str, db: Session) -> Dict[str, Any]:
    from sqlalchemy import or_
    from collections import defaultdict
    from datetime import date, datetime
    from typing import Optional

    logger.info(f"=== STARTING FUE CALCULATION for {system_name} ===")

    # ── copy _parse_date from Stage 5 exactly ──────────────────────────────
    def _parse_date(date_str):
        if not date_str:
            return None
        s = str(date_str).strip()
        if s in ('', '00000000', '0000-00-00', '00-00-0000'):
            return None
        if '9999' in s:
            return None
        for fmt in ('%d-%m-%Y', '%Y%m%d', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    today = date.today()

    RoleLicSimModel = create_role_lic_sim_model(system_name)
    AGRUsersModel = create_AGRUSERS_model(system_name)
    USR02Model = create_USR02_model(system_name)

    # STEP 1: most restrictive license per role (excluding Removed rows)
    sim_records = db.query(RoleLicSimModel).filter(
        or_(
            RoleLicSimModel.OPERATION.is_(None),
            RoleLicSimModel.OPERATION != 'Remove'
        )
    ).all()

    role_licenses = defaultdict(list)
    for rec in sim_records:
        if rec.SIM_CLASSIFY_LIC:
            role_licenses[rec.AGR_NAME].append(rec.SIM_CLASSIFY_LIC)

    role_final_licenses = {}
    for role, licenses in role_licenses.items():
        role_final_licenses[role] = min(
            licenses,
            key=lambda x: LICENSE_PRIORITY.get(x, 999)
        )

    # STEP 2: map roles → users
    user_role_mappings = db.query(AGRUsersModel).all()
    if not user_role_mappings:
        raise Exception("No user-role mappings found")

    user_licenses = defaultdict(list)
    for mapping in user_role_mappings:
        role_license = role_final_licenses.get(mapping.AGR_NAME, 'Not Classified')
        user_licenses[mapping.UNAME].append(role_license)

    # STEP 3: USR02 lookup
    usr02_map = {row.BNAME: row for row in db.query(USR02Model).all()}

    # STEP 4: per-user final license — EXACT Stage 5 logic
    license_counts = defaultdict(int)
    locked_and_expired_count = 0

    for uname, licenses in user_licenses.items():
        final_lic = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))

        usr = usr02_map.get(uname)
        if usr:
            # ── Locked check (Stage 5 style: integer, only 0 = active) ──
            # uflag_raw = str(usr.UFLAG).strip() if usr.UFLAG is not None else None
            # try:
            #     uflag_int = int(float(uflag_raw)) if uflag_raw is not None else 0
            # except (ValueError, TypeError):
            #     uflag_int = 0
            # locked = uflag_int != 0
            #
            # # ── Expiry check (Stage 5 style) ──
            # gltgb_date = _parse_date(usr.GLTGB)
            # expired = (gltgb_date is not None) and (gltgb_date < today)
            #
            # # ── Override: ONLY downgrade if BOTH expired AND locked ──
            # if expired and locked:
            #     final_lic = 'Not Classified'
            #     locked_and_expired_count += 1
            uflag_raw = str(usr.UFLAG).strip() if usr.UFLAG is not None else None
            try:
                uflag_int = int(float(uflag_raw)) if uflag_raw is not None else 0
            except (ValueError, TypeError):
                uflag_int = 0
            locked = (uflag_int != 0) and (uflag_int != 128)  # ← FIX: exclude 128

            # ── Expiry check ──
            gltgb_date = _parse_date(usr.GLTGB)
            expired = (gltgb_date is not None) and (gltgb_date < today)

            # ── Override only when BOTH ──
            if expired and locked:
                final_lic = 'Not Classified'
                locked_and_expired_count += 1

        license_counts[final_lic] += 1

    # STEP 5: FUE calculation
    gb_count = license_counts.get('GB Advanced Use', 0)
    gc_count = license_counts.get('GC Core Use', 0)
    gd_count = license_counts.get('GD Self-Service Use', 0)
    nc_count = license_counts.get('Not Classified', 0)

    gb_fue = math.ceil(gb_count * FUE_FACTORS['GB Advanced Use'])
    gc_fue = math.ceil(gc_count * FUE_FACTORS['GC Core Use'])
    gd_fue = math.ceil(gd_count * FUE_FACTORS['GD Self-Service Use'])
    total_fue = gb_fue + gc_fue + gd_fue

    logger.info(f"GB={gb_count}→{gb_fue} FUE, GC={gc_count}→{gc_fue} FUE, GD={gd_count}→{gd_fue} FUE")
    logger.info(f"TOTAL={total_fue}, expired+locked downgraded={locked_and_expired_count}")

    return {
        'total_fue': total_fue,
        'gb_fue': gb_fue, 'gc_fue': gc_fue, 'gd_fue': gd_fue,
        'gb_count': gb_count, 'gc_count': gc_count,
        'gd_count': gd_count, 'nc_count': nc_count,
        'locked_count': locked_and_expired_count
    }



@router.get("/{system_name}/debug/user-role-mappings")
async def debug_user_role_mappings(
        system_name: str,
        db: Session = Depends(get_db)
):
    """Debug: Check user-role mapping table"""
    try:
        # FIXED: Use AGRUSERS model
        from app.models.dynamic_models import create_AGRUSERS_model
        AGRUsersModel = create_AGRUSERS_model(system_name)

        table_name = AGRUsersModel.__tablename__
        total_count = db.query(AGRUsersModel).count()

        unique_users = set()
        unique_roles = set()

        all_mappings = db.query(AGRUsersModel).all()
        for mapping in all_mappings:
            unique_users.add(mapping.UNAME)
            unique_roles.add(mapping.AGR_NAME)

        sample_records = db.query(AGRUsersModel).limit(10).all()

        return {
            "table_name": table_name,
            "total_mappings": total_count,
            "unique_users": len(unique_users),
            "unique_roles": len(unique_roles),
            "sample": [
                {
                    "user": rec.UNAME,
                    "role": rec.AGR_NAME
                }
                for rec in sample_records
            ]
        }
    except Exception as e:
        logger.error(f"Error in debug: {e}", exc_info=True)
        return {"error": str(e), "traceback": traceback.format_exc()}
# ════════════════════════════════════════════════════════════════════════════
# Get simulation results
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/results")
async def get_simulation_results(
        system_name: str,
        db: Session = Depends(get_db)
):
    """
    Get all simulation run results for a system.
    """
    logger.info(f"Fetching simulation results for system '{system_name}'")

    try:
        SimResultModel = create_simulation_result_model(system_name)

        results = db.query(SimResultModel).order_by(
            SimResultModel.TIMESTAMP.desc(),
            SimResultModel.SIMULATION_RUN_ID.desc()
        ).all()

        if not results:
            return {
                "message": "No simulation results found",
                "system_name": system_name,
                "results": []
            }

        # Group by simulation run ID
        simulation_runs = {}
        for result in results:
            sim_id = result.SIMULATION_RUN_ID
            if sim_id not in simulation_runs:
                simulation_runs[sim_id] = {
                    "simulation_run_id": sim_id,
                    "timestamp": result.TIMESTAMP,
                    "status": result.STATUS,
                    "total_fue": result.TOTAL_FUE,
                    "gb_fue": result.GB_FUE,
                    "gc_fue": result.GC_FUE,
                    "gd_fue": result.GD_FUE,
                    "changes": []
                }

            # Update status to most severe
            current_status = simulation_runs[sim_id]["status"]
            new_status = result.STATUS
            if (new_status == "Failed" or
                    (new_status == "In Progress" and current_status == "Completed")):
                simulation_runs[sim_id]["status"] = new_status

            simulation_runs[sim_id]["changes"].append({
                "role_name": result.ROLE_NAME,
                "role_description": result.ROLE_DESCRIPTION,
                "object": result.OBJECT,
                "field": result.FIELD,
                "value_low": result.VALUE_LOW,
                "value_high": result.VALUE_HIGH,
                "operation": result.OPERATION,
                "prev_license": result.PREV_LICENSE,
                "current_license": result.CURRENT_LICENSE,
                "status": result.STATUS
            })

        results_list = list(simulation_runs.values())
        results_list.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "message": f"Found {len(results_list)} simulation runs",
            "system_name": system_name,
            "results": results_list
        }

    except Exception as e:
        logger.error(f"Error fetching simulation results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{system_name}/current-fue")
async def get_current_simulation_fue(
        system_name: str,
        db: Session = Depends(get_db)
):
    """
    Get current FUE calculation based on simulation table state.
    """
    logger.info(f"Fetching current simulation FUE for system '{system_name}'")

    try:
        fue_results = await calculate_simulation_fue(system_name, db)

        return {
            "system_name": system_name,
            "license_distribution": {
                "GB": {
                    "count": fue_results['gb_count'],
                    "fue": fue_results['gb_fue']
                },
                "GC": {
                    "count": fue_results['gc_count'],
                    "fue": fue_results['gc_fue']
                },
                "GD": {
                    "count": fue_results['gd_count'],
                    "fue": fue_results['gd_fue']
                }
            },
            "total_fue": fue_results['total_fue']
        }

    except Exception as e:
        logger.error(f"Error calculating simulation FUE: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{system_name}/reset")
async def reset_simulation(
        system_name: str,
        db: Session = Depends(get_db)
):
    """
    Reset simulation table to original RoleLic state.
    """
    logger.info(f"Resetting simulation table for system '{system_name}'")

    try:
        # Just re-run initialization
        return await initialize_simulation_table(system_name, db)

    except Exception as e:
        logger.error(f"Error resetting simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))