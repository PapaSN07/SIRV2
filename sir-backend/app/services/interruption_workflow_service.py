"""Service métier — workflow opérationnel interruptions distribution."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.interruption_workflow import InterruptionWorkflowStep
from app.models.utilisateurs import Utilisateur
from app.repositories import interruption_distribution_repository as distrib_repo
from app.repositories import interruption_workflow_repository as workflow_repo
from app.repositories import sig_repository as sig_repo
from app.schemas.interruption_workflow import (
    InterruptionWorkflowResponse,
    InterruptionWorkflowUpdate,
    WorkflowStepClients,
    WorkflowStepDeclenchement,
    WorkflowStepInterpellation,
    WorkflowStepLocalisation,
    WorkflowStepRemise,
    WorkflowStepReparation,
    WorkflowStepTronconnement,
)
from app.services import interruption_distribution_service as distrib_service
from app.utils.audit import ACTION_UPDATE, log_audit

WRITE_ROLES = frozenset({"BCC", "BRC", "ADMIN_SCR"})


def _compute_duree_minutes(debut: datetime | None, fin: datetime | None) -> int | None:
    if debut is None or fin is None:
        return None
    if fin < debut:
        return None
    return int((fin - debut).total_seconds() // 60)


def _empty_workflow_response(interruption_id: int) -> InterruptionWorkflowResponse:
    empty_clients = WorkflowStepClients(nombre_postes_impactes=0, nombre_clients_touches=None)
    return InterruptionWorkflowResponse(
        interruption_id=interruption_id,
        declenchement=WorkflowStepDeclenchement(),
        interpellation=WorkflowStepInterpellation(),
        tronconnement=WorkflowStepTronconnement(),
        localisation=WorkflowStepLocalisation(),
        reparation=WorkflowStepReparation(),
        remise=WorkflowStepRemise(),
        clients=empty_clients,
    )


def _to_response(
    interruption_id: int,
    step: InterruptionWorkflowStep | None,
    clients: WorkflowStepClients,
) -> InterruptionWorkflowResponse:
    if step is None:
        response = _empty_workflow_response(interruption_id)
        response.clients = clients
        return response

    troncon_libelle = step.troncon.libelle if step.troncon else None
    troncon_sig_libelle = None
    if step.troncon_sig:
        troncon_sig_libelle = step.troncon_sig.nom_troncon or step.troncon_sig.nom_noeud_amont
    return InterruptionWorkflowResponse(
        interruption_id=interruption_id,
        declenchement=WorkflowStepDeclenchement(
            date_debut=step.date_debut_declenchement,
            date_fin=step.date_fin_declenchement,
            duree_minutes=step.duree_declenchement_minutes,
        ),
        interpellation=WorkflowStepInterpellation(
            date_interpellation=step.date_interpellation_pdm,
            date_arrivee=step.date_arrivee_pdm,
            duree_minutes=step.duree_interpellation_minutes,
        ),
        tronconnement=WorkflowStepTronconnement(
            date_debut=step.date_debut_tronconnement,
            date_fin=step.date_fin_tronconnement,
            duree_minutes=step.duree_tronconnement_minutes,
            troncon_id=step.troncon_id,
            troncon_sig_id=step.troncon_sig_id,
            noeud_amont_libelle=step.noeud_amont_libelle,
            noeud_aval_libelle=step.noeud_aval_libelle,
            troncon_libelle=troncon_libelle,
            troncon_sig_libelle=troncon_sig_libelle,
        ),
        localisation=WorkflowStepLocalisation(
            date_debut=step.date_debut_localisation,
            date_fin=step.date_fin_localisation,
            duree_minutes=step.duree_localisation_minutes,
        ),
        reparation=WorkflowStepReparation(
            date_debut=step.date_debut_reparation,
            date_fin=step.date_fin_reparation,
            duree_minutes=step.duree_reparation_minutes,
        ),
        remise=WorkflowStepRemise(
            date_debut=step.date_debut_remise,
            date_fin=step.date_fin_remise,
            duree_minutes=step.duree_remise_minutes,
        ),
        clients=clients,
        responsable_matricule=step.responsable_matricule,
        observations_workflow=step.observations_workflow,
    )


async def _load_clients(db: AsyncSession, interruption_id: int) -> WorkflowStepClients:
    postes, clients = await workflow_repo.count_clients_workflow(db, interruption_id)
    return WorkflowStepClients(
        nombre_postes_impactes=postes,
        nombre_clients_touches=clients,
    )


async def _ensure_interruption_accessible(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
):
    interruption = await distrib_repo.get_interruption(db, interruption_id)
    if interruption is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )
    await distrib_service._ensure_interruption_in_scope(db, current_user, interruption)
    return interruption


def _ensure_can_write_workflow(current_user: Utilisateur) -> None:
    distrib_service._ensure_not_transport_role(current_user)
    roles = distrib_service._user_role_names(current_user)
    if is_superadmin(current_user):
        return
    if not roles.intersection(WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Modification workflow réservée aux rôles BCC, BRC et ADMIN_SCR",
            },
        )


def _build_update_values(body: InterruptionWorkflowUpdate) -> dict:
    values: dict = {}

    if body.declenchement is not None:
        d = body.declenchement
        values["date_debut_declenchement"] = d.date_debut
        values["date_fin_declenchement"] = d.date_fin
        values["duree_declenchement_minutes"] = _compute_duree_minutes(d.date_debut, d.date_fin)

    if body.interpellation is not None:
        i = body.interpellation
        values["date_interpellation_pdm"] = i.date_interpellation
        values["date_arrivee_pdm"] = i.date_arrivee
        values["duree_interpellation_minutes"] = _compute_duree_minutes(
            i.date_interpellation, i.date_arrivee
        )

    if body.tronconnement is not None:
        t = body.tronconnement
        values["date_debut_tronconnement"] = t.date_debut
        values["date_fin_tronconnement"] = t.date_fin
        values["duree_tronconnement_minutes"] = _compute_duree_minutes(t.date_debut, t.date_fin)
        values["troncon_id"] = t.troncon_id
        values["troncon_sig_id"] = t.troncon_sig_id
        values["noeud_amont_libelle"] = t.noeud_amont_libelle
        values["noeud_aval_libelle"] = t.noeud_aval_libelle

    if body.localisation is not None:
        loc = body.localisation
        values["date_debut_localisation"] = loc.date_debut
        values["date_fin_localisation"] = loc.date_fin
        values["duree_localisation_minutes"] = _compute_duree_minutes(loc.date_debut, loc.date_fin)

    if body.reparation is not None:
        r = body.reparation
        values["date_debut_reparation"] = r.date_debut
        values["date_fin_reparation"] = r.date_fin
        values["duree_reparation_minutes"] = _compute_duree_minutes(r.date_debut, r.date_fin)

    if body.remise is not None:
        rem = body.remise
        values["date_debut_remise"] = rem.date_debut
        values["date_fin_remise"] = rem.date_fin
        values["duree_remise_minutes"] = _compute_duree_minutes(rem.date_debut, rem.date_fin)

    if body.responsable_matricule is not None:
        values["responsable_matricule"] = body.responsable_matricule
    if body.observations_workflow is not None:
        values["observations_workflow"] = body.observations_workflow

    return values


async def get_workflow(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> InterruptionWorkflowResponse:
    distrib_service._ensure_can_read(current_user)
    await _ensure_interruption_accessible(db, interruption_id, current_user)
    step = await workflow_repo.get_workflow_step(db, interruption_id)
    clients = await _load_clients(db, interruption_id)
    return _to_response(interruption_id, step, clients)


async def update_workflow(
    db: AsyncSession,
    interruption_id: int,
    body: InterruptionWorkflowUpdate,
    current_user: Utilisateur,
) -> InterruptionWorkflowResponse:
    _ensure_can_write_workflow(current_user)
    interruption = await _ensure_interruption_accessible(db, interruption_id, current_user)

    if interruption.statut != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le workflow n'est modifiable que pour une interruption en cours",
            },
        )

    values = _build_update_values(body)
    if not values:
        step = await workflow_repo.get_workflow_step(db, interruption_id)
        clients = await _load_clients(db, interruption_id)
        return _to_response(interruption_id, step, clients)

    if body.tronconnement is not None and body.tronconnement.troncon_sig_id is not None:
        troncon_sig = await sig_repo.get_troncon_sig(db, body.tronconnement.troncon_sig_id)
        if troncon_sig is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Tronçon SIG {body.tronconnement.troncon_sig_id} introuvable",
                },
            )

    if body.tronconnement is not None and body.tronconnement.troncon_id is not None:
        from app.repositories import reseau_distribution_repository as reseau_repo

        troncon = await reseau_repo.get_troncon(db, body.tronconnement.troncon_id)
        if troncon is None or not troncon.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Tronçon {body.tronconnement.troncon_id} introuvable ou inactif",
                },
            )

    step = await workflow_repo.upsert_workflow_step(db, interruption_id, values)
    await log_audit(
        db,
        user_id=current_user.id,
        action=ACTION_UPDATE,
        entity_type="interruption_workflow",
        entity_id=interruption_id,
        details={"fields": sorted(values.keys())},
    )
    clients = await _load_clients(db, interruption_id)
    return _to_response(interruption_id, step, clients)
