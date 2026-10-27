"""Rapports planifiés (décision SENELEC du 27/10/2026).

- Chaque lundi à 8 h : rapport hebdomadaire de la semaine précédente (lundi → dimanche).
- Chaque 1er du mois à 8 h : rapport mensuel distribution du mois précédent.

Destinataires : ceux déjà enregistrés dans Notifications (actifs, avec e-mail). Chacun reçoit le
rapport de la région de son service, en pièce jointe PDF ; un destinataire sans service reçoit
le rapport national. Les rapports sont générés au nom d'un compte national (Admin SAQS).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Destinataire
from app.repositories import destinataire_repository as dest_repo
from app.repositories import email_repository
from app.repositories import end_repository
from app.repositories import rapport_repository
from app.services import rapport_generation_service

logger = logging.getLogger(__name__)

HEBDOMADAIRE = "hebdomadaire"
MENSUEL = "mensuel_distribution"


@dataclass
class EnvoiPlanifie:
    type_rapport: str
    periode: str
    rapports: int = 0
    emails: list[int] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)


def periode(type_rapport: str, aujourd_hui: date) -> tuple[date, date]:
    """Période couverte : semaine précédente (lundi → dimanche) ou mois précédent."""
    if type_rapport == HEBDOMADAIRE:
        return rapport_generation_service.semaine_precedente(aujourd_hui)
    fin = aujourd_hui.replace(day=1) - timedelta(days=1)
    return fin.replace(day=1), fin


def _libelle(type_rapport: str, debut: date, fin: date) -> str:
    if type_rapport == HEBDOMADAIRE:
        return f"hebdomadaire du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"
    return f"mensuel distribution {debut:%m/%Y}"


async def _par_region(db: AsyncSession, destinataires: list[Destinataire]) -> dict[int | None, list[Destinataire]]:
    groupes: dict[int | None, list[Destinataire]] = defaultdict(list)
    cache: dict[int, int | None] = {}
    for d in destinataires:
        region_id: int | None = None
        if d.service_id is not None:
            if d.service_id not in cache:
                cache[d.service_id] = await end_repository.get_region_id_for_service(db, d.service_id)
            region_id = cache[d.service_id]
        groupes[region_id].append(d)
    return groupes


async def envoyer(db: AsyncSession, type_rapport: str, aujourd_hui: date) -> EnvoiPlanifie:
    debut, fin = periode(type_rapport, aujourd_hui)
    bilan = EnvoiPlanifie(type_rapport=type_rapport, periode=f"{debut.isoformat()}/{fin.isoformat()}")

    destinataires = await dest_repo.list_actifs_avec_email(db)
    if not destinataires:
        logger.info("rapport %s : aucun destinataire avec e-mail", type_rapport)
        return bilan
    compte = await rapport_repository.get_compte_systeme(db)
    if compte is None:
        bilan.erreurs.append("Aucun compte Admin SAQS actif pour générer les rapports planifiés")
        logger.error(bilan.erreurs[-1])
        return bilan

    libelle = _libelle(type_rapport, debut, fin)
    for region_id, groupe in (await _par_region(db, destinataires)).items():
        if type_rapport == HEBDOMADAIRE:
            params = {
                "date": debut.isoformat(),
                "date_fin": fin.isoformat(),
                "region_id": region_id,
                "service_id": None,
                "include_transport": region_id is None,
            }
        else:
            params = {"annee": debut.year, "mois": debut.month, "region_id": region_id, "top_feeders_limit": 10}

        record = await rapport_repository.create_rapport(
            db,
            task_id=str(uuid.uuid4()),
            type_rapport=type_rapport,
            format="pdf",
            user_id=compte.id,
            region_id=region_id,
            params_json=json.dumps(params),
            expires_at=rapport_generation_service._expires_at() + timedelta(days=7),
        )
        await db.commit()
        try:
            await rapport_generation_service.execute_generation(db, record.id, notifier=False)
            await db.commit()
        except Exception as exc:  # une région en échec n'empêche pas les autres
            await db.rollback()
            bilan.erreurs.append(f"région {region_id}: {exc}")
            logger.exception("rapport %s région %s en échec", type_rapport, region_id)
            continue
        bilan.rapports += 1

        perimetre = "national" if region_id is None else "de votre région"
        sujet = f"[rapport_planifie] SIR — Rapport {libelle}"
        corps = (
            f"<html><body><p>Bonjour,</p><p>Veuillez trouver en pièce jointe le rapport {libelle} "
            f"({perimetre}).</p><p>Envoi automatique SIR — SENELEC.</p></body></html>"
        )
        for d in groupe:
            email = await email_repository.create_pending(
                db, destinataire_id=d.id, entity_type="rapport", entity_id=record.id, sujet=sujet, corps=corps
            )
            bilan.emails.append(email.id)
        await db.commit()
    return bilan
