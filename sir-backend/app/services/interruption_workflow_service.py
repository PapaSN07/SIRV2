"""Service métier — workflow opérationnel interruptions distribution.

Les étapes peuvent être renseignées dans n'importe quel ordre : une étape
précédente sans date de fin ne bloque pas la suivante.
"""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.interruption_workflow import ETAPE_TRONCONNEMENT, EtapeWorkflow, Workflow
from app.models.utilisateurs import Utilisateur
from app.repositories import interruption_distribution_repository as distrib_repo
from app.repositories import interruption_workflow_repository as workflow_repo
from app.repositories import reseau_distribution_repository as reseau_repo
from app.repositories import sig_repository as sig_repo
from app.schemas.interruption_workflow import (
    InterruptionWorkflowResponse,
    WorkflowEtapeResponse,
    WorkflowEtapeUpdate,
    WorkflowEtat,
    WorkflowStepClients,
)
from app.services import interruption_distribution_service as distrib_service
from app.utils.audit import ACTION_UPDATE, log_audit

WRITE_ROLES = frozenset({"BCC", "BRC", "ADMIN_SCR"})
_TRONCON_FIELDS = ("troncon_id", "troncon_sig_id", "noeud_amont_libelle", "noeud_aval_libelle")


def _error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"status": "error", "data": None, "error": message},
    )


def _compute_duree_minutes(debut: datetime | None, fin: datetime | None) -> int | None:
    if debut is None or fin is None:
        return None
    if fin < debut:
        return None
    return int((fin - debut).total_seconds() // 60)


def _split_localisation_troncon(localisation: str) -> tuple[str | None, str | None]:
    """Découpe NomTroncon legacy « amont - aval »."""
    text = localisation.strip()
    if not text:
        return None, None
    if " - " in text:
        amont, aval = text.split(" - ", 1)
        return amont.strip() or None, aval.strip() or None
    return text, None


def order_etapes(etapes: list[EtapeWorkflow]) -> list[EtapeWorkflow]:
    """Ordonne les étapes en suivant la chaîne etape_suivante_id (repli sur `ordre`)."""
    by_id = {e.id: e for e in etapes}
    targets = {e.etape_suivante_id for e in etapes if e.etape_suivante_id is not None}
    roots = sorted((e for e in etapes if e.id not in targets), key=lambda e: e.ordre)
    ordered: list[EtapeWorkflow] = []
    seen: set[int] = set()
    current = roots[0] if roots else None
    while current is not None and current.id not in seen:
        ordered.append(current)
        seen.add(current.id)
        current = by_id.get(current.etape_suivante_id) if current.etape_suivante_id else None
    ordered.extend(sorted((e for e in etapes if e.id not in seen), key=lambda e: e.ordre))
    return ordered


def compute_etats(
    etapes: list[EtapeWorkflow],
    rows_by_etape: dict[int, Workflow],
) -> dict[int, WorkflowEtat]:
    """`terminee` si date_fin saisie ; sinon l'étape reste saisissable.

    Une étape peut être passée : la suivante n'est pas verrouillée.
    """
    etats: dict[int, WorkflowEtat] = {}
    for etape in etapes:
        row = rows_by_etape.get(etape.id)
        if row is not None and row.date_fin is not None:
            etats[etape.id] = "terminee"
        else:
            etats[etape.id] = "active"
    return etats


def _etape_response(
    etape: EtapeWorkflow,
    etat: WorkflowEtat,
    row: Workflow | None,
    localisation: str | None,
) -> WorkflowEtapeResponse:
    response = WorkflowEtapeResponse(
        etape_workflow_id=etape.id,
        code=etape.code,
        libelle_etape_workflow=etape.libelle_etape_workflow,
        ordre=etape.ordre,
        etape_suivante_id=etape.etape_suivante_id,
        etat=etat,
    )
    if row is not None:
        troncon_libelle = row.troncon.libelle if row.troncon else None
        troncon_sig_libelle = None
        if row.troncon_sig:
            troncon_sig_libelle = row.troncon_sig.nom_troncon or row.troncon_sig.nom_noeud_amont
            troncon_libelle = troncon_libelle or troncon_sig_libelle
        response = response.model_copy(
            update={
                "workflow_id": row.id,
                "date_debut": row.date_debut,
                "date_fin": row.date_fin,
                "duree_minutes": _compute_duree_minutes(row.date_debut, row.date_fin),
                "observation": row.observation,
                "responsable_matricule": row.responsable_matricule,
                "troncon_id": row.troncon_id,
                "troncon_sig_id": row.troncon_sig_id,
                "noeud_amont_libelle": row.noeud_amont_libelle,
                "noeud_aval_libelle": row.noeud_aval_libelle,
                "troncon_libelle": troncon_libelle,
                "troncon_sig_libelle": troncon_sig_libelle,
            }
        )

    # NomTroncon HFSQL affiché tant qu'aucun tronçon n'est rattaché
    if etape.code == ETAPE_TRONCONNEMENT and localisation and localisation.strip():
        updates: dict[str, str] = {}
        if not response.troncon_libelle and not response.troncon_id:
            updates["troncon_libelle"] = localisation.strip()
        amont, aval = _split_localisation_troncon(localisation)
        if not response.noeud_amont_libelle and amont:
            updates["noeud_amont_libelle"] = amont
        if not response.noeud_aval_libelle and aval:
            updates["noeud_aval_libelle"] = aval
        if updates:
            response = response.model_copy(update=updates)
    return response


async def _load_clients(db: AsyncSession, interruption_id: int) -> WorkflowStepClients:
    postes, clients = await workflow_repo.count_clients_workflow(db, interruption_id)
    return WorkflowStepClients(nombre_postes_impactes=postes, nombre_clients_touches=clients)


async def _build_response(
    db: AsyncSession,
    interruption_id: int,
    localisation: str | None,
) -> InterruptionWorkflowResponse:
    etapes = order_etapes(await workflow_repo.list_etapes(db))
    rows = {row.etape_workflow_id: row for row in await workflow_repo.list_workflows(db, interruption_id)}
    etats = compute_etats(etapes, rows)
    return InterruptionWorkflowResponse(
        interruption_id=interruption_id,
        etapes=[_etape_response(e, etats[e.id], rows.get(e.id), localisation) for e in etapes],
        clients=await _load_clients(db, interruption_id),
    )


async def _ensure_interruption_accessible(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
):
    interruption = await distrib_repo.get_interruption(db, interruption_id)
    if interruption is None:
        raise _error(status.HTTP_404_NOT_FOUND, f"Interruption {interruption_id} introuvable")
    await distrib_service._ensure_interruption_in_scope(db, current_user, interruption)
    return interruption


def _ensure_can_write_workflow(current_user: Utilisateur) -> None:
    distrib_service._ensure_not_transport_role(current_user)
    if is_superadmin(current_user):
        return
    if not distrib_service._user_role_names(current_user).intersection(WRITE_ROLES):
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "Modification workflow réservée aux rôles BCC, BRC et ADMIN_SCR",
        )


