import re
import uuid
from app.core.logger import setup_logger
import nullable
from sqlalchemy import (
    Column, String, Integer, MetaData, Table, inspect as sqla_inspect, NotNullable, Boolean
)
from app.models.database import Base, engine
logger = setup_logger("app_logger")


def clean_system_name(system_name: str) -> str:
    """Cleans the client name to be suitable for a table name prefix."""
    logger.debug(f"Received system_name: '{system_name}'")
    return re.sub(r'\W+', '', system_name.replace(' ', '_')).upper()


def clean_system_release_versionInfo(system_release_version: str) -> str:
    """Cleans the client name to be suitable for a table name prefix."""
    logger.debug(f"Received system_release_versionInfo: '{system_release_version}'")
    return re.sub(r'\W+', '', system_release_version.replace(' ', '_')).upper()





def get_agr_1251_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated role auth table agr_1251_name for system '{system_name}'")
    return f"Z_FUE_{system}_ROLE_AUTH_INFO"

def get_agr_users_tablename(system_name:str) -> str:
    system = clean_system_name(system_name)
    logger.info(f"Generated user role mapping agr_users table name for system '{system_name}'")
    return f"Z_FUE_{system}_USER_ROLE_MAPPING"

def get_agr_define_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated parent child role mapping table name for system '{system_name}'")
    return f"Z_FUE_{system}_PARENT_CHILD_ROLE_MAPPING"

def get_agr_agrs_tablename(system_name:str) -> str:
    system = clean_system_name(system_name)
    logger.info(f"Generated Composite roles data table name for system '{system_name}'")
    return f"Z_FUE_{system}_COMPOSITE_ROLE_DATA"

def get_usr02_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated USER_DATA table name for system '{system_name}'")
    return f"Z_FUE_{system}_USER_DATA"

def get_transaction_usage_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated transaction_usage_data table name for system '{system_name}'")
    return f"Z_FUE_{system}_TRANSACTION_USAGE"


def get_flpca_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated flpca table name for system '{system_name}'")
    return f"Z_FUE_{system}_FIORI DATA"

def get_tcode_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated tcode text data name for system '{system_name}'")
    return f"Z_FUE_{system}_TCODE_TEXT DATA"

def get_usobxC_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated tcode text data name for system '{system_name}'")
    return f"Z_FUE_{system}_USOBX_C DATA"


def get_obj_text_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated tcode text data name for system '{system_name}'")
    return f"Z_FUE_{system}_OBJ_TEXT DATA"

def get_role_lice_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated role object license info table name for system '{system_name}'")
    return f"Z_FUE_{system}_ROLE_OBJ_LICENSE_INFO"

def get_role_lice_data_summary_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated role license summary info table name for system '{system_name}'")
    return f"Z_FUE_{system}_ROLE_LICENSE_SUMMARY"

def get_user_role_data_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated user-role license info table name for system '{system_name}'")
    return f"Z_FUE_{system}_USER_ROLE_LICENSE_INFO"

def get_user_role_summary_tablename(system_name:str) -> str:
    system= clean_system_name(system_name)
    logger.info(f"Generated user-role summary license table name for system '{system_name}'")
    return f"Z_FUE_{system}_USER_LICENSE_SUMMARY"


def get_role_lic_sim_tablename(system_name: str) -> str:
    system = clean_system_name(system_name)
    logger.info(f"Generated role_lic_sim table name for system '{system_name}'")
    return f"Z_FUE_{system}_ROLE_LIC_SIM"


def get_simulation_result_tablename(system_name: str) -> str:
    system = clean_system_name(system_name)
    logger.info(f"Generated simulation_result table name for system '{system_name}'")
    return f"Z_FUE_{system}_SIMULATION_RESULT"







class _AGR1251:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME = Column(String, nullable=False, index=True)
    OBJECT = Column(String, nullable=False, index=True)
    FIELD = Column(String, nullable=False, index=True)
    LOW = Column(String)
    HIGH = Column(String)
    OBJ_STATUS= Column(String)



class _AGRUSERS:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME = Column(String, nullable=False, index=True)
    UNAME = Column(String, nullable=False)


class _AGRDEFINE:
    id= Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME =Column(String, nullable=False, index=True)
    PARENT_AGR =Column(String)
    TEXT =Column(String)


