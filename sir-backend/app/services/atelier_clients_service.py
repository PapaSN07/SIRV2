"""Atelier clients : rattachement des unités de relève (UR) aux postes, avec validation.

Reprise de l'atelier SAIFI/SAIDI de l'application bureau SIR (PosteClient, Agent_Modif /
Agent_Valide). Les chefs d'unité BCC et BRC proposent l'ajout ou le retrait d'une UR sur un
poste de leur région ; le BRC (ou l'administration SCR / SAQS) valide. Une même personne peut
proposer et valider (décision SENELEC du 27/10/2026). Un lien proposé à l'ajout ne compte qu'une
fois validé ; un lien proposé au retrait compte jusqu'à la validation du retrait.

Après chaque validation, les clients des postes concernés sont recalculés par le worker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin, role_names
from app.models.clients import PosteUniteReleve
from app.models.utilisateurs import Utilisateur
from app.repositories import clients_repository as repo
from app.schemas.base_clients import (
    DroitsAtelier,
    LienPosteUR,
    LienPosteURCreate,
    PosteRecherche,
    UniteReleveRecherche,
)
from app.schemas.common import PaginatedResponse

PROPOSANTS = frozenset({"BCC", "BRC", "ADMIN_SCR"})
VALIDEURS = frozenset({"BRC", "ADMIN_SCR", "ADMIN_SAQS"})
LECTEURS = PROPOSANTS | VALIDEURS | {"SUPERVISEUR"}
_NATIONAUX = frozenset({"ADMIN_SCR", "ADMIN_SAQS"})


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _a_un_role(user: Utilisateur, roles: frozenset[str]) -> bool:
    return is_superadmin(user) or bool(role_names(user) & roles)


def droits(user: Utilisateur) -> tuple[bool, bool]:
    return _a_un_role(user, PROPOSANTS), _a_un_role(user, VALIDEURS)


def region_du_compte(user: Utilisateur) -> int | None:
    """Région du compte BCC / BRC (même règle que le réseau distribution) ; None = national."""
    if is_superadmin(user) or role_names(user) & _NATIONAUX:
        return None
    if not _a_un_role(user, LECTEURS):
        raise _erreur(status.HTTP_403_FORBIDDEN, "Accès à l'atelier clients non autorisé")
    region_id = user.user_roles[0].scope_service_id if user.user_roles else None
    if region_id is None:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Périmètre régional non configuré pour ce compte")
    return region_id


async def _poste_du_perimetre(db: AsyncSession, user: Utilisateur, poste_id: int) -> None:
    existe, region_poste = await repo.region_du_poste(db, poste_id)
    if not existe:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Poste introuvable")
    region_id = region_du_compte(user)
    if region_id is not None and region_poste != region_id:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Poste hors de votre région")


async def _lien_du_perimetre(db: AsyncSession, user: Utilisateur, lien_id: int) -> PosteUniteReleve:
    lien = await repo.get_lien(db, lien_id)
    if lien is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Lien introuvable")
    await _poste_du_perimetre(db, user, lien.poste_id)
    return lien


async def get_droits(db: AsyncSession, user: Utilisateur) -> DroitsAtelier:
    region_du_compte(user)
    proposer, valider = droits(user)
    periode = await repo.dernier_mois(db)
    return DroitsAtelier(
        peut_proposer=proposer,
        peut_valider=valider,
        periode=f"{periode[1]:02d}/{periode[0]}" if periode else None,
    )


async def lister(
    db: AsyncSession,
    user: Utilisateur,
    *,
    poste_id: int | None,
    a_valider: bool,
    recherche: str | None,
    page: int,
    page_size: int,
) -> PaginatedResponse[LienPosteUR]:
    region_id = region_du_compte(user)
    rows, total = await repo.lister_liens(
        db,
        region_id=region_id,
        periode=await repo.dernier_mois(db),
        poste_id=poste_id,
        a_valider=a_valider,
        recherche=recherche,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=[LienPosteUR(**r) for r in rows], total=total, page=page, page_size=page_size)


async def rechercher_postes(db: AsyncSession, user: Utilisateur, recherche: str) -> list[PosteRecherche]:
    region_id = region_du_compte(user)
    if len(recherche.strip()) < 2:
        return []
    return [PosteRecherche(**r) for r in await repo.rechercher_postes(db, recherche, region_id)]


async def rechercher_ur(db: AsyncSession, user: Utilisateur, recherche: str) -> list[UniteReleveRecherche]:
    region_du_compte(user)
    periode = await repo.dernier_mois(db)
    if periode is None or len(recherche.strip()) < 3:
        return []
    return [UniteReleveRecherche(**r) for r in await repo.rechercher_ur(db, recherche, *periode)]


async def proposer_ajout(db: AsyncSession, user: Utilisateur, data: LienPosteURCreate) -> int:
    if not droits(user)[0]:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Seuls les chefs d'unité BCC / BRC et l'Admin SCR proposent")
    await _poste_du_perimetre(db, user, data.poste_id)
    ur = data.unite_releve.strip().upper()
    existant = await repo.get_lien_par_couple(db, data.poste_id, ur)
    if existant is not None:
        if existant.statut == "suppression_proposee":
            # Retrait proposé puis annulé : le lien redevient valide tel quel
            existant.statut = "valide"
            existant.modifie_par_id, existant.modifie_le = user.id, datetime.now()
            lien_id = existant.id
            await db.commit()
            return lien_id
        raise _erreur(status.HTTP_409_CONFLICT, f"L'UR {ur} est déjà rattachée à ce poste")
    lien = await repo.ajouter_lien(
        db,
        PosteUniteReleve(
            poste_id=data.poste_id,
            unite_releve=ur,
            statut="ajout_propose",
            modifie_par_id=user.id,
            modifie_le=datetime.now(),
        ),
    )
    lien_id = lien.id
    await db.commit()
    return lien_id


async def proposer_retrait(db: AsyncSession, user: Utilisateur, lien_id: int) -> str:
    """Retrait d'une UR : un ajout encore proposé est simplement annulé."""
    if not droits(user)[0]:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Seuls les chefs d'unité BCC / BRC et l'Admin SCR proposent")
    lien = await _lien_du_perimetre(db, user, lien_id)
    if lien.statut == "ajout_propose":
        await repo.supprimer_lien(db, lien)
        await db.commit()
        return "Proposition d'ajout annulée"
    if lien.statut == "suppression_proposee":
        raise _erreur(status.HTTP_409_CONFLICT, "Retrait déjà proposé")
    lien.statut = "suppression_proposee"
    lien.modifie_par_id, lien.modifie_le = user.id, datetime.now()
    await db.commit()
    return "Retrait proposé, en attente de validation"