async def _validate_troncons(db: AsyncSession, body: WorkflowEtapeUpdate) -> None:
    if body.troncon_sig_id is not None:
        if await sig_repo.get_troncon_sig(db, body.troncon_sig_id) is None:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Tronçon SIG {body.troncon_sig_id} introuvable",
            )
    if body.troncon_id is not None:
        troncon = await reseau_repo.get_troncon(db, body.troncon_id)
        if troncon is None or not troncon.is_active:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Tronçon {body.troncon_id} introuvable ou inactif",
            )


async def get_workflow(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> InterruptionWorkflowResponse:
    distrib_service._ensure_can_read(current_user)
    interruption = await _ensure_interruption_accessible(db, interruption_id, current_user)
    return await _build_response(db, interruption_id, interruption.localisation)


async def update_etape(
    db: AsyncSession,
    interruption_id: int,
    etape_id: int,
    body: WorkflowEtapeUpdate,
    current_user: Utilisateur,
) -> InterruptionWorkflowResponse:
    _ensure_can_write_workflow(current_user)
    interruption = await _ensure_interruption_accessible(db, interruption_id, current_user)

    if interruption.statut != "en_cours":
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Le workflow n'est modifiable que pour une interruption en cours",
        )

    etapes = order_etapes(await workflow_repo.list_etapes(db))
    etape = next((e for e in etapes if e.id == etape_id), None)
    if etape is None:
        raise _error(status.HTTP_404_NOT_FOUND, f"Étape workflow {etape_id} introuvable")

    if body.date_debut and body.date_fin and body.date_fin < body.date_debut:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La date de fin doit être postérieure à la date de début",
        )

    values = body.model_dump(exclude_unset=True)
    if etape.code == ETAPE_TRONCONNEMENT:
        await _validate_troncons(db, body)
    else:
        for field in _TRONCON_FIELDS:
            values.pop(field, None)

    if values:
        await workflow_repo.upsert_workflow(db, interruption_id, etape.id, values)
        await log_audit(
            db,
            table_name="workflows",
            record_id=interruption_id,
            action=ACTION_UPDATE,
            user_id=current_user.id,
            new_values={
                "etape": etape.code,
                **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in values.items()},
            },
        )
        await db.commit()

    return await _build_response(db, interruption_id, interruption.localisation)