class _AGRAGRS:
    id=Column(Integer, primary_key=True, index=True, autoincrement=True)
    COMPOSITE_ROLE =Column(String)
    ROLE=Column(String)
    ACTIVE=Column(String)

class _USR02:
    id= Column("id", Integer, primary_key=True, index=True, autoincrement=True)
    BNAME=Column(String)
    GLTGV=Column(String)
    GLTGB=Column(String)
    UFLAG=Column(String)
    ERDAT=Column(String)
    TRDAT=Column(String)
    USTYP=Column(String)


class _TRANSACTIONUSAGE:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    TRANSACTION= Column(String)
    PROGRAM= Column(String)
    USER= Column(String)


class _FLPCA:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Single_Role_Name=Column(String)
    Single_Role_Description =Column(String)
    Catalog_ID=Column(String)
    Semantic_Object= Column(String)
    Action= Column(String)
    Title_Subtitle_Information= Column(String)
    Application_Type= Column(String)
    SAP_Fiori_ID= Column(String)
    Transaction= Column(String)
    Tile_Title= Column(String)
    Target_Mapping_Title= Column(String)
    OData_v2_Service_Name= Column(String)
    OData_v2_Service_Status= Column(String)
    OData_v4_Service_Name= Column(String)
    OData_v4_Service_Status= Column(String)




class _TSTCT:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    TCODE=  Column(String)
    TRANSACTION_TEXT =  Column(String)
    Transaction = Column(String)
    Tile_Title = Column(String)
    Target_Mapping_Title = Column(String)
    OData_v2_Service_Name = Column(String)
    OData_v2_Service_Status = Column(String)
    OData_v4_Service_Name = Column(String)
    OData_v4_Service_Status = Column(String)



class _USOBXC:
    id= Column(Integer, primary_key=True, index=True, autoincrement=True)
    NAME = Column(String)
    PROPOSED_VALUE_FOR=Column(String)
    AUTH_OBJ=Column(String)
    OKFLAG=Column(String)

class _TOBJL:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AUTH_OBJ=Column(String)
    TEXT=Column(String)


class _RoleLic:
    """
    One row per (AGR_NAME, OBJECT, FIELD, LOW) combination after license
    matching against Z_FUE_RULESET.
    """
    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME    = Column(String, nullable=False, index=True)   # role name
    OBJECT      = Column(String, nullable=False)               # auth object
    FIELD       = Column(String, nullable=False)               # auth field
    LOW         = Column(String)                               # value low  (from AGR1251)
    HIGH        = Column(String)                               # value high (from AGR1251)
    CLASSIFY_LIC= Column(String)  # 'GB Advanced Use' | 'GC Core Use' | 'GD Self-Service Use' | 'Not Classified'
    MATCH_TYPE  = Column(String)  # 'Rule Wildcard' | 'Role Wildcard' | 'Exact Match' | 'Range Match' | 'No Match'


class _RoleLicSummary:
    """
    One row per role.  Most-restrictive license wins across all ROLELIC rows
    for that role.
    """
    id           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME     = Column(String, nullable=False, index=True)
    TEXT         = Column(String)            # role description from AGRDEFINE
    PARENT_AGR   = Column(String)            # parent role from AGRDEFINE
    CLASSIFY_LIC = Column(String)            # final (most-restrictive) license for role
    TOTAL_OBJ    = Column(Integer)           # total auth object rows
    GB_COUNT     = Column(Integer)           # count of GB Advanced Use rows
    GC_COUNT     = Column(Integer)           # count of GC Core Use rows
    GD_COUNT     = Column(Integer)           # count of GD Self-Service Use rows
    NC_COUNT     = Column(Integer)           # count of Not Classified rows


class _UserRoleLlic:
    """
    One row per (user, role) pair — the license that role contributes to
    that user.
    """
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    UNAME = Column(String, nullable=False, index=True)  # user name
    AGR_NAME = Column(String, nullable=False, index=True)  # role name
    CLASSIFY_LIC = Column(String)  # license from ROLELICSUMMARY

