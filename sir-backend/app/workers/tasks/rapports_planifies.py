"""Rapports planifiés : hebdomadaire (lundi 8 h) et mensuel (le 1er à 8 h), heure de Dakar."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.workers.celery_app import celery_app
from app.workers.db import WorkerSessionLocal

logger = logging.getLogger(__name__)


async def _envoyer(type_rapport: str, aujourd_hui: date) -> dict[str, object]:
    from app.services import rapport_planifie_service

    async with WorkerSessionLocal() as db:
        bilan = await rapport_planifie_service.envoyer(db, type_rapport, aujourd_hui)
    return {
        "type": bilan.type_rapport,
        "periode": bilan.periode,
        "rapports": bilan.rapports,
        "emails": bilan.emails,
        "erreurs": bilan.erreurs,
    }


@celery_app.task(name="rapports_planifies")
def rapports_planifies_task(type_rapport: str, aujourd_hui: str | None = None) -> dict[str, object]:
    import redis

    from app.core.config import settings
    from app.services.rapport_planifie_service import periode

    jour = date.fromisoformat(aujourd_hui) if aujourd_hui else date.today()
    debut, _ = periode(type_rapport, jour)
    # Un seul envoi par période, même si le planificateur redémarre ou rejoue la tâche
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        if not client.set(f"rapport_planifie:{type_rapport}:{debut.isoformat()}", "1", nx=True, ex=40 * 86400):
            logger.info("rapport %s %s déjà envoyé", type_rapport, debut)
            return {"type": type_rapport, "deja_envoye": True}
    finally:
        client.close()

    bilan = asyncio.run(_envoyer(type_rapport, jour))
    for email_id in bilan["emails"]:  # type: ignore[union-attr]
        celery_app.send_task("envoi_email", args=[email_id])
    logger.info("rapport %s : %s fichier(s), %s e-mail(s)", type_rapport, bilan["rapports"], len(bilan["emails"]))  # type: ignore[arg-type]
    return bilan
