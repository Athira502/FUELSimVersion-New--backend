from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict

class SystemCreate(BaseModel):
    SYSTEM_NAME: str
    SYSTEM_RELEASE_INFO: str

class SystemUpdate(BaseModel):
    system_release_info: str

class SystemResponse(BaseModel):
    id: int
    SYSTEM_NAME: str
    SYSTEM_RELEASE_INFO: str


class RuleSetSchema(BaseModel):
    id: int
    rule_description: str
    auth_object: str
    auth_field: str
    auth_value: str

    model_config = ConfigDict(from_attributes=True)