class _UserLicSummary:
    """
    One row per user — final license, governance flags and dormancy info.
    """
    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    UNAME            = Column(String, nullable=False, index=True)
    CLASSIFY_LIC     = Column(String)    # final (most-restrictive) license across all roles
    UFLAG            = Column(String)    # from USR02
    TRDAT            = Column(String)    # last logon date from USR02
    ERDAT            = Column(String)    # creation date from USR02
    USTYP            = Column(String)    # user type from USR02
    LAST_USED        = Column(String)    # MAX date from TRANSACTIONUSAGE (or fallback)
    DORMANT_DAYS     = Column(Integer)   # days since last activity (None if unknown)
    FLAG_90          = Column(Boolean, default=False)   # dormant >= 90 days
    FLAG_180         = Column(Boolean, default=False)   # dormant >= 180 days
    LOCKED           = Column(Boolean, default=False)   # UFLAG not in (0, 128)
    CLEANUP_CATEGORY = Column(String)    # 'Locked' | 'Dormant 180+' | 'Dormant 90+' | None


class _RoleLicSim:
    """
    Simulation copy of RoleLic - allows what-if modifications
    """
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    AGR_NAME = Column(String, nullable=False, index=True)
    OBJECT = Column(String, nullable=False)
    FIELD = Column(String, nullable=False)
    LOW = Column(String)
    HIGH = Column(String)

    # Original classification from base RoleLic
    ORIGINAL_CLASSIFY_LIC = Column(String)
    ORIGINAL_MATCH_TYPE = Column(String)

    # Simulation fields
    OPERATION = Column(String)  # 'Add', 'Change', 'Remove', None
    NEW_LOW = Column(String)  # Modified value for simulation
    NEW_HIGH = Column(String)  # Modified value for simulation
    SIM_CLASSIFY_LIC = Column(String)  # Recalculated license after change
    SIM_MATCH_TYPE = Column(String)  # Match type after change


class _SimulationResult:
    """
    Stores simulation run metadata and results
    """
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    SIMULATION_RUN_ID = Column(String, index=True, default=lambda: f"SIM{uuid.uuid4().hex[:8].upper()}")
    TIMESTAMP = Column(String, index=True)
    STATUS = Column(String(20))  # 'In Progress', 'Completed', 'Failed'
    SYSTEM_NAME = Column(String)

    # Change details (one row per change in payload)
    ROLE_NAME = Column(String)
    ROLE_DESCRIPTION = Column(String)
    OBJECT = Column(String)
    FIELD = Column(String)
    VALUE_LOW = Column(String)
    VALUE_HIGH = Column(String)
    OPERATION = Column(String)  # 'Add', 'Change', 'Remove'

    # License impact
    PREV_LICENSE = Column(String)
    CURRENT_LICENSE = Column(String)

    # Summary metrics (populated at end)
    TOTAL_FUE = Column(String)
    GB_FUE = Column(String)
    GC_FUE = Column(String)
    GD_FUE = Column(String)

_dynamic_models_cache = {}


