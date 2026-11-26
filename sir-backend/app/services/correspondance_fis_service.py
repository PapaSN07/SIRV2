"""Service — correspondances FIS administrées (libellé FIS → entrée du Référentiel).

Créées et supprimées avec les droits du Référentiel distribution (Admin SCR, SUPERADMIN) ;
la cible doit être active et, pour une cause, un siège ou une signalisation, de type
distribution ou commun (mêmes règles que l'import FIS et la saisie manuelle).
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.correspondance_fis import CorrespondanceFis
from app.models.utilisateurs import Utilisateur
from app.repositories import correspondance_fis_repository as repo
from app.schemas.correspondance_fis import (
    CorrespondanceFisCreate,
    CorrespondanceFisResponse,
    normaliser_libelle_fis,
)
from app.services import referentiel_service
from app.utils.audit import ACTION_CREATE, ACTION_DELETE, log_audit

_RESSOURCES: dict[str, str] = {
    "nature": "natures",
    "cause": "causes",
    "siege": "sieges",
    "signalisation": "signalisations",
}
_LIBELLES: dict[str, str] = {
    "nature": "Nature",
    "cause": "Cause",
    "siege": "Siège",
    "signalisation": "Signalisation",
}
_TYPES_RESEAU_DISTRIBUTION = frozenset({"distribution", "commun"})


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _ensure_peut_ecrire(user: Utilisateur, categorie: str) -> None:
    """Droits du Référentiel distribution, et Admin SCR seulement : les correspondances ne
    servent qu'à l'import FIS distribution (`natures` est aussi ouvert à l'Admin Dispatching
    dans le Référentiel, pas ici)."""
    referentiel_service._ensure_can_write(user, _RESSOURCES[categorie], "distribution")
    if not is_superadmin(user) and "ADMIN_SCR" not in referentiel_service._user_role_names(user):
        raise _erreur(status.HTTP_403_FORBIDDEN, "Correspondances FIS réservées à l'Admin SCR")


def _cible(ligne: CorrespondanceFis) -> Any:
    return getattr(ligne, ligne.categorie)


def _reponse(ligne: CorrespondanceFis, cible: Any | None = None) -> CorrespondanceFisResponse:
    cible = cible if cible is not None else _cible(ligne)
    return CorrespondanceFisResponse(
        id=ligne.id,
        categorie=ligne.categorie,  # type: ignore[arg-type]
        libelle_fis=ligne.libelle_fis,
        referentiel_id=cible.id,
        referentiel_code=cible.code,
        referentiel_libelle=cible.libelle,
        is_force_majeure=ligne.is_force_majeure,
        created_at=ligne.created_at,
    )


async def lister(db: AsyncSession, categorie: str | None = None) -> list[CorrespondanceFisResponse]:
    return [_reponse(ligne) for ligne in await repo.lister(db, categorie=categorie)]


async def creer(
    db: AsyncSession, current_user: Utilisateur, body: CorrespondanceFisCreate
) -> CorrespondanceFisResponse:
    categorie = body.categorie
    _ensure_peut_ecrire(current_user, categorie)

    libelle = normaliser_libelle_fis(body.libelle_fis)
    if not libelle:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Libellé FIS obligatoire")
    if body.is_force_majeure is not None and categorie != "cause":
        raise _erreur(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "La force majeure ne se renseigne que pour une cause"
        )

    nom = _LIBELLES[categorie]
    cible = await repo.get_cible(db, categorie, body.referentiel_id)
    if cible is None:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{nom} {body.referentiel_id} introuvable")
    if not cible.is_active:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{nom} « {cible.libelle} » inactive")
    if categorie != "nature" and getattr(cible, "type_reseau", None) not in _TYPES_RESEAU_DISTRIBUTION:
        raise _erreur(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{nom} « {cible.libelle} » : type distribution ou commun attendu",
        )

    if await repo.existe(db, categorie, libelle):
        raise _erreur(
            status.HTTP_409_CONFLICT, f"Une correspondance existe déjà pour {nom.lower()} « {libelle} »"
        )

    try:
        ligne = await repo.creer(
            db,
            categorie=categorie,
            libelle_fis=libelle,
            referentiel_id=cible.id,
            is_force_majeure=body.is_force_majeure,
            created_by_id=current_user.id,
        )
    except IntegrityError as exc:  # création simultanée du même libellé (contrainte d'unicité)
        raise _erreur(
            status.HTTP_409_CONFLICT, f"Une correspondance existe déjà pour {nom.lower()} « {libelle} »"
        ) from exc
    await log_audit(
        db,
        table_name="correspondances_fis",
        record_id=ligne.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={
            "categorie": categorie,
            "libelle_fis": libelle,
            "referentiel_id": cible.id,
            "is_force_majeure": body.is_force_majeure,
        },
    )
    return _reponse(ligne, cible)


async def supprimer(db: AsyncSession, current_user: Utilisateur, correspondance_id: int) -> None:
    ligne = await repo.get_by_id(db, correspondance_id)
    if ligne is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, f"Correspondance FIS {correspondance_id} introuvable")
    _ensure_peut_ecrire(current_user, ligne.categorie)
    anciennes = {
        "categorie": ligne.categorie,
        "libelle_fis": ligne.libelle_fis,
        "referentiel_id": getattr(ligne, repo.COLONNES_CIBLES[ligne.categorie]),
        "is_force_majeure": ligne.is_force_majeure,
    }
    await repo.supprimer(db, ligne)
    await log_audit(
        db,
        table_name="correspondances_fis",
        record_id=correspondance_id,
        action=ACTION_DELETE,
        user_id=current_user.id,
        old_values=anciennes,
    )
