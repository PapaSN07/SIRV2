from typing import Literal

from pydantic import BaseModel, Field

ResourceSlug = Literal[
    "postes-sources",
    "feeders",
    "postes",
    "troncons",
    "sous-feeders",
]

VALID_SLUGS: frozenset[str] = frozenset(
    {"postes-sources", "feeders", "postes", "troncons", "sous-feeders"}
)

READ_ROLES: frozenset[str] = frozenset({"BCC", "BRC", "ADMIN_SCR", "ADMIN_SAQS"})


# ---------------------------------------------------------------------------
# Poste source
# ---------------------------------------------------------------------------


class PosteSourceCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    region_id: int | None = None
    puissance_mva: float | None = None


class PosteSourceUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    region_id: int | None = None
    puissance_mva: float | None = None
    is_active: bool | None = None


class PosteSourceResponse(BaseModel):
    id: int
    code: str
    libelle: str
    region_id: int | None
    puissance_mva: float | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Feeder
# ---------------------------------------------------------------------------


class FeederCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    poste_source_id: int
    service_id: int | None = None
    tension_kv: float | None = None
    puissance_installee_mva: float | None = None


class FeederUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    poste_source_id: int | None = None
    service_id: int | None = None
    tension_kv: float | None = None
    puissance_installee_mva: float | None = None
    is_active: bool | None = None


class FeederResponse(BaseModel):
    id: int
    code: str
    libelle: str
    poste_source_id: int
    service_id: int | None
    tension_kv: float | None
    puissance_installee_mva: float | None
    is_active: bool
    service_libelle: str | None = None
    poste_source_libelle: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Poste
# ---------------------------------------------------------------------------


class PosteCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    feeder_id: int | None = None
    service_id: int | None = None
    puissance_kva: float | None = None
    nombre_clients: int | None = None


class PosteUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    feeder_id: int | None = None
    service_id: int | None = None
    puissance_kva: float | None = None
    nombre_clients: int | None = None
    is_active: bool | None = None


class PosteResponse(BaseModel):
    id: int
    code: str
    libelle: str
    feeder_id: int | None
    service_id: int | None
    puissance_kva: float | None
    nombre_clients: int | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tronçon
# ---------------------------------------------------------------------------


class TronconCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    feeder_id: int | None = None
    longueur_km: float | None = None
    tension_kv: float | None = None


class TronconUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    feeder_id: int | None = None
    longueur_km: float | None = None
    tension_kv: float | None = None
    is_active: bool | None = None


class TronconResponse(BaseModel):
    id: int
    code: str
    libelle: str
    feeder_id: int | None
    longueur_km: float | None
    tension_kv: float | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sous-feeder
# ---------------------------------------------------------------------------


class SousFeederCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    feeder_id: int


class SousFeederUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    feeder_id: int | None = None
    is_active: bool | None = None


class SousFeederResponse(BaseModel):
    id: int
    code: str
    libelle: str
    feeder_id: int
    is_active: bool

    model_config = {"from_attributes": True}
