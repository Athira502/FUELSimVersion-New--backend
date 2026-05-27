# app/routers/fue_calculation.py
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from psycopg2 import ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette import status
from app.core.logger import setup_logger
from app.models.database import get_db
from app.models.dynamic_models import get_role_lice_data_summary_tablename, get_agr_users_tablename, \
    get_role_lice_data_tablename, get_user_role_data_tablename, get_user_role_summary_tablename
from app.schema.RoleDetailResponse import RoleDetailResponse, SpecificRoleDetailsResponse

router = APIRouter(
    prefix="/fue",
    tags=["FUE Calculation"]
)
logger = setup_logger("fue_calculation_logger")


@router.get("/roles/details/", response_model=List[RoleDetailResponse])
async def get_role_details(
        system_name: str = Query(..., description="System name for filtering roles."),
        db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Fetch role details with authorization classifications and user counts.

    Uses:
    - {SYSTEM}_RoleLicSummary: Pre-calculated role-level license classifications
    - {SYSTEM}_AGRUSERS: User-to-role assignments for counting assigned users

    This is much more efficient than the original approach as classifications
    are already computed in RoleLicSummary.
    """
    logger.info(f"Fetching role details for system: '{system_name}'")

    try:
        # Use the pre-computed summary table instead of recalculating
        role_lic_summary_table = get_role_lice_data_summary_tablename(system_name)
        agrusers_table = get_agr_users_tablename(system_name)

        logger.debug(f"Using tables: '{role_lic_summary_table}' and '{agrusers_table}' for the query.")

        # Use pre-calculated data from RoleLicSummary
        role_details_query = text(f"""
            WITH UserCounts AS (
                SELECT
                    "AGR_NAME",
                    COUNT(DISTINCT "UNAME") AS assignedUsers
                FROM public."{agrusers_table}"
                GROUP BY "AGR_NAME"
            )
            SELECT
                rls."AGR_NAME" AS id,
                rls."AGR_NAME" AS profile,
                rls."TEXT" AS description,
                rls."CLASSIFY_LIC" AS classification,
                COALESCE(uc.assignedUsers, 0) AS assignedUsers,
                rls."GB_COUNT" AS gb,
                rls."GC_COUNT" AS gc,
                rls."GD_COUNT" AS gd,
                rls."NC_COUNT" AS not_classified
            FROM public."{role_lic_summary_table}" rls
            LEFT JOIN UserCounts uc ON rls."AGR_NAME" = uc."AGR_NAME"
            WHERE rls."CLASSIFY_LIC" IN ('GB Advanced Use', 'GC Core Use', 'GD Self-Service Use')
            ORDER BY rls."AGR_NAME";
        """)

        logger.debug(f"Executing role details query. Timeout set to 80 seconds.")
        role_records = db.execute(role_details_query, execution_options={"timeout": 80}).fetchall()

        if not role_records:
            logger.warning(f"No roles found for system: '{system_name}'. Returning empty list.")
            return []

        logger.info(f"Successfully fetched {len(role_records)} roles for system '{system_name}'.")

        return [
            {
                "id": str(record[0]),
                "profile": str(record[1]),
                "description": str(record[2]) if record[2] else "",
                "classification": str(record[3]),
                "assignedUsers": int(record[4]),
                "gb": int(record[5]),
                "gc": int(record[6]),
                "gd": int(record[7]),
                # "notClassified": int(record[8])  # Uncomment if needed in response
            }
            for record in role_records
        ]

    except ProgrammingError as e:
        logger.error(f"SQL Programming Error fetching role details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role details for system '{system_name}' not found or tables do not exist. Please check the system name."
        )
    except Exception as e:
        logger.error(f"Error fetching role details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching role details."
        )


@router.get("/role-details/{role_name:path}", response_model=SpecificRoleDetailsResponse)
async def get_specific_role_details(
        role_name: str = Path(..., description="Role name for filtering role details, can contain slashes."),
        system_name: str = Query(..., description="System name for filtering role details."),
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Fetch detailed authorization objects for a specific role.

    Uses:
    - {SYSTEM}_RoleLicSummary: For role-level info (description)
    - {SYSTEM}_RoleLic: For detailed object-level license classifications

    Returns authorization objects with their individual license classifications.
    """
    logger.info(f"Fetching details for role: '{role_name}' for system: '{system_name}'")

    try:
        role_lic_summary_table = get_role_lice_data_summary_tablename(system_name)
        role_lic_table = get_role_lice_data_tablename(system_name)

        logger.debug(f"Using tables: '{role_lic_summary_table}' and '{role_lic_table}' for role: '{role_name}'.")

        # Get role description from summary
        role_info_query = text(f"""
            SELECT
                "AGR_NAME",
                "TEXT"
            FROM public."{role_lic_summary_table}"
            WHERE "AGR_NAME" = :role_name;
        """)

        role_info = db.execute(role_info_query, {"role_name": role_name}).fetchone()

        if not role_info:
            logger.warning(f"Role '{role_name}' not found in summary for system: '{system_name}'.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found for system '{system_name}'."
            )

        fetched_role_name = role_info[0]
        role_description = role_info[1] if role_info[1] else f"Role: {fetched_role_name}"

        # Get detailed authorization objects from RoleLic
        role_objects_query = text(f"""
            SELECT
                "OBJECT",
                "FIELD",
                "LOW",
                "HIGH",
                "CLASSIFY_LIC",
                "MATCH_TYPE"
            FROM public."{role_lic_table}"
            WHERE "AGR_NAME" = :role_name
            ORDER BY "OBJECT", "FIELD";
        """)

        logger.debug(f"Executing query for specific role object details.")
        records = db.execute(role_objects_query, {"role_name": role_name}).fetchall()

        if not records:
            logger.warning(f"No authorization objects found for role '{role_name}'.")
            # Role exists in summary but has no objects - return empty details
            return {
                "roleName": fetched_role_name,
                "roleDescription": role_description,
                "objectDetails": []
            }

        logger.info(f"Successfully fetched details for role '{role_name}'. Found {len(records)} authorization objects.")

        object_details = []
        for record in records:
            object_details.append({
                "object": str(record[0]),
                "fieldName": str(record[1]),
                "valueLow": str(record[2]) if record[2] else "",
                "valueHigh": str(record[3]) if record[3] else "",
                "classification": str(record[4]),  # CLASSIFY_LIC from RoleLic
                "ttext": str(record[5]) if record[5] else ""  # Using MATCH_TYPE as ttext
            })

        return {
            "roleName": fetched_role_name,
            "roleDescription": role_description,
            "objectDetails": object_details
        }

    except ProgrammingError as e:
        logger.error(f"SQL Programming Error fetching specific role details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data tables for system '{system_name}' not found for role details. Please verify the system name."
        )
    except Exception as e:
        logger.error(f"Error fetching specific role details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching role details."
        )


@router.get("/users-by-role/{role_name:path}")
async def get_users_by_role(
        role_name: str = Path(..., description="Role name to fetch assigned users."),
        system_name: str = Query(..., description="System name for filtering users."),
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Fetch all users assigned to a specific role with their license info.

    Uses:
    - {SYSTEM}_UserRoleLlic: User-role assignments with license classifications

    Returns users with the license classification this role contributes to them.
    """
    logger.info(f"Fetching users for role: '{role_name}' in system: '{system_name}'")

    try:
        user_role_llic_table = get_user_role_data_tablename(system_name)

        logger.debug(f"Using table: '{user_role_llic_table}' for user query.")

        users_query = text(f"""
            SELECT DISTINCT
                "UNAME",
                "CLASSIFY_LIC"
            FROM public."{user_role_llic_table}"
            WHERE "AGR_NAME" = :role_name
            ORDER BY "UNAME";
        """)

        logger.debug(f"Executing query for users assigned to role '{role_name}'.")
        records = db.execute(users_query, {"role_name": role_name}).fetchall()

        users_with_license = [
            {
                "username": str(record[0]),
                "licenseFromRole": str(record[1]) if record[1] else "Not Classified"
            }
            for record in records
        ]

        logger.info(f"Successfully fetched {len(users_with_license)} users for role '{role_name}'.")

        return {
            "roleName": role_name,
            "systemName": system_name,
            "userCount": len(users_with_license),
            "users": users_with_license
        }

    except ProgrammingError as e:
        logger.error(f"SQL Programming Error fetching users by role: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Users table for system '{system_name}' not found. Please verify the system name."
        )
    except Exception as e:
        logger.error(f"Error fetching users by role: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching users."
        )


@router.get("/dashboard/{system_name}")
async def get_fue_dashboard(
        system_name: str = Path(..., description="System name for dashboard data."),
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Fetch FUE dashboard summary data.

    Uses:
    - {SYSTEM}_UserLicSummary: User-level license distribution and governance flags
    - {SYSTEM}_RoleLicSummary: Role-level license distribution

    Returns comprehensive dashboard metrics including:
    - User license distribution (GB/GC/GD)
    - Role license distribution (GB/GC/GD)
    - Dormant user counts (90+ and 180+ days)
    - Locked/Expired user governance metrics
    """
    logger.info(f"Fetching FUE dashboard for system: '{system_name}'")

    try:
        user_lic_summary_table = get_user_role_summary_tablename(system_name)
        role_lic_summary_table = get_role_lice_data_summary_tablename(system_name)

        logger.debug(f"Using tables: '{user_lic_summary_table}' and '{role_lic_summary_table}'")

        # User license distribution
        user_distribution_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{user_lic_summary_table}";
        """)

        user_dist = db.execute(user_distribution_query).fetchone()

        # Role license distribution
        role_distribution_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{role_lic_summary_table}";
        """)

        role_dist = db.execute(role_distribution_query).fetchone()

        # Dormant 90+ days
        dormant_90_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{user_lic_summary_table}"
            WHERE "FLAG_90" = TRUE;
        """)

        dormant_90 = db.execute(dormant_90_query).fetchone()

        # Dormant 180+ days
        dormant_180_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{user_lic_summary_table}"
            WHERE "FLAG_180" = TRUE;
        """)

        dormant_180 = db.execute(dormant_180_query).fetchone()

        # Expired not locked (UFLAG indicates expired but not locked)
        expired_not_locked_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{user_lic_summary_table}"
            WHERE "UFLAG" NOT IN ('0', '128') AND "LOCKED" = FALSE;
        """)

        expired_not_locked = db.execute(expired_not_locked_query).fetchone()

        # Locked not expired
        locked_not_expired_query = text(f"""
            SELECT
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GB Advanced Use' THEN 1 END) AS gb,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GC Core Use' THEN 1 END) AS gc,
                COUNT(CASE WHEN "CLASSIFY_LIC" = 'GD Self-Service Use' THEN 1 END) AS gd,
                COUNT(*) AS total
            FROM public."{user_lic_summary_table}"
            WHERE "LOCKED" = TRUE;
        """)

        locked_not_expired = db.execute(locked_not_expired_query).fetchone()

        logger.info(f"Successfully fetched dashboard data for system '{system_name}'.")

        return {
            "user_license_distribution": {
                "gb": int(user_dist[0]),
                "gc": int(user_dist[1]),
                "gd": int(user_dist[2]),
                "total": int(user_dist[3])
            },
            "role_license_distribution": {
                "gb": int(role_dist[0]),
                "gc": int(role_dist[1]),
                "gd": int(role_dist[2]),
                "total": int(role_dist[3])
            },
            "dormant_90": {
                "gb": int(dormant_90[0]),
                "gc": int(dormant_90[1]),
                "gd": int(dormant_90[2]),
                "total": int(dormant_90[3])
            },
            "dormant_180": {
                "gb": int(dormant_180[0]),
                "gc": int(dormant_180[1]),
                "gd": int(dormant_180[2]),
                "total": int(dormant_180[3])
            },
            "expired_not_locked": {
                "gb": int(expired_not_locked[0]),
                "gc": int(expired_not_locked[1]),
                "gd": int(expired_not_locked[2]),
                "total": int(expired_not_locked[3])
            },
            "locked_not_expired": {
                "gb": int(locked_not_expired[0]),
                "gc": int(locked_not_expired[1]),
                "gd": int(locked_not_expired[2]),
                "total": int(locked_not_expired[3])
            }
        }

    except ProgrammingError as e:
        logger.error(f"SQL Programming Error fetching dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard data for system '{system_name}' not found or tables do not exist."
        )
    except Exception as e:
        logger.error(f"Error fetching dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching dashboard data."
        )