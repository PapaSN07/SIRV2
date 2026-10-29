"""Service — orchestration dispatch notifications (Sprint 8)."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Destinataire
from app.repositories import destinataire_repository as dest_repo
from app.repositories import email_repository as email_repo
from app.repositories import geo_scope_repository
from app.repositories import sms_repository as sms_repo
from app.repositories import utilisateur_repository
from app.schemas.notifications import NotificationEventType
from app.services import notification_stream_service, notification_template_service

logger = logging.getLogger(__name__)

_SMS_EVENTS = frozenset(
    {
        NotificationEventType.INTERRUPTION_CREEE,
        NotificationEventType.INTERRUPTION_CLOTUREE,
        NotificationEventType.INTERRUPTION_VALIDEE,
        NotificationEventType.INTERRUPTION_RENVOYEE,
        NotificationEventType.INTERRUPTION_ALERTE_24H,
    }
)


async def _resolve_destinataires(
    db: AsyncSession,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    service_id: int | None,
    extra: dict,
) -> list[Destinataire]:
    if event_type == NotificationEventType.RAPPORT_PRET:
        user_id = extra.get("user_id")
        if user_id is None:
            return []
        user = await utilisateur_repository.get_by_id(db, int(user_id))
        if user is None:
            return []
        linked = await dest_repo.get_by_utilisateur_id(db, user.id)
        if linked is not None:
            return [linked]
        if user.email:
            virtual = Destinataire(
                id=0,
                nom=f"{user.prenom} {user.nom}",
                telephone=user.telephone,
                email=user.email,
                utilisateur_id=user.id,
                service_id=service_id,
                is_active=True,
            )
            return [virtual]
        return []

    destinataires: list[Destinataire] = []
    if event_type == NotificationEventType.INTERRUPTION_RENVOYEE and extra.get("user_id"):
        # Le saisisseur est prévenu en premier : c'est à lui de corriger
        createur = await utilisateur_repository.get_by_id(db, int(extra["user_id"]))
        if createur is not None:
            linked = await dest_repo.get_by_utilisateur_id(db, createur.id)
            if linked is not None:
                destinataires.append(linked)
            elif createur.email:
                destinataires.append(
                    Destinataire(
                        id=0,
                        nom=f"{createur.prenom} {createur.nom}",
                        telephone=createur.telephone,
                        email=createur.email,
                        utilisateur_id=createur.id,
                        service_id=service_id,
                        is_active=True,
                    )
                )
    if service_id is None:
        return destinataires
    deja = {d.id for d in destinataires if d.id}
    destinataires += [
        d for d in await dest_repo.list_active_for_service(db, service_id) if d.id not in deja
    ]
    return destinataires


async def dispatch_event(
    db: AsyncSession,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    service_id: int | None,
    extra_json: str | None = None,
) -> dict[str, int]:
    extra = json.loads(extra_json) if extra_json else {}
    destinataires = await _resolve_destinataires(
        db,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        service_id=service_id,
        extra=extra,
    )

    email_ids: list[int] = []
    sms_ids: list[int] = []

    sujet, corps = notification_template_service.render_email(
        event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        extra=extra,
    )
    sms_body = notification_template_service.render_sms(
        event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        extra=extra,
    )

    for destinataire in destinataires:
        if destinataire.email:
            if destinataire.id and await email_repo.has_recent_send(
                db,
                destinataire_id=destinataire.id or 0,
                entity_type=entity_type,
                entity_id=entity_id,
                event_marker=f"[{event_type}]",
            ):
                continue

            if destinataire.id:
                email_record = await email_repo.create_pending(
                    db,
                    destinataire_id=destinataire.id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    sujet=sujet,
                    corps=corps,
                )
                email_ids.append(email_record.id)
            else:
                from app.workers.celery_app import celery_app

                celery_app.send_task(
                    "envoi_email_direct",
                    args=[destinataire.email, sujet, corps],
                )

        if event_type in _SMS_EVENTS and destinataire.telephone and destinataire.id:
            if await sms_repo.has_recent_send(
                db,
                destinataire_id=destinataire.id,
                entity_type=entity_type,
                entity_id=entity_id,
                event_marker=f"[{event_type}]",
            ):
                continue
            sms_record = await sms_repo.create_pending(
                db,
                destinataire_id=destinataire.id,
                entity_type=entity_type,
                entity_id=entity_id,
                contenu=sms_body,
            )
            sms_ids.append(sms_record.id)

    await db.commit()

    from app.workers.celery_app import celery_app

    for email_id in email_ids:
        celery_app.send_task("envoi_email", args=[email_id])
    if sms_ids:
        # Une seule tâche pour tous les SMS de l'événement (un appel sendOneSignedSMS chacun)
        celery_app.send_task("envoi_sms_lot", args=[sms_ids])

    message = f"{event_type} — {entity_type} #{entity_id}"
    region_id = (
        await geo_scope_repository.get_region_id_for_service(db, service_id)
        if service_id is not None
        else None
    )
    await notification_stream_service.publish_event(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        service_id=service_id,
        region_id=region_id,
    )

    logger.info(
        "Notification dispatch event=%s entity=%s:%s emails=%s sms=%s",
        event_type,
        entity_type,
        entity_id,
        email_ids,
        sms_ids,
    )
    return {"emails": len(email_ids), "sms": len(sms_ids)}


def schedule_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    service_id: int | None,
    extra: dict | None = None,
) -> None:
    """Enqueue dispatch Celery après commit transaction métier.

    Une notification ne doit jamais faire échouer l'opération métier déjà
    validée en base : si le broker est indisponible, on journalise et on continue.
    """
    from app.workers.celery_app import celery_app

    try:
        celery_app.send_task(
            "dispatch_notification_event",
            args=[event_type, entity_type, entity_id, service_id, json.dumps(extra or {})],
        )
    except Exception:
        logger.exception(
            "Notification non planifiée (broker indisponible) event=%s entity=%s:%s",
            event_type,
            entity_type,
            entity_id,
        )
