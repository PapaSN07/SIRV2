"""Cycle de vie commun distribution / transport : historique, renvoi, dévalidation, archivage.

Décisions SENELEC du 27/10/2026 :
- renvoi en correction et dévalidation réservés à l'Admin SCR (distribution) — l'Admin
  Dispatching tient le même rôle pour le transport ; motif obligatoire ;
- une même personne peut saisir et valider ;
- les interruptions validées d'un mois sont archivées (gelées) après le rapport mensuel CRSE.

Les contrôles d'accès au dossier (lecture, périmètre) restent dans chaque service métier ;
ce module reçoit une interruption déjà chargée et accessible.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.interruption_statut_historique import (
    ACTION_ARCHIVAGE,
    ACTION_DEVALIDATION,
    ACTION_RENVOI,
)
from app.models.interruptions import Interruption
from app.models.utilisateurs import Utilisateur
from app.repositories import end_repository
from app.repositories import interruption_statut_repository as repo
from app.schemas.interruption_statut import ArchivageResponse, StatutHistoriqueResponse
from app.services.indicateurs_cache_service import invalidate_indicateurs_cache
from app.utils.audit import ACTION_UPDATE, log_audit

# Rôle qui peut renvoyer / dévalider, par type de réseau
_ROLE_CORRECTION = {
    "distribution": frozenset({"ADMIN_SCR"}),
    "transport": frozenset({"ADMIN_DISPATCHING"}),
    "omvg": frozenset({"ADMIN_DISPATCHING"}),
}
# Archivage mensuel : le même rôle, plus l'Admin SAQS qui produit le rapport CRSE
_ROLE_ARCHIVAGE = {
    "distribution": frozenset({"ADMIN_SCR", "ADMIN_SAQS"}),
    "transport": frozenset({"ADMIN_DISPATCHING", "ADMIN_SAQS"}),
    "omvg": frozenset({"ADMIN_DISPATCHING", "ADMIN_SAQS"}),
}
_LIBELLE_ROLE = {"distribution": "l'Admin SCR", "transport": "l'Admin Dispatching", "omvg": "l'Admin Dispatching"}


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=code, detail={"status": "error", "data": None, "error": message}
    )


def _roles(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def ensure_peut_corriger(user: Utilisateur, type_direction: str) -> None:
    if is_superadmin(user) or _roles(user) & _ROLE_CORRECTION.get(type_direction, frozenset()):
        return
    raise _erreur(
        status.HTTP_403_FORBIDDEN,
        f"Renvoi en correction et dévalidation réservés à {_LIBELLE_ROLE.get(type_direction, 'l’administrateur')}",
    )


def ensure_peut_archiver(user: Utilisateur, type_direction: str) -> None:
    if is_superadmin(user) or _roles(user) & _ROLE_ARCHIVAGE.get(type_direction, frozenset()):
        return
    raise _erreur(status.HTTP_403_FORBIDDEN, "Archivage mensuel non autorisé pour ce rôle")


async def enregistrer(
    db: AsyncSession,
    interruption: Interruption,
    *,
    action: str,
    ancien_statut: str | None,
    user: Utilisateur,
    motif: str | None = None,
) -> None:
    """Trace un changement de statut (appelé avant le commit de l'opération métier)."""
    await repo.ajouter(
        db,
        interruption_id=interruption.id,
        action=action,
        ancien_statut=ancien_statut,
        nouveau_statut=interruption.statut,
        utilisateur_id=user.id,
        motif=motif,
    )


async def historique(db: AsyncSession, interruption_id: int) -> list[StatutHistoriqueResponse]:
    rows = await repo.lister(db, interruption_id)
    return [
        StatutHistoriqueResponse(
            id=r.id,
            action=r.action,
            ancien_statut=r.ancien_statut,
            nouveau_statut=r.nouveau_statut,
            motif=r.motif,
            utilisateur_id=r.utilisateur_id,
            utilisateur_nom=(
                f"{r.utilisateur.prenom} {r.utilisateur.nom}".strip() if r.utilisateur else None
            ),
            created_at=r.created_at,
        )
        for r in rows
    ]


async def dates_cloture(db: AsyncSession, interruption_ids: list[int]) -> dict:
    return await repo.dates_cloture(db, interruption_ids)


async def _region_id(db: AsyncSession, interruption: Interruption) -> int | None:
    if interruption.service_id is None:
        return None
    return await end_repository.get_region_id_for_service(db, interruption.service_id)


async def renvoyer_en_correction(
    db: AsyncSession, interruption: Interruption, motif: str, user: Utilisateur
) -> None:
    """Clôturée → En cours : la date de remise, la durée et l'END sont effacées, le motif tracé."""
    ensure_peut_corriger(user, interruption.type_direction)
    if interruption.statut != "cloture":
        raise _erreur(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Seule une interruption clôturée (non validée) peut être renvoyée en correction",
        )
    ancienne_remise = interruption.date_remise
    region_id = await _region_id(db, interruption)
    old = {
        "statut": interruption.statut,
        "date_remise": ancienne_remise.isoformat() if ancienne_remise else None,
        "duree_minutes": interruption.duree_minutes,
    }

    await repo.appliquer(
        db, interruption, statut="en_cours", date_remise=None, duree_minutes=None, updated_by_id=user.id
    )
    await repo.supprimer_end(db, interruption.id)
    await enregistrer(
        db, interruption, action=ACTION_RENVOI, ancien_statut="cloture", user=user, motif=motif
    )
    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_UPDATE,
        user_id=user.id,
        old_values=old,
        new_values={"statut": "en_cours", "motif_renvoi": motif},
    )
    createur_id = interruption.created_by_id
    interruption_id, service_id = interruption.id, interruption.service_id
    await db.commit()

    if region_id is not None and ancienne_remise is not None:
        invalidate_indicateurs_cache(region_id, ancienne_remise, indicateurs=("end", "tableau-de-bord"))

    from app.schemas.notifications import NotificationEventType
    from app.services import notification_dispatch_service

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_RENVOYEE,
        entity_type="interruption",
        entity_id=interruption_id,
        service_id=service_id,
        extra={"motif": motif, "user_id": createur_id},
    )


