from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import exists
from sqlalchemy import inspect as sqla_inspect, desc, text
from app.core.logger import setup_logger, get_daily_log_filename
from app.models.database import get_db, engine
from app.models.client_sys_release_version import clientSysReleaseData, ensure_ruleset_table_exists
from app.models.dynamic_models import create_AGR1251_model, create_role_lic_model, create_AGRDEFINE_model, \
    create_role_lic_summary_model, create_AGRUSERS_model, create_user_lic_model, create_USR02_model, \
    create_TRANSACTIONUSAGE_model, create_user_lic_summary_model

from app.models.log_data import logData
from app.service.data_loader_service import (
    DataLoaderError,
    load_agrdefine_from_csv_upload, load_agragrs_from_csv_upload, load_usr02_from_csv_upload,
    load_transactionusage_from_csv_upload, load_tstct_from_csv_upload, load_flpca_from_csv_upload,
    load_usobxc_from_csv_upload, load_objText_from_csv_upload
)
import math
import logging
from datetime import date, datetime,timedelta
from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from app.service.data_loader_service import load_agr1251_from_csv_upload, load_agrusers_from_csv_upload

router = APIRouter(
    prefix="/data",
    tags=["Data Loading"]
)
logger = setup_logger("app_logger")
async def table_exists(db_engine, table_name: str) -> bool:
    """Checks if a table exists in the database."""
    inspector = sqla_inspect(db_engine)
    return inspector.has_table(table_name)

async def create_table(db_engine, model_class):

    """Creates a table if it doesn't exist."""
    table_name = model_class.__tablename__
    if not await table_exists(db_engine, table_name):
        logger.info(f"Creating table: {table_name}")
        print(f"Creating table: {table_name}")
        try:
            model_class.__table__.create(bind=db_engine)
            logger.info(f"Table '{table_name}' created successfully.")
            print(f"Table '{table_name}' created successfully.")
        except Exception as e:
            logger.error(f"Error creating table '{table_name}': {e}")
            print(f"Error creating table '{table_name}': {e}")
            raise  # Re-raise the exception after logging
    else:
        logger.warning(f"Table '{table_name}' already exists.")
        print(f"Table '{table_name}' already exists.")