async def decider(db: AsyncSession, user: Utilisateur, lien_id: int, accepter: bool) -> tuple[str, list[int]]:
    """Valide ou rejette une proposition ; renvoie le message et les postes à recalculer."""
    if not droits(user)[1]:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Validation réservée au BRC et à l'administration SCR / SAQS")
    lien = await _lien_du_perimetre(db, user, lien_id)
    if lien.statut == "valide":
        raise _erreur(status.HTTP_409_CONFLICT, "Aucune proposition en attente sur ce lien")
    postes = await repo.postes_partageant(db, lien.unite_releve)
    ajout = lien.statut == "ajout_propose"
    if ajout == accepter:
        # ajout accepté ou retrait rejeté : le lien est (re)validé
        lien.statut = "valide"
        lien.valide_par_id, lien.valide_le = user.id, datetime.now()
    else:
        await repo.supprimer_lien(db, lien)
    await db.commit()
    message = {
        (True, True): "Ajout validé",
        (True, False): "Ajout rejeté",
        (False, True): "Retrait validé",
        (False, False): "Retrait rejeté",
    }[(ajout, accepter)]
    # Un rejet ne change pas les UR comptées : rien à recalculer
    return message, postes if accepter else []


def lancer_recalcul(postes: list[int]) -> None:
    if not postes:
        return
    from app.workers.celery_app import celery_app

    celery_app.send_task("recalculer_clients_postes", args=[sorted(set(postes))])


async def recalculer_postes(db: AsyncSession, postes: list[int]) -> dict[str, Any]:
    """Clients des postes au dernier mois chargé (les autres postes de l'UR partagée inclus)."""
    periode = await repo.dernier_mois(db)
    if periode is None:
        return {"ignore": "aucun mois chargé"}
    valeurs = await repo.clients_par_poste(db, *periode)
    touches = {p: valeurs.get(p, 0) for p in postes}
    await repo.mettre_a_jour_clients_postes(db, {p: v for p, v in touches.items() if p in valeurs}, set(postes))
    await db.commit()
    return {"periode": f"{periode[1]:02d}/{periode[0]}", "postes": touches}
