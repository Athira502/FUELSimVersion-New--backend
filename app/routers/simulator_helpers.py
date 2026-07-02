# app/routers/simulation_helpers.py

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.logger import setup_logger
from app.models.database import get_db
from app.models.client_sys_release_version import actvtText
from app.models.dynamic_models import (
    create_role_lic_model,
    create_role_lic_summary_model,
    create_AGRUSERS_model,
    create_role_lic_sim_model,
    ensure_table_exists
)

router = APIRouter(
    prefix="/simulation-helpers",
    tags=["Simulation Helpers"]
)

logger = setup_logger("app_logger")

# License classification order for sorting
CLASSIFICATION_ORDER = {
    "GB Advanced Use": 1,
    "GC Core Use": 2,
    "GD Self-Service Use": 3,
    "Not Classified": 4
}

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
# Get role details for simulation UI (equivalent to old /roles_for_sim/details/)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/roles/details")
async def get_simulation_role_details(
        system_name: str,
        db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all roles with their classification details for simulation UI.
    Equivalent to old project's /roles_for_sim/details/
    """
    logger.info(f"Fetching simulation role details for system '{system_name}'")

    try:
        RoleLicSummaryModel = create_role_lic_summary_model(system_name)
        AGRUsersModel = create_AGRUSERS_model(system_name)

        ensure_table_exists(db.bind, RoleLicSummaryModel)
        ensure_table_exists(db.bind, AGRUsersModel)

        # Query similar to old project's implementation
        role_details_query = text(f"""
            WITH RoleAggregates AS (
                SELECT
                    rls."AGR_NAME",
                    rls."TEXT" AS description,
                    rls."CLASSIFY_LIC" AS classification,
                    rls."GB_COUNT" AS gb,
                    rls."GC_COUNT" AS gc,
                    rls."GD_COUNT" AS gd,
                    rls."TOTAL_OBJ" AS total_objects
                FROM "{RoleLicSummaryModel.__tablename__}" rls
                WHERE rls."CLASSIFY_LIC" IN ('GB Advanced Use', 'GC Core Use', 'GD Self-Service Use')
            ),
            UserCounts AS (
                SELECT
                    urm."AGR_NAME",
                    COUNT(DISTINCT urm."UNAME") AS assignedUsers
                FROM "{AGRUsersModel.__tablename__}" urm
                GROUP BY urm."AGR_NAME"
            )
            SELECT
                ra."AGR_NAME" AS id,
                ra."AGR_NAME" AS profile,
                ra.description,
                ra.classification,
                COALESCE(uc.assignedUsers, 0) AS assignedUsers,
                ra.gb,
                ra.gc,
                ra.gd,
                ra.total_objects
            FROM RoleAggregates ra
            LEFT JOIN UserCounts uc ON ra."AGR_NAME" = uc."AGR_NAME"
            ORDER BY ra."AGR_NAME"
        """)

        role_records = db.execute(role_details_query).fetchall()

        if not role_records:
            logger.info(f"No role records found for system '{system_name}'. Returning empty list.")
            return []

        return [
            {
                "id": str(record[0]),
                "profile": record[1],
                "description": record[2],
                "classification": record[3],
                "assignedUsers": record[4],
                "gb": record[5],
                "gc": record[6],
                "gd": record[7],
                "total_objects": record[8]
            }
            for record in role_records
        ]

    except Exception as e:
        logger.error(f"Error fetching simulation role details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching role details: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════
# Get specific role details for simulation (equivalent to old /role-details-for-simulation/)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/role-details/{role_name}")
async def get_specific_role_simulation_details(
        system_name: str,
        role_name: str = Path(...),
        db: Session = Depends(get_db)
):
    """
    Get detailed authorization objects for a specific role in simulation context.
    Equivalent to old project's /role-details-for-simulation/{role_name}
    """
    logger.info(f"Fetching simulation details for role '{role_name}' in system '{system_name}'")

    try:
        RoleLicSimModel = create_role_lic_sim_model(system_name)
        ensure_table_exists(db.bind, RoleLicSimModel)

        table_name = RoleLicSimModel.__tablename__

        # Query to get role details from simulation table
        query = text(f"""
            SELECT
                "AGR_NAME",
                "OBJECT",
                "FIELD",
                "LOW",
                "HIGH",
                "ORIGINAL_CLASSIFY_LIC",
                "SIM_CLASSIFY_LIC",
                "OPERATION",
                "NEW_LOW",
                "NEW_HIGH"
            FROM "{table_name}"
            WHERE "AGR_NAME" = :role_name
            ORDER BY "OBJECT", "FIELD"
        """)

        records = db.execute(query, {"role_name": role_name}).fetchall()

        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"Role '{role_name}' not found in simulation table"
            )

        object_details = []
        for record in records:
            object_details.append({
                "object": record[1],
                "fieldName": record[2],
                "valueLow": record[8] if record[8] else record[3],  # NEW_LOW or LOW
                "valueHigh": record[9] if record[9] else record[4],  # NEW_HIGH or HIGH
                "classification": record[6] if record[6] else record[5],  # SIM or ORIGINAL
                "operation": record[7],
                "originalClassification": record[5]
            })

        # Sort by classification priority
        object_details.sort(key=lambda x: CLASSIFICATION_ORDER.get(x["classification"], 999))

        return {
            "roleName": records[0][0],
            "objectDetails": object_details
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching specific role details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching role details: {str(e)}")






# ════════════════════════════════════════════════════════════════════════════
# Get simulation FUE calculation (pivot table equivalent)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/fue-calculation")
async def get_simulation_fue_calculation(
        system_name: str,
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate FUE based on simulation table state.
    Equivalent to old project's get_simulation_license_classification_pivot_table
    """
    logger.info(f"Calculating simulation FUE for system '{system_name}'")

    try:
        from collections import defaultdict
        import math
        from sqlalchemy import or_

        RoleLicSimModel = create_role_lic_sim_model(system_name)
        AGRUsersModel = create_AGRUSERS_model(system_name)

        ensure_table_exists(db.bind, RoleLicSimModel)
        ensure_table_exists(db.bind, AGRUsersModel)

        # Step 1: Get most restrictive license per role from simulation table
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

        # Get most restrictive license per role
        role_final_licenses = {}
        for role, licenses in role_licenses.items():
            role_final_licenses[role] = min(
                licenses,
                key=lambda x: LICENSE_PRIORITY.get(x, 999)
            )

        # Step 2: Map roles to users
        user_role_mappings = db.query(AGRUsersModel).all()

        user_licenses = defaultdict(list)
        for mapping in user_role_mappings:
            role_license = role_final_licenses.get(
                mapping.AGR_NAME,
                'Not Classified'
            )
            user_licenses[mapping.UNAME].append(role_license)

        # Get most restrictive license per user
        license_counts = defaultdict(int)

        for user, licenses in user_licenses.items():
            final_lic = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))
            license_counts[final_lic] += 1

        # Calculate FUE
        gb_count = license_counts.get('GB Advanced Use', 0)
        gc_count = license_counts.get('GC Core Use', 0)
        gd_count = license_counts.get('GD Self-Service Use', 0)
        nc_count = license_counts.get('Not Classified', 0)

        gb_fue = math.ceil(gb_count * FUE_FACTORS['GB Advanced Use'])
        gc_fue = math.ceil(gc_count * FUE_FACTORS['GC Core Use'])
        gd_fue = math.ceil(gd_count * FUE_FACTORS['GD Self-Service Use'])

        total_fue = gb_fue + gc_fue + gd_fue

        pivot_table = {
            "Users": {
                "GB Advanced Use": gb_count,
                "GC Core Use": gc_count,
                "GD Self-Service Use": gd_count,
                "Not Classified": nc_count,
                "Total": gb_count + gc_count + gd_count + nc_count
            }
        }

        fue_summary = {
            "GB Advanced Use FUE": gb_fue,
            "GC Core Use FUE": gc_fue,
            "GD Self-Service Use FUE": gd_fue,
            "Total FUE Required": total_fue
        }

        return {
            "pivot_table": pivot_table,
            "fue_summary": fue_summary,
            "system_name": system_name
        }

    except Exception as e:
        logger.error(f"Error calculating simulation FUE: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error calculating FUE: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════
# Get auth object field license data (for Add operation suggestions)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/auth-field-licenses")
async def get_auth_field_license_data(
        system_name: str,
        authorization_object: str = Query(...),
        field: str = Query(...),
        db: Session = Depends(get_db)
):
    """
    Get license data for authorization object and field.
    Used for providing suggestions in Add operations.

    NOTE: This endpoint requires the Z_FUE_RULESET table to exist.
    In the new project, this data comes from the ruleset table.
    """
    logger.info(
        f"Fetching auth field license data for object='{authorization_object}', field='{field}', system='{system_name}'")

    try:
        from app.models.client_sys_release_version import ruleSet

        # Query the ruleset table for matching auth object and field
        auth_records = db.query(ruleSet).filter(
            ruleSet.AUTHOBJECT == authorization_object,
            ruleSet.AUTHFIELD == field
        ).all()

        if not auth_records:
            logger.warning(f"No license data found for object='{authorization_object}', field='{field}'")
            return []

        results = [
            {
                "AUTHORIZATION_OBJECT": record.AUTHOBJECT,
                "FIELD": record.AUTHFIELD,
                "ACTIVITY": record.AUTHVALUE,
                "LICENSE": record.RULE_DESCRIPTION,
                "TEXT": f"{record.AUTHVALUE} - {record.RULE_DESCRIPTION}",
                "UI_TEXT": f"{record.AUTHVALUE};{record.AUTHFIELD};{record.RULE_DESCRIPTION}"
            }
            for record in auth_records
        ]

        logger.info(f"Found {len(results)} license options for object='{authorization_object}', field='{field}'")
        return results

    except Exception as e:
        logger.error(f"Error fetching auth field license data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching license data: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════
# Get add suggestions (equivalent to old /get-add-suggestions/)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/{system_name}/add-suggestions")
async def get_add_suggestions(
        system_name: str,
        authorization_object: str = Query(...),
        field: str = Query(...),
        db: Session = Depends(get_db)
):
    """
    Get suggestions for Add operations including both activity and license.
    Equivalent to old project's /get-add-suggestions/
    """
    logger.info(f"Getting add suggestions for system='{system_name}', object='{authorization_object}', field='{field}'")

    try:
        from app.models.client_sys_release_version import ruleSet

        # Query the ruleset for available values
        auth_records = db.query(ruleSet).filter(
            ruleSet.AUTHOBJECT == authorization_object,
            ruleSet.AUTHFIELD == field
        ).all()

        if not auth_records:
            logger.info(f"No suggestions found for object='{authorization_object}', field='{field}'")
            return []

        suggestions = []
        for record in auth_records:
            suggestions.append({
                "value": record.AUTHVALUE,
                "license": record.RULE_DESCRIPTION,
                "ui_text": f"{record.AUTHVALUE};{record.AUTHFIELD};{record.RULE_DESCRIPTION}",
                "text": f"{record.AUTHVALUE} ({record.RULE_DESCRIPTION})"
            })

        logger.info(f"Returning {len(suggestions)} suggestions")
        return suggestions

    except Exception as e:
        logger.error(f"Error getting add suggestions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")