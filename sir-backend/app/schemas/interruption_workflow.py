"""Schémas Pydantic — workflow opérationnel interruption distribution (étapes chaînées)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkflowEtat = Literal["terminee", "active", "verrouillee"]


class WorkflowStepClients(BaseModel):
    """Onglet clients — données agrégées depuis poste_interruptions."""

    nombre_postes_impactes: int = 0
    nombre_clients_touches: int | None = None


class WorkflowEtapeResponse(BaseModel):
    etape_workflow_id: int
    code: str
    libelle_etape_workflow: str
    ordre: int
    etape_suivante_id: int | None = None
    etat: WorkflowEtat
    workflow_id: int | None = None
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None
    observation: str | None = None
    responsable_matricule: int | None = None
    troncon_id: int | None = None
    troncon_sig_id: int | None = None
    noeud_amont_libelle: str | None = None
    noeud_aval_libelle: str | None = None
    troncon_libelle: str | None = None
    troncon_sig_libelle: str | None = None


class InterruptionWorkflowResponse(BaseModel):
    interruption_id: int
    etapes: list[WorkflowEtapeResponse] = Field(default_factory=list)
    clients: WorkflowStepClients


class WorkflowEtapeUpdate(BaseModel):
    """Saisie d'une étape. Les champs tronçon ne sont pris en compte que pour l'étape tronçonnement."""

    date_debut: datetime | None = None
    date_fin: datetime | None = None
    observation: str | None = Field(default=None, max_length=2000)
    responsable_matricule: int | None = Field(default=None, ge=1)
    troncon_id: int | None = Field(default=None, ge=1)
    troncon_sig_id: int | None = Field(default=None, ge=1)
    noeud_amont_libelle: str | None = Field(default=None, max_length=255)
    noeud_aval_libelle: str | None = Field(default=None, max_length=255)
