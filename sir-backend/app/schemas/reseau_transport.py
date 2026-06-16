from pydantic import BaseModel, Field

VALID_SLUGS: frozenset[str] = frozenset(
    {"equipements-transport", "sources-transport", "postes-lignes"}
)

READ_ROLES: frozenset[str] = frozenset({"DISPATCHER", "ADMIN_DISPATCHING", "ADMIN_SAQS"})


class EquipementTransportCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    type_equipement: str = Field(..., min_length=1, max_length=50)
    tension_kv: float | None = None
    puissance_mva: float | None = None


class EquipementTransportUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    type_equipement: str | None = Field(default=None, min_length=1, max_length=50)
    tension_kv: float | None = None
    puissance_mva: float | None = None
    is_active: bool | None = None


class EquipementTransportResponse(BaseModel):
    id: int
    code: str
    libelle: str
    type_equipement: str
    tension_kv: float | None
    puissance_mva: float | None
    is_active: bool

    model_config = {"from_attributes": True}


class SourceTransportCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    puissance_mw: float | None = None


class SourceTransportUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    puissance_mw: float | None = None
    is_active: bool | None = None


class SourceTransportResponse(BaseModel):
    id: int
    code: str
    libelle: str
    puissance_mw: float | None
    is_active: bool

    model_config = {"from_attributes": True}


class PosteLigneCreate(BaseModel):
    poste_source_id: int
    equipement_transport_id: int


class PosteLigneUpdate(BaseModel):
    poste_source_id: int | None = None
    equipement_transport_id: int | None = None
    is_active: bool | None = None


class PosteLigneResponse(BaseModel):
    id: int
    poste_source_id: int
    equipement_transport_id: int
    is_active: bool

    model_config = {"from_attributes": True}
