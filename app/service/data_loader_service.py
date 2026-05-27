import csv
from io import BytesIO
from sqlalchemy.orm import Session
from app.core.logger import setup_logger, get_daily_log_filename
from app.models.dynamic_models import (

    ensure_table_exists,
    # create_auth_obj_field_lic_data,
    create_AGRDEFINE_model, create_AGRAGRS_model, create_USR02_model,
    create_TRANSACTIONUSAGE_model, create_AGR1251_model, create_AGRUSERS_model, create_TSTCT_model, create_FLPCA_model,
    create_USOBXC_model, create_TOBJL_model
)
from app.models.database import engine


logger = setup_logger("app_logger")
class DataLoaderError(Exception):
    pass


async def load_agr1251_from_csv_upload(db: Session, csv_file,system_name: str):
    """Parses Role Auth CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        print(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting CSV data load for system: {system_name}")


    DynamicAGR1251Model = create_AGR1251_model(system_name) # Pass system_name
    table_name = DynamicAGR1251Model.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicAGR1251Model)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicAGR1251Model).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
        print(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    objects_to_load = []
    try:
        csv_content = csv_file.read()

        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
                logger.debug("Successfully decoded CSV content with 'utf-8-sig'.")

            except UnicodeDecodeError:

                csv_text = BytesIO(csv_content).read().decode('cp1252')
                logger.debug("Successfully decoded CSV content with 'cp1252'.")

        csv_reader = csv.reader(csv_text.splitlines())
        headers = ['agr_name', 'object','field', 'low', 'high','obj-status']
        next(csv_reader)


        field_map = {
            'AGR_NAME': 0,
            'OBJECT': 1,
            'FIELD': 2,
            'LOW': 3,
            'HIGH': 4,
            'OBJ_STATUS':5
        }

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                auth_data_obj = DynamicAGR1251Model(**obj_data)
                objects_to_load.append(auth_data_obj)
            except IndexError as e:
                logger.error(f"Error processing row {i+2} in CSV data: Not enough columns. Row: {row}")
                print(f"Error processing row {i+2} in CSV data: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i+2}: Not enough columns.")
            except Exception as row_e:
                print(f"Error processing row {i+2} in CSV data: {row_e}")
                print(f"Row data: {row}")
                logger.error(f"Error processing row {i+2} in CSV data: {row_e}")
                raise DataLoaderError(f"Error processing row {i+2}: {row_e}")

        if not objects_to_load:
            logger.warning(f"Warning: No data rows found in CSV data.")
            print(f"Warning: No data rows found in CSV data.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        print(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")



async def load_agrusers_from_csv_upload(db: Session, csv_file,system_name: str):
    """Parses Role Auth CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        print(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting CSV data load for system: {system_name}")


    DynamicAGRUSERModel = create_AGRUSERS_model(system_name) # Pass system_name
    table_name = DynamicAGRUSERModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicAGRUSERModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicAGRUSERModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
        print(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    objects_to_load = []
    try:
        csv_content = csv_file.read()

        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
                logger.debug("Successfully decoded CSV content with 'utf-8-sig'.")

            except UnicodeDecodeError:

                csv_text = BytesIO(csv_content).read().decode('cp1252')
                logger.debug("Successfully decoded CSV content with 'cp1252'.")

        csv_reader = csv.reader(csv_text.splitlines())
        headers = ['agr_name','uname']
        next(csv_reader)
        field_map = {
            'AGR_NAME': 0,
            'UNAME' :1
        }

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                auth_data_obj = DynamicAGRUSERModel(**obj_data)
                objects_to_load.append(auth_data_obj)
            except IndexError as e:
                logger.error(f"Error processing row {i+2} in CSV data: Not enough columns. Row: {row}")
                print(f"Error processing row {i+2} in CSV data: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i+2}: Not enough columns.")
            except Exception as row_e:
                print(f"Error processing row {i+2} in CSV data: {row_e}")
                print(f"Row data: {row}")
                logger.error(f"Error processing row {i+2} in CSV data: {row_e}")
                raise DataLoaderError(f"Error processing row {i+2}: {row_e}")

        if not objects_to_load:
            logger.warning(f"Warning: No data rows found in CSV data.")
            print(f"Warning: No data rows found in CSV data.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        print(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_agrdefine_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses AGR_DEFINE CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting AGR_DEFINE CSV data load for system: {system_name}")

    DynamicAGRDEFINEModel = create_AGRDEFINE_model(system_name)
    table_name = DynamicAGRDEFINEModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicAGRDEFINEModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicAGRDEFINEModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: AGR_NAME, PARENT_AGR, TEXT
    field_map = {
        'AGR_NAME': 0,
        'PARENT_AGR': 1,
        'TEXT': 2,
    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicAGRDEFINEModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in AGR_DEFINE CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading AGR_DEFINE CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_agragrs_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses AGR_AGRS CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting AGR_AGRS CSV data load for system: {system_name}")

    DynamicAGRAGRSModel = create_AGRAGRS_model(system_name)
    table_name = DynamicAGRAGRSModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicAGRAGRSModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicAGRAGRSModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: DERIVED_ROLE, MASTER_ROLE, TEXT
    field_map = {
        'COMPOSITE_ROLE': 0,
        'ROLE': 1,
        'ACTIVE': 2,
    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicAGRAGRSModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in AGR_AGRS CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading AGR_AGRS CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_usr02_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses USR02 CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting USR02 CSV data load for system: {system_name}")

    DynamicUSR02Model = create_USR02_model(system_name)
    table_name = DynamicUSR02Model.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicUSR02Model)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicUSR02Model).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: COMP_ROLE, ROLE
    field_map = {
        'BNAME': 0,
        'GLTGV': 1,
        'GLTGB': 2,
        'UFLAG': 3,
        'ERDAT':4,
        'TRDAT':5,
        'USTYP':6

    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicUSR02Model(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in USR02 CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading USR02 CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_transactionusage_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses TRANSACTION_USAGE CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting TRANSACTION_USAGE CSV data load for system: {system_name}")

    DynamicTUSAGEModel = create_TRANSACTIONUSAGE_model(system_name)
    table_name = DynamicTUSAGEModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicTUSAGEModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicTUSAGEModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: TRANSACTION, PROGRAM, USER
    field_map = {
        'TRANSACTION': 0,
        'PROGRAM': 1,
        'USER': 2,
    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicTUSAGEModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in TRANSACTION_USAGE CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading TRANSACTION_USAGE CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_tstct_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses TSTCT CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting TSTCT CSV data load for system: {system_name}")

    DynamicTSTCTModel = create_TSTCT_model(system_name)
    table_name = DynamicTSTCTModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicTSTCTModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicTSTCTModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: TRANSACTION, PROGRAM, USER
    field_map = {
        'TCODE': 0,
        'TRANSACTION_TEXT': 1

    }


    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicTSTCTModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in TRANSACTION_USAGE CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading TRANSACTION_USAGE CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_flpca_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses FLPCA CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting FLPCA CSV data load for system: {system_name}")

    DynamicFLPCAModel= create_FLPCA_model(system_name)
    table_name = DynamicFLPCAModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicFLPCAModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicFLPCAModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: TRANSACTION, PROGRAM, USER
    field_map = {
    'Single_Role_Name':0,
    'Single_Role_Description':1,
    'Catalog_ID':2,
    'Semantic_Object':3,
    'Action':4,
    'Title_Subtitle_Information':5,
    'Application_Type':6,
    'SAP_Fiori_ID':7,
    'Transaction':8,
    'Tile_Title':9,
    'Target_Mapping_Title':10,
    'OData_v2_Service_Name':11,
    'OData_v2_Service_Status':12,
    'OData_v4_Service_Name':13,
    'OData_v4_Service_Status':14


    }


    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicFLPCAModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in FLPCA CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading FLPCA CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")


async def load_usobxc_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses USOBXC CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting USOBXC  CSV data load for system: {system_name}")

    DynamicUSOBXCModel = create_USOBXC_model(system_name)
    table_name = DynamicUSOBXCModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicUSOBXCModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicUSOBXCModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: TRANSACTION, PROGRAM, USER
    field_map = {
    'NAME':0,
    'PROPOSED_VALUE_FOR':1,
    'AUTH_OBJ':2,
    'OKFLAG':3
    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicUSOBXCModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in DynamicUSOBXCModel CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading USOBXC Model CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")





async def load_objText_from_csv_upload(db: Session, csv_file, system_name: str):
    """Parses TOBJL CSV from a file-like object, ensures table exists, truncates, and loads data."""
    if not csv_file:
        logger.info(f"Skipping CSV data load for system: {system_name} as no file was provided.")
        return {"message": "No CSV file provided, skipping load.", "table_name": None, "records_loaded": 0}

    logger.info(f"Starting TOBJL  CSV data load for system: {system_name}")

    DynamicTOBJLModel = create_TOBJL_model(system_name)
    table_name = DynamicTOBJLModel.__tablename__
    engine = db.bind
    ensure_table_exists(engine, DynamicTOBJLModel)
    logger.debug(f"Dynamic model and table '{table_name}' for system '{system_name}' created/verified.")

    try:
        deleted_count = db.query(DynamicTOBJLModel).delete()
        logger.info(f"Truncated (deleted) {deleted_count} rows from {table_name}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to truncate table {table_name}: {e}", exc_info=True)
        raise DataLoaderError(f"Failed to truncate table {table_name}: {e}")

    # Expected CSV columns: TRANSACTION, PROGRAM, USER
    field_map = {
    'AUTH_OBJ':0,
        'TEXT':1
    }

    objects_to_load = []
    try:
        csv_content = csv_file.read()
        try:
            csv_text = BytesIO(csv_content).read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                csv_text = BytesIO(csv_content).read().decode('latin-1')
            except UnicodeDecodeError:
                csv_text = BytesIO(csv_content).read().decode('cp1252')

        csv_reader = csv.reader(csv_text.splitlines())
        next(csv_reader)  # skip header row

        for i, row in enumerate(csv_reader):
            try:
                obj_data = {model_field: row[csv_index]
                            for model_field, csv_index in field_map.items()}
                objects_to_load.append(DynamicTOBJLModel(**obj_data))
            except IndexError:
                logger.error(f"Row {i + 2}: Not enough columns. Row: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: Not enough columns.")
            except Exception as row_e:
                logger.error(f"Row {i + 2}: {row_e}. Row data: {row}")
                raise DataLoaderError(f"Error processing row {i + 2}: {row_e}")

        if not objects_to_load:
            logger.warning("No data rows found in DynamicTOBJLModel CSV.")

        db.add_all(objects_to_load)
        db.commit()
        msg = f"Successfully loaded {len(objects_to_load)} records into {table_name}"
        logger.info(msg)
        return {"message": msg, "table_name": table_name, "records_loaded": len(objects_to_load)}

    except DataLoaderError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed loading DynamicTOBJLModel Model CSV data: {e}")
        raise DataLoaderError(f"Failed loading CSV data: {e}")






