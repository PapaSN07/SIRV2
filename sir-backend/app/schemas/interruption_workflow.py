"""Schémas Pydantic — workflow opérationnel interruption distribution."""

from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowStepDeclenchement(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None


class WorkflowStepInterpellation(BaseModel):
    date_interpellation: datetime | None = None
    date_arrivee: datetime | None = None
    duree_minutes: int | None = None


class WorkflowStepTronconnement(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None
    troncon_id: int | None = Field(default=None, ge=1)
    troncon_sig_id: int | None = Field(default=None, ge=1)
    noeud_amont_libelle: str | None = Field(default=None, max_length=255)
    noeud_aval_libelle: str | None = Field(default=None, max_length=255)
    troncon_libelle: str | None = None
    troncon_sig_libelle: str | None = None


class WorkflowStepLocalisation(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None


class WorkflowStepReparation(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None


class WorkflowStepRemise(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    duree_minutes: int | None = None


class WorkflowStepClients(BaseModel):
    """Onglet clients — données agrégées depuis poste_interruptions."""

    nombre_postes_impactes: int = 0
    nombre_clients_touches: int | None = None


class InterruptionWorkflowResponse(BaseModel):
    interruption_id: int
    declenchement: WorkflowStepDeclenchement
    interpellation: WorkflowStepInterpellation
    tronconnement: WorkflowStepTronconnement
    localisation: WorkflowStepLocalisation
    reparation: WorkflowStepReparation
    remise: WorkflowStepRemise
    clients: WorkflowStepClients
    responsable_matricule: int | None = None
    observations_workflow: str | None = None


class WorkflowStepDeclenchementUpdate(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None


class WorkflowStepInterpellationUpdate(BaseModel):
    date_interpellation: datetime | None = None
    date_arrivee: datetime | None = None


class WorkflowStepTronconnementUpdate(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    troncon_id: int | None = Field(default=None, ge=1)
    troncon_sig_id: int | None = Field(default=None, ge=1)
    noeud_amont_libelle: str | None = Field(default=None, max_length=255)
    noeud_aval_libelle: str | None = Field(default=None, max_length=255)


class WorkflowStepLocalisationUpdate(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None


class WorkflowStepReparationUpdate(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None


class WorkflowStepRemiseUpdate(BaseModel):
    date_debut: datetime | None = None
    date_fin: datetime | None = None


class InterruptionWorkflowUpdate(BaseModel):
    declenchement: WorkflowStepDeclenchementUpdate | None = None
    interpellation: WorkflowStepInterpellationUpdate | None = None
    tronconnement: WorkflowStepTronconnementUpdate | None = None
    localisation: WorkflowStepLocalisationUpdate | None = None
    reparation: WorkflowStepReparationUpdate | None = None
    remise: WorkflowStepRemiseUpdate | None = None
    responsable_matricule: int | None = Field(default=None, ge=1)
    observations_workflow: str | None = Field(default=None, max_length=2000)