async def devalider(
    db: AsyncSession, interruption: Interruption, motif: str, user: Utilisateur
) -> None:
    """Validée → Clôturée : SAIFI/SAIDI du mois sont recalculés sans elle."""
    ensure_peut_corriger(user, interruption.type_direction)
    if interruption.statut == "archive":
        raise _erreur(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Interruption archivée après le rapport mensuel CRSE : elle ne peut plus être dévalidée",
        )
    if interruption.statut != "valide":
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seule une interruption validée peut être dévalidée")

    region_id = await _region_id(db, interruption)
    old = {"statut": interruption.statut, "validated_by_id": interruption.validated_by_id}
    await repo.appliquer(
        db, interruption, statut="cloture", validated_by_id=None, updated_by_id=user.id
    )
    await enregistrer(
        db, interruption, action=ACTION_DEVALIDATION, ancien_statut="valide", user=user, motif=motif
    )
    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_UPDATE,
        user_id=user.id,
        old_values=old,
        new_values={"statut": "cloture", "motif_devalidation": motif},
    )
    service_id = interruption.service_id
    apparition = interruption.date_apparition
    remise = interruption.date_remise
    type_direction = interruption.type_direction
    await db.commit()

    if region_id is not None:
        invalidate_indicateurs_cache(region_id, apparition)
        if remise is not None:
            invalidate_indicateurs_cache(region_id, remise)
    if service_id is not None and type_direction == "distribution":
        from app.workers.tasks.indicateurs import recalcul_saifi_saidi_periode_task

        try:
            recalcul_saifi_saidi_periode_task.delay(service_id, apparition.year, apparition.month)
        except Exception:  # broker indisponible : le prochain recalcul du mois corrigera
            pass


async def archiver_mois(
    db: AsyncSession,
    *,
    type_direction: str,
    annee: int,
    mois: int,
    user: Utilisateur,
) -> ArchivageResponse:
    """Gèle les interruptions validées du mois (après le rapport mensuel CRSE)."""
    ensure_peut_archiver(user, type_direction)
    a_archiver = await repo.lister_validees_du_mois(
        db, type_direction=type_direction, annee=annee, mois=mois
    )
    for interruption in a_archiver:
        await repo.appliquer(db, interruption, statut="archive", updated_by_id=user.id)
        await enregistrer(
            db, interruption, action=ACTION_ARCHIVAGE, ancien_statut="valide", user=user,
            motif=f"Rapport mensuel {mois:02d}/{annee}",
        )
    if a_archiver:
        await log_audit(
            db,
            table_name="interruptions",
            record_id=a_archiver[0].id,
            action=ACTION_UPDATE,
            user_id=user.id,
            new_values={
                "archivage_mensuel": f"{annee}-{mois:02d}",
                "type_direction": type_direction,
                "nombre": len(a_archiver),
            },
        )
    restantes = await repo.compter_non_validees_du_mois(
        db, type_direction=type_direction, annee=annee, mois=mois
    )
    await db.commit()
    return ArchivageResponse(
        annee=annee, mois=mois, archivees=len(a_archiver), non_validees_restantes=restantes
    )
