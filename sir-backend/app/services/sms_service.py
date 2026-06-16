"""Service — envoi SMS via gateway HTTP (Sprint 8.1)."""

import logging
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories import sms_repository as repo

logger = logging.getLogger(__name__)


async def send_sms_record(db: AsyncSession, sms_id: int) -> dict[str, str]:
    record = await repo.get_by_id(db, sms_id)
    if record is None:
        raise ValueError(f"SMS introuvable: id={sms_id}")

    destinataire = record.destinataire
    if destinataire is None or not destinataire.telephone:
        await repo.update_statut(
            db,
            record,
            statut="echec",
            erreur="Destinataire sans téléphone",
        )
        return {"statut": "echec"}

    try:
        if settings.sms_gateway_url:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    settings.sms_gateway_url,
                    json={
                        "to": destinataire.telephone,
                        "message": record.contenu,
                    },
                    headers={"Authorization": f"Bearer {settings.sms_gateway_api_key}"},
                )
                response.raise_for_status()
        else:
            logger.warning(
                "SMS mock — message simulé id=%s to=%s contenu=%s",
                sms_id,
                destinataire.telephone,
                record.contenu,
            )

        await repo.update_statut(
            db,
            record,
            statut="envoye",
            sent_at=datetime.now(),
        )
        return {"statut": "envoye"}
    except Exception as exc:
        await repo.update_statut(
            db,
            record,
            statut="echec",
            erreur=str(exc)[:500],
        )
        raise
