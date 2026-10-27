"""Tâches Celery — indicateurs END / SAIFI / SAIDI."""

import asyncio
import logging

from app.workers.db import WorkerSessionLocal
from app.services import end_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_calcul_end(interruption_id: int) -> dict[str, int | float | str | bool | None]:
    async with WorkerSessionLocal() as db:
        try:
            result = await end_service.calculer_et_persister_end(db, interruption_id)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="calcul_end", bind=True)
def calcul_end_task(
    self, interruption_id: int
) -> dict[str, int | float | str | bool | None]:
    """Calcule et persiste l'END pour une interruption clôturée."""
    try:
        return asyncio.run(_run_calcul_end(interruption_id))
    except Exception as exc:
        logger.exception("calcul_end failed for interruption_id=%s", interruption_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc


async def _run_calcul_saifi_saidi(
    interruption_id: int,
) -> dict[str, int | float | str | None]:
    from app.services import saifi_saidi_service

    async with WorkerSessionLocal() as db:
        try:
            result = await saifi_saidi_service.calculer_et_persister_saifi_saidi(
                db, interruption_id
            )
            if result.get("status") == "calculated":
                await db.commit()
            else:
                await db.rollback()
            return result
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="calcul_saifi_saidi", bind=True)
def calcul_saifi_saidi_task(
    self, interruption_id: int
) -> dict[str, int | float | str | None]:
    """Recalcule SAIFI/SAIDI pour le service/période de l'interruption validée."""
    try:
        return asyncio.run(_run_calcul_saifi_saidi(interruption_id))
    except Exception as exc:
        logger.exception(
            "calcul_saifi_saidi failed for interruption_id=%s", interruption_id
        )
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc


async def _run_recalcul_periode(service_id: int, annee: int, mois: int) -> dict[str, int | str | None]:
    from app.services import saifi_saidi_service

    async with WorkerSessionLocal() as db:
        try:
            result = await saifi_saidi_service.recalculer_periode(
                db, service_id=service_id, annee=annee, mois=mois
            )
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="recalcul_saifi_saidi_periode", bind=True)
def recalcul_saifi_saidi_periode_task(
    self, service_id: int, annee: int, mois: int
) -> dict[str, int | str | None]:
    """Recalcule SAIFI/SAIDI d'un mois de service (après dévalidation d'une interruption)."""
    try:
        return asyncio.run(_run_recalcul_periode(service_id, annee, mois))
    except Exception as exc:
        logger.exception("recalcul periode failed service=%s %s/%s", service_id, mois, annee)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc
