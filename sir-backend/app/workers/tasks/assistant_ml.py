"""Tâches Celery — scoring risque Assistant ML (P0)."""

from __future__ import annotations

import asyncio
import logging

from app.workers.db import WorkerSessionLocal
from app.services import ml_scoring_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_score_feeders(horizon_days: int) -> dict[str, int | str]:
    async with WorkerSessionLocal() as db:
        try:
            return await ml_scoring_service.score_feeders(
                db, horizon_days=horizon_days
            )
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="score_feeder_risk", bind=True)
def score_feeder_risk_task(
    self, horizon_days: int = ml_scoring_service.DEFAULT_HORIZON_DAYS
) -> dict[str, int | str]:
    """Recalcule les scores de risque feeder (P0 règles) — hors chemin critique API."""
    try:
        return asyncio.run(_run_score_feeders(horizon_days))
    except Exception as exc:
        logger.exception("score_feeder_risk failed horizon_days=%s", horizon_days)
        raise self.retry(exc=exc, countdown=120, max_retries=3) from exc
