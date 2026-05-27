import traceback

from fastapi.params import File
import io
from sqlalchemy import inspect as sqla_inspect, text
from typing import List, Dict
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Body
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from fastapi.responses import StreamingResponse
import pandas as pd
from io import StringIO

from starlette import status

from app.core.logger import setup_logger, get_daily_log_filename
from app.models.database import get_db, engine, Base
from app.models.client_sys_release_version import clientSysReleaseData, ensure_ruleset_table_exists, ruleSet
from app.schema.SystemSchema import SystemCreate, SystemUpdate, SystemResponse, RuleSetSchema
from app.models.dynamic_models import (
    get_user_role_data_tablename,
    get_agr_1251_tablename, get_agr_users_tablename, get_agr_define_tablename, get_agr_agrs_tablename,
    get_usr02_tablename, get_transaction_usage_data_tablename, get_tcode_data_tablename, get_flpca_data_tablename,
    get_role_lice_data_tablename, get_role_lice_data_summary_tablename, get_user_role_summary_tablename,
    get_role_lic_sim_tablename, get_simulation_result_tablename, get_usobxC_data_tablename, get_obj_text_data_tablename,
)

router = APIRouter(
    prefix="/manage-data",
    tags=["Manage Data"]
)
logger = setup_logger("app_logger")

async def table_exists(db_engine, table_name: str) -> bool:
    """Checks if a table exists in the database."""
    inspector = sqla_inspect(db_engine)
    return inspector.has_table(table_name)