async def ensure_client_system_info(db: Session, system_name: str, system_release_info: str):
    """Ensures client, system, and release info exists in Z_FUE_CLIENT_SYS_INFO."""
    await create_table(engine, clientSysReleaseData)  # Create the table if it doesn't exist
    await create_table(engine,logData)

    exists_query = db.query(exists().where(
        (clientSysReleaseData.SYSTEM_NAME == system_name) &
        (clientSysReleaseData.SYSTEM_RELEASE_INFO == system_release_info)
    )).scalar()

    if not exists_query:
        db_entry = clientSysReleaseData(
            SYSTEM_NAME=system_name,
            SYSTEM_RELEASE_INFO=system_release_info
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        print(f"Added new system info: {system_name}, {system_release_info}")
        logger.info(f"Added new system info:{system_name}, {system_release_info}")
    else:
        print(f"system info already exists: {system_name}, {system_release_info}")
        logger.info(f"system info already exists: {system_name}, {system_release_info}")

@router.post("/load-agr1251")
async def load_agr_1251_endpoint(
    system_name: str,
    system_release_info: str,  # Expect system release info
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Loads authorization data from an uploaded CSV file for a specific client and system.
    """
    print(f"Received request to load agr_1251 data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to agr_1251 data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    filename = csv_file.filename
    log_entry = logData(
        FILENAME=filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id
    try:
        result = await load_agr1251_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        print(f"Auth data load completed: {result}")
        logger.info(f"Auth data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading auth data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading auth data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during auth data load")

@router.post("/load-agrusers")
async def load_agr_users_endpoint(
        system_name: str,
        system_release_info: str,  # Expect system release info
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """
    Loads authorization data from an uploaded CSV file for a specific client and system.
    """
    print(f"Received request to load agr_users data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to agr_users data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    filename = csv_file.filename
    log_entry = logData(
        FILENAME=filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id
    try:
        result = await load_agrusers_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        print(f"Auth data load completed: {result}")
        logger.info(f"Auth data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading auth data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading auth data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during auth data load")

@router.post("/load-agrdefine")
async def load_agr_define_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads AGR_DEFINE data from an uploaded CSV file for a specific system."""
    print(f"Received request to load AGR_DEFINE data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load AGR_DEFINE data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_agrdefine_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"AGR_DEFINE data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading AGR_DEFINE data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading AGR_DEFINE data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during AGR_DEFINE data load")

@router.post("/load-agragrs")
async def load_agr_agrs_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads AGR_AGRS data from an uploaded CSV file for a specific system."""
    print(f"Received request to load AGR_AGRS data for system: {system_name}, release: {system_release_info}")
    logger.info(f"Received request to load AGR_AGRS data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_agragrs_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"AGR_AGRS data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading AGR_AGRS data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading AGR_AGRS data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during AGR_AGRS data load")

@router.post("/load-usr02")
async def load_usr02_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads USR02 data from an uploaded CSV file for a specific system."""
    print(f"Received request to load USR02 data for system: {system_name}, release: {system_release_info}")
    logger.info(f"Received request to load USR02 data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_usr02_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"USR02 data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading USR02 data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading USR02 data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during USR02 data load")


@router.post("/load-transactionusage")
async def load_transaction_usage_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads TRANSACTION_USAGE data from an uploaded CSV file for a specific system."""
    print(f"Received request to load TRANSACTION_USAGE data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load TRANSACTION_USAGE data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_transactionusage_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"TRANSACTION_USAGE data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading TRANSACTION_USAGE data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading TRANSACTION_USAGE data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during TRANSACTION_USAGE data load")


@router.post("/load-tstctData")
async def load_tsctct_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads TRANSACTION_USAGE data from an uploaded CSV file for a specific system."""
    print(f"Received request to load TSTCT data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load TSTCT data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_tstct_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"TSTCT data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading TSTCT data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading TSTCT data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during TSTCT data load")

@router.post("/load-flpcaData")
async def load_flpca_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads FLPCA data from an uploaded CSV file for a specific system."""
    print(f"Received request to load FLPCA data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load FLPCA data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_flpca_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"FLPCA data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading FLPCA data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading FLPCA data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during FLPCA data load")




@router.post("/load-usobxcData")
async def load_usobxc_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads USOBXC data from an uploaded CSV file for a specific system."""
    print(f"Received request to load USOBXC data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load USOBXC data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_usobxc_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"USOBXC data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading USOBXC data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading USOBXC data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during USOBXC data load")


@router.post("/load-objTextData")
async def load_objText_endpoint(
        system_name: str,
        system_release_info: str,
        csv_file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Loads objText data from an uploaded CSV file for a specific system."""
    print(f"Received request to load objText data for system: {system_name}, release: {system_release_info}")
    logger.info(
        f"Received request to load objText data for system: '{system_name}', release: '{system_release_info}'")
    logger.debug(f"Uploaded filename: '{csv_file.filename}', content type: '{csv_file.content_type}'")

    await ensure_client_system_info(db, system_name, system_release_info)
    log_entry = logData(
        FILENAME=csv_file.filename,
        SYSTEM_NAME=system_name,
        SYSTEM_RELEASE_INFO=system_release_info,
        STATUS="In Progress"
    )
    db.add(log_entry)
    db.commit()
    log_id = log_entry.id

    try:
        result = await load_objText_from_csv_upload(
            db=db,
            csv_file=csv_file.file,
            system_name=system_name
        )
        logger.info(f"TOBJL data load completed: {result}")
        db.query(logData).filter(logData.id == log_id).update({"STATUS": "Success"})
        db.commit()
        return result
    except DataLoaderError as e:
        logger.error(f"Error loading TOBJL data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error loading TOBJL data: {e}")
        db.query(logData).filter(logData.id == log_id).update(
            {"STATUS": "Failed", "LOG_DATA": f"Internal server error: {e}"})
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during TOBJL data load")




@router.get("/latest-log", response_model=List[dict])
async def get_latest_logs(db: Session = Depends(get_db)):
    """
    Retrieves the latest 10 log entries from the Z_FUE_LOG_FILE table.
    """
    logger.info(
        f"Request for fetching the new logs received")

    try:
        logs = (
            db.query(logData)
            .order_by(desc(logData.TIMESTAMP))
            .limit(15)
            .all()
        )

        if logs:
            return [
                {
                    "timestamp": log.TIMESTAMP,
                    "filename": log.FILENAME,
                    "client_name": log.CLIENT_NAME,
                    "system_name": log.SYSTEM_NAME,
                    "system_release_info": log.SYSTEM_RELEASE_INFO,
                    "status": log.STATUS,
                    "log_data": log.LOG_DATA
                }
                for log in logs
            ]
            logger.info(f"Log fteched")
            logger.debug(f"Log fteched: {logs}")
        else:
            raise HTTPException(status_code=404, detail="No log entries found")
    except Exception as e:
        logger.error(f"Error retrieving log entries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# ─────────────────────────────────────────────────────────────────────────────
# License priority map — lower number = more restrictive = higher FUE cost
# ─────────────────────────────────────────────────────────────────────────────
LICENSE_PRIORITY = {
    'GB Advanced Use': 100,
    'GC Core Use': 200,
    'GD Self-Service Use': 300,
    'Not Classified': 999,
}


# ════════════════════════════════════════════════════════════════════════════
# STAGE 2 — RoleLic
# ════════════════════════════════════════════════════════════════════════════

def _evaluate_match(authvalue: str, low: Optional[str], high: Optional[str]) -> Optional[str]:
    """Returns match type string or None if no match."""
    if not authvalue:
        return None
    if authvalue == '*':
        return 'Rule Wildcard'
    if low == '*':
        return 'Role Wildcard'
    if not high or high.strip() == '':
        if low == authvalue:
            return 'Exact Match'
        return None
    if low <= authvalue <= high:
        return 'Range Match'
    return None


@router.post("/fue/{system_name}/compute/rolelic")
async def compute_rolelic(system_name: str, db: Session = Depends(get_db)):
    """Stage 2 — Populate RoleLic from AGR1251 + RuleSet."""
    logger.info(f"[Stage 2] Computing RoleLic for {system_name}")
    try:
        AGR1251Model = create_AGR1251_model(system_name)
        RoleLicModel = create_role_lic_model(system_name)

        from app.models.client_sys_release_version import ruleSet
        RuleSetModel = ruleSet

        active_connection = db.get_bind()
        AGR1251Model.__table__.create(bind=active_connection, checkfirst=True)
        RoleLicModel.__table__.create(bind=active_connection, checkfirst=True)

        ruleset_map = defaultdict(list)
        for rule in db.query(RuleSetModel).all():
            step = LICENSE_PRIORITY.get(rule.RULE_DESCRIPTION, 999)
            ruleset_map[(rule.AUTHOBJECT, rule.AUTHFIELD)].append({
                'step': step,
                'license': rule.RULE_DESCRIPTION,
                'authvalue': rule.AUTHVALUE,
            })

        db.query(RoleLicModel).delete()
        db.flush()

        batch = []
        for row in db.query(AGR1251Model).all():
            candidate_rules = ruleset_map.get((row.OBJECT, row.FIELD), [])
            matched = []
            for rule in candidate_rules:
                match_type = _evaluate_match(rule['authvalue'], row.LOW, row.HIGH)
                if match_type is not None:
                    matched.append((rule['step'], rule['license'], match_type))

            if matched:
                best = min(matched, key=lambda x: x[0])
                classify_lic = best[1]
                match_type = best[2]
            else:
                classify_lic = 'Not Classified'
                match_type = 'No Match'

            batch.append(RoleLicModel(
                AGR_NAME=row.AGR_NAME, OBJECT=row.OBJECT, FIELD=row.FIELD,
                LOW=row.LOW, HIGH=row.HIGH, CLASSIFY_LIC=classify_lic, MATCH_TYPE=match_type,
            ))
            if len(batch) >= 500:
                db.bulk_save_objects(batch)
                db.flush()
                batch.clear()

        if batch:
            db.bulk_save_objects(batch)

        db.commit()
        count = db.query(RoleLicModel).count()
        logger.info(f"[Stage 2] Done — {count} rows written to RoleLic")
        return {"status": "success", "rows_written": count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Stage 2] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# STAGE 3 — RoleLicSummary
# ════════════════════════════════════════════════════════════════════════════

@router.post("/fue/{system_name}/compute/rolelicsummary")
async def compute_rolelicsummary(system_name: str, db: Session = Depends(get_db)):
    """Stage 3 — Populate RoleLicSummary from RoleLic + AGRDefine."""
    logger.info(f"[Stage 3] Computing RoleLicSummary for {system_name}")
    try:
        RoleLicModel = create_role_lic_model(system_name)
        AGRDefineModel = create_AGRDEFINE_model(system_name)
        RoleLicSummaryModel = create_role_lic_summary_model(system_name)

        active_connection = db.get_bind()
        AGRDefineModel.__table__.create(bind=active_connection, checkfirst=True)
        RoleLicModel.__table__.create(bind=active_connection, checkfirst=True)
        RoleLicSummaryModel.__table__.create(bind=active_connection, checkfirst=True)

        role_groups = defaultdict(list)
        for row in db.query(RoleLicModel).all():
            role_groups[row.AGR_NAME].append(row.CLASSIFY_LIC)

        define_map = {
            row.AGR_NAME: (row.TEXT, row.PARENT_AGR)
            for row in db.query(AGRDefineModel).all()
        }

        db.query(RoleLicSummaryModel).delete()
        db.flush()

        batch = []
        for agr_name, licenses in role_groups.items():
            final_license = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))
            text, parent_agr = define_map.get(agr_name, (None, None))

            batch.append(RoleLicSummaryModel(
                AGR_NAME=agr_name, TEXT=text, PARENT_AGR=parent_agr,
                CLASSIFY_LIC=final_license, TOTAL_OBJ=len(licenses),
                GB_COUNT=licenses.count('GB Advanced Use'),
                GC_COUNT=licenses.count('GC Core Use'),
                GD_COUNT=licenses.count('GD Self-Service Use'),
                NC_COUNT=licenses.count('Not Classified'),
            ))
            if len(batch) >= 500:
                db.bulk_save_objects(batch)
                db.flush()
                batch.clear()

        if batch:
            db.bulk_save_objects(batch)

        db.commit()
        count = db.query(RoleLicSummaryModel).count()
        logger.info(f"[Stage 3] Done — {count} rows written to RoleLicSummary")
        return {"status": "success", "rows_written": count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Stage 3] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# STAGE 4 — UserRoleLic
# ════════════════════════════════════════════════════════════════════════════

@router.post("/fue/{system_name}/compute/userrolellic")
async def compute_userrolellic(system_name: str, db: Session = Depends(get_db)):
    """Stage 4 — Populate UserRoleLic from AGRUsers + RoleLicSummary."""
    logger.info(f"[Stage 4] Computing UserRoleLic for {system_name}")
    try:
        AGRUsersModel = create_AGRUSERS_model(system_name)
        RoleLicSummaryModel = create_role_lic_summary_model(system_name)
        UserRoleLicModel = create_user_lic_model(system_name)

        active_connection = db.get_bind()
        AGRUsersModel.__table__.create(bind=active_connection, checkfirst=True)
        UserRoleLicModel.__table__.create(bind=active_connection, checkfirst=True)
        RoleLicSummaryModel.__table__.create(bind=active_connection, checkfirst=True)

        role_license_map = {
            row.AGR_NAME: row.CLASSIFY_LIC
            for row in db.query(RoleLicSummaryModel).all()
        }

        db.query(UserRoleLicModel).delete()
        db.flush()

        batch = []
        for row in db.query(AGRUsersModel).all():
            license = role_license_map.get(row.AGR_NAME, 'Not Classified')
            batch.append(UserRoleLicModel(
                UNAME=row.UNAME, AGR_NAME=row.AGR_NAME, CLASSIFY_LIC=license,
            ))
            if len(batch) >= 500:
                db.bulk_save_objects(batch)
                db.flush()
                batch.clear()

        if batch:
            db.bulk_save_objects(batch)

        db.commit()
        count = db.query(UserRoleLicModel).count()
        logger.info(f"[Stage 4] Done — {count} rows written to UserRoleLic")
        return {"status": "success", "rows_written": count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Stage 4] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# STAGE 5 — UserLicSummary   ← ALL 3 BUGS FIXED HERE
# ════════════════════════════════════════════════════════════════════════════

def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse SAP date strings into Python date objects.

    Handles all formats seen in this system:
      DD-MM-YYYY   e.g. '29-01-2025'  ← actual format in USR02
      DD-MM-9999   e.g. '31-12-9999'  ← SAP 'never expires' sentinel
      YYYYMMDD     e.g. '20250129'    ← classic SAP format
      YYYY-MM-DD   e.g. '2025-01-29'  ← ISO format

    Returns None for blank, zero-date, or unparseable strings.
    Returns None for '31-12-9999' / '9999-12-31' sentinel (treated as no expiry).
    """
    if not date_str:
        return None

    s = str(date_str).strip()

    # Blank or SAP zero-date
    if s in ('', '00000000', '0000-00-00', '00-00-0000'):
        return None

    # SAP "never expires" sentinel — treat as no expiry (not expired)
    if '9999' in s:
        return None

    # Try all known formats
    for fmt in ('%d-%m-%Y', '%Y%m%d', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    return None


@router.post("/fue/{system_name}/compute/userlicsummary")
async def compute_userlicsummary(system_name: str, db: Session = Depends(get_db)):
    """Stage 5 — Populate UserLicSummary from UserRoleLic + USR02 + TransactionUsage."""
    logger.info(f"[Stage 5] Computing UserLicSummary for {system_name}")
    try:
        UserRoleLicModel = create_user_lic_model(system_name)
        USR02Model = create_USR02_model(system_name)
        TxUsageModel = create_TRANSACTIONUSAGE_model(system_name)
        UserLicSummaryModel = create_user_lic_summary_model(system_name)

        # today = date.today()
        today = date.today() - timedelta(days=1)


        active_connection = db.get_bind()
        USR02Model.__table__.create(bind=active_connection, checkfirst=True)
        UserRoleLicModel.__table__.create(bind=active_connection, checkfirst=True)
        UserLicSummaryModel.__table__.create(bind=active_connection, checkfirst=True)
        TxUsageModel.__table__.create(bind=active_connection, checkfirst=True)

        # Step 1: Group licenses per user from UserRoleLic
        user_licenses = defaultdict(list)
        for row in db.query(UserRoleLicModel).all():
            user_licenses[row.UNAME].append(row.CLASSIFY_LIC)

        # Step 2: USR02 lookup — keyed by BNAME
        usr02_map = {row.BNAME: row for row in db.query(USR02Model).all()}

        # Step 3: Last activity from TransactionUsage
        # _TRANSACTIONUSAGE model has: TRANSACTION, PROGRAM, USER — no DATE column.
        # If a DATE column is added to the model and CSV later, plug it in here.
        last_activity: dict = {}

        # Step 4: Compute per-user summary
        db.query(UserLicSummaryModel).delete()
        db.flush()

        # batch = []
        # for BNAME, licenses in user_licenses.items():
        #     # Most restrictive license wins (lowest LICENSE_PRIORITY step)
        #     final_license = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))
        #
        #     # USR02 attributes
        #     usr = usr02_map.get(BNAME)
        #     uflag = str(usr.UFLAG).strip() if usr and usr.UFLAG is not None else None
        #     trdat = usr.TRDAT if usr else None
        #     erdat = usr.ERDAT if usr else None
        #     gltgb = usr.GLTGB if usr else None
        #     ustyp = usr.USTYP if usr else None
        #
        #     # ── Dormancy ────────────────────────────────────────────────────
        #     # Preferred: TransactionUsage DATE (not yet available)
        #     # Fallback:  TRDAT (last logon) → ERDAT (creation date)
        #     # _parse_date now handles DD-MM-YYYY format correctly
        #     last_used_date = last_activity.get(BNAME)
        #     if last_used_date is None:
        #         last_used_date = _parse_date(trdat) or _parse_date(erdat)
        #
        #     dormant_days = (today - last_used_date).days if last_used_date else None
        #     last_used_str = last_used_date.strftime('%d-%m-%Y') if last_used_date else None
        #
        #     flag_90 = dormant_days is not None and dormant_days >= 90
        #     flag_180 = dormant_days is not None and dormant_days >= 180
        #
        #     # ── Expiry ──────────────────────────────────────────────────────
        #     # GLTGB '31-12-9999' = never expires → _parse_date returns None → expired=False
        #     # GLTGB '29-01-2025' = past date     → expired=True
        #     gltgb_date = _parse_date(gltgb)
        #     expired = (gltgb_date is not None) and (gltgb_date < today)
        #
        #     # ── Locked ──────────────────────────────────────────────────────
        #     # SAP UFLAG bitmask: 0=active, 64=admin lock, 128=wrong pwd lock,
        #     # 192=both (64+128), 32=CUA lock.
        #     # Treat ONLY 0 as unlocked. Everything else = locked.
        #     # try:
        #     #     uflag_int = int(float(uflag)) if uflag is not None else 0
        #     # except (ValueError, TypeError):
        #     #     uflag_int = 0
        #     # locked = uflag_int != 0  # only UFLAG=0 is truly active
        #     #
        #     # # ── License override ────────────────────────────────────────────
        #     # # Algorithm: override to NC only when BOTH expired AND locked
        #     # if expired and locked:
        #     #     final_license = 'Not Classified'
        #     #
        #     # # ── Cleanup category ────────────────────────────────────────────
        #     # if expired and locked:
        #     #     cleanup = 'Expired & Locked'
        #     # elif locked and not expired:
        #     #     cleanup = 'Locked but not Expired'  # keeps real license
        #     # elif expired and not locked:
        #     #     cleanup = 'Expired but Not Locked'  # keeps real license
        #     # elif flag_180:
        #     #     cleanup = 'Dormant 180+'
        #     # elif flag_90:
        #     #     cleanup = 'Dormant 90+'
        #     # else:
        #     #     cleanup = None
        #     #
        #     # batch.append(UserLicSummaryModel(
        #     #     UNAME=BNAME,
        #     #     CLASSIFY_LIC=final_license,
        #     #     UFLAG=uflag,
        #     #     TRDAT=trdat,
        #     #     ERDAT=erdat,
        #     #     USTYP=ustyp,
        #     #     LAST_USED=last_used_str,
        #     #     DORMANT_DAYS=dormant_days,
        #     #     FLAG_90=flag_90,
        #     #     FLAG_180=flag_180,
        #     #     LOCKED=locked,
        #     #     CLEANUP_CATEGORY=cleanup,
        #     # ))
        #
        #     try:
        #         uflag_int = int(float(uflag)) if uflag is not None else 0
        #     except (ValueError, TypeError):
        #         uflag_int = 0
        #     locked = (uflag_int != 0) and (uflag_int != 128)  # ← KEY FIX
        #
        #     # ── Expiry ──────────────────────────────────────────────────────
        #     gltgb_date = _parse_date(gltgb)
        #     expired = (gltgb_date is not None) and (gltgb_date < today)
        #
        #     # ── Dormancy ────────────────────────────────────────────────────
        #     last_used_date = last_activity.get(BNAME)
        #     if last_used_date is None:
        #         last_used_date = _parse_date(trdat) or _parse_date(erdat)
        #
        #     dormant_days = (today - last_used_date).days if last_used_date else None
        #     last_used_str = last_used_date.strftime('%d-%m-%Y') if last_used_date else None
        #
        #     # Per spec: ≥180 sets BOTH flags
        #     flag_90 = dormant_days is not None and dormant_days >= 90
        #     flag_180 = dormant_days is not None and dormant_days >= 180
        #     # flag_90 is already True whenever flag_180 is True (180 ≥ 90), so no change needed
        #
        #     # ── License override (Step 8) ───────────────────────────────────
        #     # Override to NC only when BOTH expired AND locked
        #     if expired and locked:
        #         final_license = 'Not Classified'
        #
        #     # ── Cleanup Category (Step 9) ───────────────────────────────────
        #     if expired and locked:
        #         cleanup = 'Expired & Locked'
        #     elif expired and not locked:
        #         cleanup = 'Expired but Not Locked'
        #     elif locked and not expired:
        #         cleanup = 'Locked but not Expired'
        #     elif flag_90 or flag_180:  # ← was missing "Dormant" bucket
        #         cleanup = 'Dormant'
        #     else:
        #         cleanup = None
        #
        #     batch.append(UserLicSummaryModel(
        #         UNAME=BNAME,
        #         CLASSIFY_LIC=final_license,
        #         UFLAG=uflag,
        #         TRDAT=trdat,
        #         ERDAT=erdat,
        #         GLTGB=gltgb,  # store for reference
        #         USTYP=ustyp,
        #         LAST_USED=last_used_str,
        #         DORMANT_DAYS=dormant_days,
        #         FLAG_90=flag_90,
        #         FLAG_180=flag_180,
        #         EXPIRED_FLAG=expired,  # ← add to model if not present
        #         LOCKED_FLAG=locked,  # ← rename from LOCKED if needed
        #         LOCKED=locked,  # keep if existing columns depend on it
        #         CLEANUP_CATEGORY=cleanup,
        #     ))
        #
        #     if len(batch) >= 500:
        #         db.bulk_save_objects(batch)
        #         db.flush()
        #         batch.clear()

        batch = []
        for BNAME, licenses in user_licenses.items():

            # Step 1+2: Most restrictive license (lowest priority step)
            final_license = min(licenses, key=lambda x: LICENSE_PRIORITY.get(x, 999))

            # Step 3: Fetch USR02 attributes
            usr = usr02_map.get(BNAME)
            uflag = str(usr.UFLAG).strip() if usr and usr.UFLAG is not None else None
            trdat = usr.TRDAT if usr else None
            erdat = usr.ERDAT if usr else None
            gltgv = usr.GLTGV if usr else None  # ← NOW FETCHED
            gltgb = usr.GLTGB if usr else None
            ustyp = usr.USTYP if usr else None

            # Step 4: Expired — GLTGB < Today AND GLTGB not blank
            gltgb_date = _parse_date(gltgb)
            expired = (gltgb_date is not None) and (gltgb_date < today)

            # Step 5: Locked — UFLAG ≠ 0 AND UFLAG ≠ 128
            try:
                uflag_int = int(float(uflag)) if uflag is not None else 0
            except (ValueError, TypeError):
                uflag_int = 0
            locked = (uflag_int != 0) and (uflag_int != 128)

            # Step 6: Dormant days — TRDAT preferred, ERDAT fallback
            last_used_date = last_activity.get(BNAME)
            if last_used_date is None:
                last_used_date = _parse_date(trdat) or _parse_date(erdat)

            dormant_days = (today - last_used_date).days if last_used_date else None
            last_used_str = last_used_date.strftime('%d-%m-%Y') if last_used_date else None

            # Step 7: Dormant flags

            flag_90 = dormant_days is not None and dormant_days >= 90
            flag_180 = dormant_days is not None and dormant_days >= 180

            # Step 8: License override — only when BOTH expired AND locked
            if expired and locked:
                final_license = 'Not Classified'

            # Step 9: Cleanup category
            if expired and locked:
                cleanup = 'Expired & Locked'
            elif expired and not locked:
                cleanup = 'Expired but Not Locked'
            elif locked and not expired:
                cleanup = 'Locked but not Expired'
            elif flag_90 or flag_180:
                cleanup = 'Dormant'
            else:
                cleanup = None

            batch.append(UserLicSummaryModel(
                UNAME=BNAME,
                GLTGV=gltgv,  # ← added
                GLTGB=gltgb,  # ← added
                CLASSIFY_LIC=final_license,
                UFLAG=uflag,
                TRDAT=trdat,
                ERDAT=erdat,
                USTYP=ustyp,
                LAST_USED=last_used_str,
                DORMANT_DAYS=dormant_days,
                FLAG_90=flag_90,
                FLAG_180=flag_180,
                EXPIRED_FLAG=expired,  # ← added
                LOCKED_FLAG=locked,  # ← added (rename LOCKED to LOCKED_FLAG)
                CLEANUP_CATEGORY=cleanup,
            ))

            if len(batch) >= 500:
                db.bulk_save_objects(batch)
                db.flush()
                batch.clear()

        if batch:
            db.bulk_save_objects(batch)

        db.commit()
        count = db.query(UserLicSummaryModel).count()
        try:
            FUE_FACTORS = {
                'GB Advanced Use': 1.0,
                'GC Core Use': 0.2,
                'GD Self-Service Use': 0.0333,
            }
            from collections import Counter
            lic_counts = Counter()
            for row in db.query(UserLicSummaryModel).all():
                lic_counts[row.CLASSIFY_LIC or 'Not Classified'] += 1

            gb = lic_counts.get('GB Advanced Use', 0)
            gc = lic_counts.get('GC Core Use', 0)
            gd = lic_counts.get('GD Self-Service Use', 0)
            nc = lic_counts.get('Not Classified', 0)

            gb_fue = math.ceil(gb * FUE_FACTORS['GB Advanced Use'])
            gc_fue = math.ceil(gc * FUE_FACTORS['GC Core Use'])
            gd_fue = math.ceil(gd * FUE_FACTORS['GD Self-Service Use'])
            total_fue = gb_fue + gc_fue + gd_fue

            year_month = datetime.now().strftime('%Y-%m')

            # Create table if needed
            FUEHistory.__table__.create(bind=db.get_bind(), checkfirst=True)

            history_row = FUEHistory(
                SYSTEM_NAME=system_name,
                SNAPSHOT_DATE=datetime.now(),
                YEAR_MONTH=year_month,
                GB_USERS=gb,
                GC_USERS=gc,
                GD_USERS=gd,
                NC_USERS=nc,
                TOTAL_USERS=gb + gc + gd + nc,
                GB_FUE=gb_fue,
                GC_FUE=gc_fue,
                GD_FUE=gd_fue,
                TOTAL_FUE=total_fue,
            )
            db.add(history_row)
            db.commit()
            logger.info(f"[Stage 5] FUE history snapshot saved: {year_month} → total_fue={total_fue}")
        except Exception as e:
            logger.error(f"[Stage 5] Failed to save FUE history: {e}", exc_info=True)
            # Don't fail the main compute for this

        return {"status": "success", "rows_written": count}
        # logger.info(f"[Stage 5] Done — {count} rows written to UserLicSummary")
        # return {"status": "success", "rows_written": count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Stage 5] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# CONVENIENCE — Run all stages sequentially
# ════════════════════════════════════════════════════════════════════════════

@router.post("/fue/{system_name}/compute/all")
async def compute_all_stages(system_name: str, db: Session = Depends(get_db)):
    """Run Stage 2 → 3 → 4 → 5 in order."""
    results = {}
    for name, fn in [
        ("rolelic", compute_rolelic),
        ("rolelicsummary", compute_rolelicsummary),
        ("userrolellic", compute_userrolellic),
        ("userlicsummary", compute_userlicsummary),
    ]:
        result = await fn(system_name=system_name, db=db)
        results[name] = result
    return {"status": "success", "stages": results}


# ── FUE Factors ──────────────────────────────────────────────────────────────
FUE_FACTORS = {
    'GB Advanced Use': 1.0,
    'GC Core Use': 0.2,
    'GD Self-Service Use': 0.0333,
    'Not Classified': 0.0,
}


# ════════════════════════════════════════════════════════════════════════════
# STAGE 6 — FUE Dashboard    ← FIX 4 here (locked_count logic)
# ════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════
# FUE Factors
# ════════════════════════════════════════════════════════════════════════════
FUE_FACTORS = {
    'GB Advanced Use':     1.0,
    'GC Core Use':         0.2,
    'GD Self-Service Use': 0.0333,
    'Not Classified':      0.0,
}

# Canonical display order for all license breakdowns
LICENSE_ORDER = ['GB Advanced Use', 'GC Core Use', 'GD Self-Service Use', 'Not Classified']


def _build_license_breakdown(counter: dict) -> list:
    """
    Given {license: count}, returns a list of dicts with count + FUE
    in canonical order, only including licenses that have count > 0.
    """
    result = []
    for lic in LICENSE_ORDER:
        count = counter.get(lic, 0)
        if count == 0:
            continue
        fue = math.ceil(count * FUE_FACTORS.get(lic, 0.0))
        result.append({
            "category": lic,
            "count":    count,
            "fue":      fue,
        })
    return result


# ════════════════════════════════════════════════════════════════════════════
# STAGE 6 — FUE Dashboard (full breakdown matching the reference output)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/fue/{system_name}/dashboard")
async def get_fue_dashboard(system_name: str, db: Session = Depends(get_db)):
    """
    Returns all 6 dashboard sections:

      1. user_license_distribution   — all users, grouped by final license
      2. role_license_distribution   — all roles, grouped by CLASSIFY_LIC
      3. dormant_90                  — users dormant >= 90 days, by license
      4. dormant_180                 — users dormant >= 180 days, by license
      5. expired_not_locked          — CLEANUP_CATEGORY = 'Expired but Not Locked'
      6. locked_not_expired          — CLEANUP_CATEGORY = 'Locked but not Expired'

    Each section has a per-license breakdown (category, count, fue) plus
    section-level totals (total_count, total_fue).
    """
    logger.info(f"[Stage 6] Fetching FUE Dashboard for {system_name}")
    try:
        UserLicSummaryModel = create_user_lic_summary_model(system_name)
        RoleLicSummaryModel = create_role_lic_summary_model(system_name)

        # ── Load all user summary rows once ─────────────────────────────────
        users = db.query(UserLicSummaryModel).all()

        # Counters for each section — keyed by license string
        user_lic_counter     = defaultdict(int)   # section 1
        dormant_90_counter   = defaultdict(int)   # section 3
        dormant_180_counter  = defaultdict(int)   # section 4
        expired_nl_counter   = defaultdict(int)   # section 5: expired but not locked
        locked_ne_counter    = defaultdict(int)   # section 6: locked but not expired

        for user in users:
            lic     = user.CLASSIFY_LIC or 'Not Classified'
            cleanup = getattr(user, 'CLEANUP_CATEGORY', None)

            # Section 1 — all users
            user_lic_counter[lic] += 1

            # Section 3 — dormant >= 90 days
            if getattr(user, 'FLAG_90', False):
                dormant_90_counter[lic] += 1

            # Section 4 — dormant >= 180 days
            if getattr(user, 'FLAG_180', False):
                dormant_180_counter[lic] += 1

            # Section 5 — expired but not locked (keep their real license)
            if cleanup == 'Expired but Not Locked':
                expired_nl_counter[lic] += 1

            # Section 6 — locked but not expired (keep their real license)
            if cleanup == 'Locked but not Expired':
                locked_ne_counter[lic] += 1

        # ── Section 2 — Role license distribution ───────────────────────────
        # Comes from RoleLicSummary, not UserLicSummary
        role_lic_counter = defaultdict(int)
        roles = db.query(RoleLicSummaryModel).all()
        for role in roles:
            lic = role.CLASSIFY_LIC or 'Not Classified'
            role_lic_counter[lic] += 1

        # ── Helper: build section totals ────────────────────────────────────
        def _section(counter: dict) -> dict:
            breakdown   = _build_license_breakdown(counter)
            total_count = sum(r["count"] for r in breakdown)
            total_fue   = sum(r["fue"]   for r in breakdown)
            return {
                "breakdown":   breakdown,
                "total_count": total_count,
                "total_fue":   total_fue,
            }

        def _section_no_fue(counter: dict) -> dict:
            """For role distribution — roles don't have a FUE count."""
            result = []
            total  = 0
            for lic in LICENSE_ORDER:
                count = counter.get(lic, 0)
                if count == 0:
                    continue
                result.append({"category": lic, "count": count})
                total += count
            return {"breakdown": result, "total_count": total}

        return {
            # ── Section 1 ───────────────────────────────────────────────────
            "user_license_distribution": _section(user_lic_counter),

            # ── Section 2 ───────────────────────────────────────────────────
            "role_license_distribution": _section_no_fue(role_lic_counter),

            # ── Section 3 ───────────────────────────────────────────────────
            "dormant_90": _section(dormant_90_counter),

            # ── Section 4 ───────────────────────────────────────────────────
            "dormant_180": _section(dormant_180_counter),

            # ── Section 5 ───────────────────────────────────────────────────
            "expired_not_locked": _section(expired_nl_counter),

            # ── Section 6 ───────────────────────────────────────────────────
            "locked_not_expired": _section(locked_ne_counter),
        }

    except Exception as e:
        logger.error(f"[Stage 6] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from app.models.fue_history import FUEHistory
from sqlalchemy import func as sqla_func

@router.get("/fue/{system_name}/history")
async def get_fue_history(system_name: str, db: Session = Depends(get_db)):
    """Returns monthly averaged FUE for last 12 months for trend chart."""
    try:
        FUEHistory.__table__.create(bind=db.get_bind(), checkfirst=True)

        # Average per YEAR_MONTH in case multiple snapshots exist in same month
        rows = (
            db.query(
                FUEHistory.YEAR_MONTH,
                sqla_func.avg(FUEHistory.GB_FUE).label("gb_fue"),
                sqla_func.avg(FUEHistory.GC_FUE).label("gc_fue"),
                sqla_func.avg(FUEHistory.GD_FUE).label("gd_fue"),
                sqla_func.avg(FUEHistory.TOTAL_FUE).label("total_fue"),
            )
            .filter(FUEHistory.SYSTEM_NAME == system_name)
            .group_by(FUEHistory.YEAR_MONTH)
            .order_by(FUEHistory.YEAR_MONTH.desc())
            .limit(12)
            .all()
        )

        # Return in ascending order for chart
        result = [
            {
                "month":     row.YEAR_MONTH,
                "gb_fue":    round(row.gb_fue or 0),
                "gc_fue":    round(row.gc_fue or 0),
                "gd_fue":    round(row.gd_fue or 0),
                "total_fue": round(row.total_fue or 0),
            }
            for row in reversed(rows)
        ]
        return {"system_name": system_name, "history": result}

    except Exception as e:
        logger.error(f"FUE history fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

