"""Schémas — base clients SAIFI/SAIDI (contrats par unité de relève)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PeriodeContrats(BaseModel):
    annee: int
    mois: int
    ur: int
    contrats: int
    contrats_sans_agence: int
    ur_rattachees: int
    contrats_rattaches: int
    date_maj: datetime | None
    source: str


class BaseClientsResume(BaseModel):
    """Mois chargés, liens poste ↔ UR par statut et état de la synchronisation BI_ODS."""

    periodes: list[PeriodeContrats]
    liens: dict[str, int]
    bi_ods_configure: bool


class TacheLancee(BaseModel):
    task_id: str
    message: str


# ── Atelier : lien poste ↔ unité de relève ───────────────────────────────────

StatutLien = Literal["valide", "ajout_propose", "suppression_proposee"]


class LienPosteUR(BaseModel):
    id: int
    poste_id: int
    poste_code: str
    poste_libelle: str
    service: str | None
    unite_releve: str
    ur_libelle: str | None
    # Contrats de l'UR au dernier mois chargé ; None = UR absente de la base clients
    nb_contrats: int | None
    # Postes qui se partagent l'UR (ses contrats leur sont répartis à parts égales)
    nb_postes: int | None
    statut: StatutLien
    modifie_par: str | None
    modifie_le: datetime | None
    valide_par: str | None
    valide_le: datetime | None


class LienPosteURCreate(BaseModel):
    poste_id: int = Field(..., ge=1)
    unite_releve: str = Field(..., min_length=4, max_length=20, pattern=r"^\s*[0-9A-Za-z]{4,20}\s*$")


class PosteRecherche(BaseModel):
    id: int
    code: str
    libelle: str
    service: str | None
    nombre_clients: int | None
    nb_ur: int


class UniteReleveRecherche(BaseModel):
    unite_releve: str
    libelle: str | None
    nb_contrats: int
    nb_postes: int


class DroitsAtelier(BaseModel):
    peut_proposer: bool
    peut_valider: bool
    periode: str | None


class ActionAtelier(BaseModel):
    id: int
    message: str
