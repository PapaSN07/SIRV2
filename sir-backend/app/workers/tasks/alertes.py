"""Alertes de retard (décision SENELEC du 27/10/2026 : seuil 24 h).

Toutes les heures : une interruption en cours depuis plus de 24 h, ou clôturée depuis plus
de 24 h sans validation, déclenche une notification (SMS / e-mail / temps réel) au service.
Rappel au plus une fois par 24 h et par situation (verrou Redis).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app
from app.workers.db import WorkerSessionLocal

logger = logging.getLogger(__name__)

SEUIL_ALERTE = timedelta(hours=24)
_LIBELLES = {"en_cours": "en cours", "non_validee": "clôturée non validée"}


async def _detecter() -> list[tuple[int, int | None, str]]:
    from app.repositories import interruption_statut_repository as repo

    avant = datetime.now(timezone.utc).replace(tzinfo=None) - SEUIL_ALERTE
    async with WorkerSessionLocal() as db:
        lignes = await repo.lister_en_retard(db, avant=avant)
        return [(i.id, i.service_id, situation) for i, situation in lignes]


def _premiere_fois(client, interruption_id: int, situation: str) -> bool:
    cle = f"alerte24h:{interruption_id}:{situation}"
    return bool(client.set(cle, "1", nx=True, ex=int(SEUIL_ALERTE.total_seconds())))


@celery_app.task(name="alertes_retard_24h")
def alertes_retard_24h_task() -> dict[str, int]:
    import redis

    from app.core.config import settings
    from app.schemas.notifications import NotificationEventType
    from app.services import notification_dispatch_service

    lignes = asyncio.run(_detecter())
    client = redis.from_url(settings.redis_url, decode_responses=True)
    envoyees = 0
    try:
        for interruption_id, service_id, situation in lignes:
            if not _premiere_fois(client, interruption_id, situation):
                continue
            notification_dispatch_service.schedule_event(
                event_type=NotificationEventType.INTERRUPTION_ALERTE_24H,
                entity_type="interruption",
                entity_id=interruption_id,
                service_id=service_id,
                extra={"situation": _LIBELLES[situation]},
            )
            envoyees += 1
    finally:
        client.close()
    logger.info("alertes 24h : %s en retard, %s notifiées", len(lignes), envoyees)
    return {"en_retard": len(lignes), "notifiees": envoyees}
