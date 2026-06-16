from pydantic import BaseModel


class RegionResponse(BaseModel):
    id: int
    code: str
    libelle: str
    is_active: bool

    model_config = {"from_attributes": True}


class DelegationResponse(BaseModel):
    id: int
    region_id: int
    code: str
    libelle: str
    is_active: bool

    model_config = {"from_attributes": True}


class AgenceResponse(BaseModel):
    id: int
    delegation_id: int
    code: str
    libelle: str
    is_active: bool

    model_config = {"from_attributes": True}


class ServiceResponse(BaseModel):
    id: int
    agence_id: int
    code: str
    libelle: str
    is_active: bool

    model_config = {"from_attributes": True}