def create_AGR1251_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_agr_1251_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicAGR1251Model = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_1251Data",
        (_AGR1251, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicAGR1251Model
    return DynamicAGR1251Model

def create_AGRUSERS_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_agr_users_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicAGRUSERModel = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_USERSData",
        (_AGRUSERS, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicAGRUSERModel
    return DynamicAGRUSERModel


def create_AGRDEFINE_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_agr_define_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicAGRDEFINEModel = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_DEFINEData",
        (_AGRDEFINE, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicAGRDEFINEModel
    return DynamicAGRDEFINEModel

def create_AGRAGRS_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_agr_agrs_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicAGRAGRSModel = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_AGRSData",
        (_AGRAGRS, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicAGRAGRSModel
    return DynamicAGRAGRSModel

def create_USR02_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_usr02_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicUSR02Model = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_USR02Data",
        (_USR02, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicUSR02Model
    return DynamicUSR02Model

def create_TRANSACTIONUSAGE_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_transaction_usage_data_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicTUSAGEModel = type(
        f"Z_FUE_{clean_system_name(system_name)}AGR_TUSAGEData",
        (_TRANSACTIONUSAGE, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicTUSAGEModel
    return DynamicTUSAGEModel

def create_TSTCT_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_tcode_data_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicTSTCTModel = type(
        f"Z_FUE_{clean_system_name(system_name)}_TSTCTData",
        (_TSTCT, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicTSTCTModel
    return DynamicTSTCTModel


def create_FLPCA_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_flpca_data_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicFLPCAModel = type(
        f"Z_FUE_{clean_system_name(system_name)}_FLPCAData",
        (_FLPCA, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicFLPCAModel
    return DynamicFLPCAModel

def create_USOBXC_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_usobxC_data_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicUSOBXCModel = type(
        f"Z_FUE_{clean_system_name(system_name)}_USOBXCData",
        (_USOBXC, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicUSOBXCModel
    return DynamicUSOBXCModel


def create_TOBJL_model(system_name:str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    table_name = get_obj_text_data_tablename(system_name)
    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicTOBJLModel = type(
        f"Z_FUE_{clean_system_name(system_name)}_TOBJLData",
        (_TOBJL, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    _dynamic_models_cache[table_name] = DynamicTOBJLModel
    return DynamicTOBJLModel



def create_role_lic_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    """Create dynamic model for role object license data."""
    table_name = get_role_lice_data_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicRoleLicData= type(
        f"Z_FUE_{clean_system_name(system_name)}RoleLicData",
        (_RoleLic, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicRoleLicData
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    return DynamicRoleLicData


def create_role_lic_summary_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    """Create dynamic model for role object license summary data."""
    table_name = get_role_lice_data_summary_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicRoleLicSummaryData= type(
        f"Z_FUE_{clean_system_name(system_name)}RoleLicSummaryData",
        (_RoleLicSummary, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicRoleLicSummaryData
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    return DynamicRoleLicSummaryData



def create_user_lic_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    """Create dynamic model for user role licenses data."""
    table_name = get_user_role_data_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicUserLicData= type(
        f"Z_FUE_{clean_system_name(system_name)}UserLicData",
        (_UserRoleLlic, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicUserLicData
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    return DynamicUserLicData



def create_user_lic_summary_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve model for system='{system_name}'")
    """Create dynamic model for user role licenses summary data."""
    table_name = get_user_role_summary_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache. Returning cached model.")
        return _dynamic_models_cache[table_name]
    logger.info(f"Model for table '{table_name}' not in cache. Creating a new dynamic model.")

    DynamicUserLicSummaryData= type(
        f"Z_FUE_{clean_system_name(system_name)}UserLicSummaryData",
        (_UserLicSummary, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicUserLicSummaryData
    logger.info(f"Successfully created dynamic model for table '{table_name}'")
    return DynamicUserLicSummaryData

def create_role_lic_sim_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve RoleLicSim model for system='{system_name}'")
    table_name = get_role_lic_sim_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache.")
        return _dynamic_models_cache[table_name]

    logger.info(f"Creating new dynamic RoleLicSim model for table '{table_name}'")

    DynamicRoleLicSimModel = type(
        f"Z_FUE_{clean_system_name(system_name)}RoleLicSim",
        (_RoleLicSim, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicRoleLicSimModel
    logger.info(f"Successfully created dynamic RoleLicSim model for table '{table_name}'")
    return DynamicRoleLicSimModel


def create_simulation_result_model(system_name: str):
    logger.debug(f"Attempting to create or retrieve SimulationResult model for system='{system_name}'")
    table_name = get_simulation_result_tablename(system_name)

    if table_name in _dynamic_models_cache:
        logger.info(f"Model for table '{table_name}' found in cache.")
        return _dynamic_models_cache[table_name]

    logger.info(f"Creating new dynamic SimulationResult model for table '{table_name}'")

    DynamicSimResultModel = type(
        f"Z_FUE_{clean_system_name(system_name)}SimulationResult",
        (_SimulationResult, Base),
        {"__tablename__": table_name, "__table_args__": {'extend_existing': True}}
    )

    _dynamic_models_cache[table_name] = DynamicSimResultModel
    logger.info(f"Successfully created dynamic SimulationResult model for table '{table_name}'")
    return DynamicSimResultModel


def ensure_table_exists(db_engine, model_class):
    inspector = sqla_inspect(db_engine)
    table_name = model_class.__tablename__
    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' not found. Creating...")
        try:
            model_class.__table__.create(bind=db_engine)
            print(f"Table '{table_name}' created.")
        except Exception as e:
            print(f"Error creating table {table_name}: {e}")
            raise
    else:
        print(f"Table '{table_name}' already exists.")


