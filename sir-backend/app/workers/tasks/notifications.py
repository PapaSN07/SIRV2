"""Tâches Celery — notifications (Sprint 8)."""

import asyncio
import logging

from app.workers.db import WorkerSessionLocal
from app.services import email_service, notification_dispatch_service, sms_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_dispatch(
    event_type: str,
    entity_type: str,
    entity_id: int,
    service_id: int | None,
    extra_json: str | None,
) -> dict[str, int]:
    async with WorkerSessionLocal() as db:
        try:
            result = await notification_dispatch_service.dispatch_event(
                db,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                service_id=service_id,
                extra_json=extra_json,
            )
            return result
        except Exception:
            await db.rollback()
            raise


async def _commit_failure_trace(db, kind: str, record_id: int) -> None:
    """Persiste le statut « echec » écrit par le service ; rollback si la base elle-même est en cause."""
    try:
        await db.commit()
    except Exception:
        logger.exception("Trace d'échec %s non enregistrée id=%s", kind, record_id)
        await db.rollback()


async def _run_envoi_email(email_id: int) -> dict[str, str]:
    async with WorkerSessionLocal() as db:
        try:
            result = await email_service.send_email_record(db, email_id)
            await db.commit()
            return result
        except Exception:
            # Le service a marqué l'envoi « echec » avant de lever : on conserve
            # cette trace (sinon le rollback l'efface et l'échec devient invisible).
            await _commit_failure_trace(db, "email", email_id)
            raise


async def _run_envoi_sms_lot(sms_ids: list[int]) -> dict[str, int]:
    async with WorkerSessionLocal() as db:
        try:
            result = await sms_service.send_sms_lot(db, sms_ids)
            await db.commit()
            return result
        except Exception:
            # Les échecs sont tracés par le service : on les conserve avant de lever.
            try:
                await db.commit()
            except Exception:
                logger.exception("Trace d'échec SMS non enregistrée ids=%s", sms_ids)
                await db.rollback()
            raise


async def _run_envoi_sms(sms_id: int) -> dict[str, str]:
    async with WorkerSessionLocal() as db:
        try:
            result = await sms_service.send_sms_record(db, sms_id)
            await db.commit()
            return result
        except Exception:
            # Le service a marqué l'envoi « echec » avant de lever : on conserve
            # cette trace (sinon le rollback l'efface et l'échec devient invisible).
            await _commit_failure_trace(db, "sms", sms_id)
            raise


@celery_app.task(name="dispatch_notification_event", bind=True)
def dispatch_notification_event_task(
    self,
    event_type: str,
    entity_type: str,
    entity_id: int,
    service_id: int | None,
    extra_json: str | None = None,
) -> dict[str, int]:
    try:
        return asyncio.run(
            _run_dispatch(event_type, entity_type, entity_id, service_id, extra_json)
        )
    except Exception as exc:
        logger.exception("dispatch_notification_event failed")
        raise self.retry(exc=exc, countdown=30, max_retries=3) from exc


@celery_app.task(name="envoi_email", bind=True)
def envoi_email_task(self, email_id: int) -> dict[str, str]:
    try:
        return asyncio.run(_run_envoi_email(email_id))
    except Exception as exc:
        logger.exception("envoi_email failed email_id=%s", email_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc


@celery_app.task(name="envoi_email_direct", bind=True)
def envoi_email_direct_task(self, to_email: str, sujet: str, corps: str) -> dict[str, str]:
    try:
        return asyncio.run(email_service.send_direct(to_email=to_email, sujet=sujet, corps=corps))
    except Exception as exc:
        logger.exception("envoi_email_direct failed to=%s", to_email)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc


@celery_app.task(name="envoi_sms_lot", bind=True)
def envoi_sms_lot_task(self, sms_ids: list[int]) -> dict[str, int]:
    """Un appel sendManySMS par message : tous les destinataires en une fois."""
    try:
        return asyncio.run(_run_envoi_sms_lot(sms_ids))
    except Exception:
        logger.exception("envoi_sms_lot failed sms_ids=%s", sms_ids)
        raise


@celery_app.task(name="envoi_sms", bind=True)
def envoi_sms_task(self, sms_id: int) -> dict[str, str]:
    try:
        return asyncio.run(_run_envoi_sms(sms_id))
    except Exception as exc:
        logger.exception("envoi_sms failed sms_id=%s", sms_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc
