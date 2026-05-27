from typing import Optional, List

from pydantic import BaseModel
class RoleDetailResponse(BaseModel):
    id: str
    profile: str
    description: str
    classification: str
    gb: int
    gc: int
    gd: int
    # not_classified: int
    assignedUsers: int

class RoleObjectDetail(BaseModel):
        object: str
        classification: str
        fieldName: str
        valueLow: str
        valueHigh: Optional[str] = None  # Make valueHigh optional
        ttext: Optional[str] = None  # Make ttext optional


class SpecificRoleDetailsResponse(BaseModel):
    roleName: str
    roleDescription: str
    objectDetails: List[RoleObjectDetail]


    class Config:
        orm_mode = True