@router.post("/systems", response_model=SystemResponse)
async def create_system(
    payload: SystemCreate,        # 👈 no Body(), no by_alias
    db: Session = Depends(get_db)
):
    existing = db.query(clientSysReleaseData).filter(
        clientSysReleaseData.SYSTEM_NAME == payload.SYSTEM_NAME
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail=f"System '{payload.SYSTEM_NAME}' already exists.")

    entry = clientSysReleaseData(
        SYSTEM_NAME=payload.SYSTEM_NAME,
        SYSTEM_RELEASE_INFO=payload.SYSTEM_RELEASE_INFO,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info(f"Created system: {payload.SYSTEM_NAME}")
    return entry





@router.get("/systems", response_model=List[SystemResponse])
async def get_all_systems(db: Session = Depends(get_db)):
    """Returns all systems."""
    return db.query(clientSysReleaseData).all()


@router.get("/systems/{system_name}", response_model=SystemResponse)
async def get_system(SYSTEM_NAME: str, db: Session = Depends(get_db)):
    """Returns a single system by name."""
    entry = (
        db.query(clientSysReleaseData)
        .filter(clientSysReleaseData.SYSTEM_NAME ==SYSTEM_NAME  )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"System '{SYSTEM_NAME}' not found.")
    return entry


@router.put("/systems/{system_name}", response_model=SystemResponse)
async def update_system(
    system_name: str,
    payload: SystemUpdate,
    db: Session = Depends(get_db)
):
    """Updates the release info for a system."""
    entry = (
        db.query(clientSysReleaseData)
        .filter(clientSysReleaseData.SYSTEM_NAME == system_name)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"System '{system_name}' not found.")

    entry.SYSTEM_RELEASE_INFO = payload.system_release_info
    db.commit()
    db.refresh(entry)
    logger.info(f"Updated system: {system_name}")
    return entry


@router.delete("/systems/{system_name}")
async def delete_system(system_name: str, db: Session = Depends(get_db)):
    """Deletes a system by name and all its related tables."""

    entry = (
        db.query(clientSysReleaseData)
        .filter(clientSysReleaseData.SYSTEM_NAME == system_name)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"System '{system_name}' not found.")

    potential_table_names = [
        get_agr_1251_tablename(system_name),
        get_agr_users_tablename(system_name),
        get_agr_define_tablename(system_name),
        get_agr_agrs_tablename(system_name),
        get_usr02_tablename(system_name),
        get_transaction_usage_data_tablename(system_name),
        get_tcode_data_tablename(system_name),
        get_flpca_data_tablename(system_name),
        get_role_lice_data_tablename(system_name),
        get_role_lice_data_summary_tablename(system_name),
        get_user_role_data_tablename(system_name),
        get_user_role_summary_tablename(system_name),
        get_role_lic_sim_tablename(system_name),
        get_simulation_result_tablename(system_name)
    ]

    inspector = sqla_inspect(engine)
    existing_tables = inspector.get_table_names()
    tables_to_drop = [table for table in potential_table_names if table in existing_tables]

    dropped_tables = []
    failed_tables = []

    # Drop tables first
    for table_name in tables_to_drop:
        try:
            db.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            db.commit()
            dropped_tables.append(table_name)
            logger.info(f"Dropped table: {table_name}")
        except Exception as e:
            logger.error(f"Failed to drop table {table_name}: {str(e)}")
            failed_tables.append(table_name)
            db.rollback()

    # Always try to delete the system entry (even if some tables failed)
    try:
        db.delete(entry)
        db.commit()
        logger.info(f"Deleted system: {system_name}")
    except Exception as e:
        logger.error(f"Failed to delete system entry: {str(e)}")
        db.rollback()
        # If system entry delete fails, this is critical
        raise HTTPException(
            status_code=500,
            detail=f"Tables dropped but failed to delete system entry: {str(e)}"
        )

    return {
        "message": f"System '{system_name}' deleted successfully.",
        "dropped_tables": dropped_tables,
        "failed_tables": failed_tables,
        "total_tables_dropped": len(dropped_tables),
        "total_tables_failed": len(failed_tables)
    }


# @router.delete("/systems/{system_name}")
# async def delete_system(system_name: str, db: Session = Depends(get_db)):
#     """Deletes a system by name."""
#     entry = (
#         db.query(clientSysReleaseData)
#         .filter(clientSysReleaseData.SYSTEM_NAME == system_name)
#         .first()
#     )
#     if not entry:
#         raise HTTPException(status_code=404, detail=f"System '{system_name}' not found.")
#
#     db.delete(entry)
#     db.commit()
#     logger.info(f"Deleted system: {system_name}")
#     return {"message": f"System '{system_name}' deleted successfully."}


@router.post("/ruleset", status_code=status.HTTP_201_CREATED)
async def create_or_replace_ruleset(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """
    Deletes all existing data in the Z_FUE_RULESET table
    and uploads the newly shared data from an .xlsx file.
    """
    # 1. Ensure the DB table physically exists
    ensure_ruleset_table_exists()

    # 2. Check file extension
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid Excel (.xlsx) file."
        )

    try:
        # 3. Read the Excel content into an in-memory buffer
        contents = await file.read()
        excel_buffer = io.BytesIO(contents)

        # 4. Parse the Excel file with Pandas
        df = pd.read_excel(excel_buffer, engine='openpyxl')

        # Clean up columns: trim spaces and make lowercase to match your schema fields
        df.columns = [str(col).strip().lower() for col in df.columns]

        # 5. Map Excel headers to your RuleSetSchema fields (ignoring auto-incrementing 'id')
        required_columns = {"rule_description", "auth_object", "auth_field", "auth_value"}
        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Excel sheet is missing required columns: {', '.join(missing)}"
            )

        # 6. CRITICAL STEP: Clear out old ruleset rows completely
        logger.info("Purging old records from Z_FUE_RULESET table...")
        db.query(ruleSet).delete()

        # 7. Map rows into your database SQLAlchemy model instances
        new_records = []
        for _, row in df.iterrows():
            # Skip rows where vital fields are completely blank
            if pd.isna(row["rule_description"]) and pd.isna(row["auth_object"]):
                continue

            entry = ruleSet(
                RULE_DESCRIPTION=str(row["rule_description"]).strip(),
                AUTHOBJECT=str(row["auth_object"]).strip(),
                AUTHFIELD=str(row["auth_field"]).strip(),
                AUTHVALUE=str(row["auth_value"]).strip()
            )
            new_records.append(entry)

        if not new_records:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded Excel sheet contains no valid data rows."
            )

        # 8. Bulk insert fresh records and commit transaction safely
        db.bulk_save_objects(new_records)
        db.commit()

        logger.info(f"Successfully replaced ruleset data. Imported {len(new_records)} records.")
        return {
            "status": "success",
            "message": f"Successfully cleared old configuration rules and imported {len(new_records)} fresh ruleset records."
        }

    except HTTPException as http_err:
        db.rollback()
        raise http_err
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process ruleset bulk upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the Excel data: {str(e)}"
        )


