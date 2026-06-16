"""Tâches Celery — génération de rapports CRSE (Sprint 6.6)."""

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.services import rapport_generation_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_generer_rapport(rapport_id: int) -> dict[str, str]:
    async with AsyncSessionLocal() as db:
        try:
            result = await rapport_generation_service.execute_generation(db, rapport_id)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="generer_rapport", bind=True)
def generer_rapport_task(self, rapport_id: int) -> dict[str, str]:
    """Génère un rapport (PDF/XLSX) et met à jour le suivi en base."""
    try:
        return asyncio.run(_run_generer_rapport(rapport_id))
    except Exception as exc:
        logger.exception("generer_rapport failed for rapport_id=%s", rapport_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc
