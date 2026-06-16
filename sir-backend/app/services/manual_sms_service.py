"""Service — envoi SMS manuel (Phase 7)."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import destinataire_repository as dest_repo
from app.repositories import sms_repository as sms_repo
from app.repositories import utilisateur_repository
from app.schemas.notifications import ManualSmsSendResponse
from app.services import destinataire_service

logger = logging.getLogger(__name__)

_ENTITY_TYPE_MANUAL = "manual"


def _truncate_message(message: str) -> str:
    text = message.strip()
    if len(text) > 160:
        return text[:157] + "..."
    return text


async def _resolve_destinataire_for_user(
    db: AsyncSession,
    user: Utilisateur,
) -> int:
    linked = await dest_repo.get_by_utilisateur_id(db, user.id)
    if linked is not None:
        if not linked.telephone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"L'utilisateur {user.login} n'a pas de téléphone enregistré",
                },
            )
        return linked.id

    if not user.telephone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"L'utilisateur {user.login} n'a pas de téléphone enregistré",
            },
        )

    scope_service_id = user.user_roles[0].scope_service_id if user.user_roles else None
    record = await dest_repo.create(
        db,
        nom=f"{user.prenom} {user.nom}".strip(),
        telephone=user.telephone,
        email=user.email,
        utilisateur_id=user.id,
        service_id=scope_service_id,
    )
    return record.id


async def send_manual_sms(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    message: str,
    destinataire_ids: list[int] | None,
    utilisateur_ids: list[int] | None,
) -> ManualSmsSendResponse:
    """Crée des enregistrements SMS en attente et enqueue l'envoi Celery."""
    contenu = _truncate_message(message)
    target_destinataire_ids: list[int] = []

    for dest_id in destinataire_ids or []:
        dest = await dest_repo.get_by_id(db, dest_id)
        if dest is None or not dest.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Destinataire {dest_id} introuvable ou inactif",
                },
            )
        await destinataire_service.assert_destinataire_in_scope(db, current_user, dest)
        if not dest.telephone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Le destinataire {dest.nom} n'a pas de téléphone",
                },
            )
        target_destinataire_ids.append(dest.id)

    for user_id in utilisateur_ids or []:
        user = await utilisateur_repository.get_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Utilisateur {user_id} introuvable ou inactif",
                },
            )
        dest_id = await _resolve_destinataire_for_user(db, user)
        if dest_id not in target_destinataire_ids:
            target_destinataire_ids.append(dest_id)

    sms_ids: list[int] = []
    for dest_id in target_destinataire_ids:
        record = await sms_repo.create_pending(
            db,
            destinataire_id=dest_id,
            entity_type=_ENTITY_TYPE_MANUAL,
            entity_id=None,
            contenu=contenu,
        )
        sms_ids.append(record.id)

    await db.commit()

    from app.workers.celery_app import celery_app

    for sms_id in sms_ids:
        celery_app.send_task("envoi_sms", args=[sms_id])

    logger.info("Manual SMS queued count=%s by user=%s", len(sms_ids), current_user.id)
    return ManualSmsSendResponse(sent_count=len(sms_ids), sms_ids=sms_ids)