@router.delete("/rulesets")
async def delete_all_rulesets(db: Session = Depends(get_db)):
    """Deletes all records from the Z_FUE_RULESET table."""

    # 1. Count how many records exist before deleting (optional but good for tracking)
    record_count = db.query(ruleSet).count()

    if record_count == 0:
        raise HTTPException(
            status_code=404,
            detail="No ruleset data found to delete."
        )

    try:
        # 2. Use .delete() on the query directly to clear out the entire table efficiently
        db.query(ruleSet).delete()
        db.commit()

        logger.info(f"Successfully deleted all {record_count} ruleset entries.")
        return {
            "status": "success",
            "message": f"Successfully deleted all {record_count} ruleset records."
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear ruleset table: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while deleting ruleset data: {str(e)}"
        )


@router.get("/tables/{system_name}", response_model=List[str])
async def get_tables_for_client_system(system_name: str):
    logger.debug("Starting to tables for given  system nameand client from the database.")

    """Returns a list of existing table names for a given client and system."""
    potential_table_names = [
        get_agr_1251_tablename(system_name),
        get_agr_users_tablename(system_name),
        get_agr_define_tablename(system_name),
        get_agr_agrs_tablename(system_name),
        get_usr02_tablename(system_name),
        get_transaction_usage_data_tablename(system_name),
        get_tcode_data_tablename(system_name),
        get_flpca_data_tablename(system_name),
        get_usobxC_data_tablename(system_name),
        get_obj_text_data_tablename(system_name)
    ]
    inspector = sqla_inspect(engine)
    existing_tables = inspector.get_table_names()
    logger.info(f"Successfully fetched tables {existing_tables} for  and system: {system_name}.")
    return [table for table in potential_table_names if table in existing_tables]

@router.get("/download/{system_name}/{table_name}")
async def download_table_data(system_name: str, table_name: str, db: Session = Depends(get_db)):
    """Downloads data from a specified table for a client and system as CSV."""
    logger.info(f"download_table_data called with: system_name={system_name}, table_name={table_name}")

    if not await table_exists(engine, table_name):
        error_message = f"Table '{table_name}' not found"
        logger.error(error_message)
        raise HTTPException(status_code=404, detail=error_message)

    try:
        query_string = f'SELECT * FROM public."{table_name}"'
        logger.info(f"Executing query: {query_string}")
        query = text(query_string)

        result_proxy = db.execute(query)
        result = result_proxy.fetchall()
        columns = result_proxy.keys()  # Get column names from metadata

        if not result:
            message = f"No data found in table '{table_name}'"
            logger.info(message)
            return JSONResponse(content={"message": message}, status_code=200)

        df = pd.DataFrame(result, columns=columns)
        csv_output = StringIO()
        df.to_csv(csv_output, index=False)

        response = StreamingResponse(
            iter([csv_output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
        )
        logger.info("Returning StreamingResponse")
        return response

    except Exception as e:
        error_message = f"Error downloading data from {table_name}: {e}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)



@router.delete("/delete/{system_name}/{table_name}")
async def truncate_table(system_name: str, table_name: str, db: Session = Depends(get_db)):
    """Truncates (deletes all data from) a specified table for a client and system."""
    if not await table_exists(engine, table_name):
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        query = text(f'DROP TABLE public."{table_name}"')
        db.execute(query)
        db.commit()
        logger.info(f"Table '{table_name}' deleted successfully")
        return JSONResponse(content={"message": f"Table '{table_name}' deleted successfully"}, status_code=200)
    except Exception as e:
        logger.error(f"Error deleting table {table_name}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete table")
