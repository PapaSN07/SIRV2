from typing import Literal

from pydantic import BaseModel, Field

TypeReseau = Literal["distribution", "transport", "commun"]

VALID_RESOURCES = frozenset({"causes", "sieges", "signalisations", "natures", "types_end"})
RESOURCES_WITH_TYPE_RESEAU = frozenset({"causes", "sieges", "signalisations"})


class ReferentielCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    libelle: str = Field(..., min_length=1, max_length=200)
    type_reseau: TypeReseau | None = None
    description: str | None = Field(default=None, max_length=500)


class ReferentielUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    type_reseau: TypeReseau | None = None
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ReferentielResponse(BaseModel):
    id: int
    code: str
    libelle: str
    type_reseau: str | None = None
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
