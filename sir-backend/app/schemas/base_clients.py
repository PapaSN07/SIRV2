"""Schémas — base clients SAIFI/SAIDI (contrats par unité de relève)."""

from datetime import datetime

from pydantic import BaseModel


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
