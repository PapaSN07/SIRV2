"""Service — envoi des SMS enregistrés via la passerelle SENELEC (sendOneSignedSMS).

Un appel par destinataire, signé ``SMS_GATEWAY_SIGNATURE``. Sans ``SMS_GATEWAY_URL``
ni ``SMS_GATEWAY_WSDL``, l'envoi est simulé.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories import sms_repository as repo
from app.services import sms_gateway

logger = logging.getLogger(__name__)


async def send_sms_lot(db: AsyncSession, sms_ids: list[int]) -> dict[str, int]:
    """Envoie les SMS ``sms_ids`` un par un et met à jour leur statut (envoye / echec).

    Un échec n'arrête pas les envois suivants. Lève la dernière erreur à la fin, après
    avoir tracé les échecs, pour que la tâche Celery le signale.
    """
    envoyes = echecs = 0
    derniere_erreur: Exception | None = None
    for sms_id in sms_ids:
        record = await repo.get_by_id(db, sms_id)
        if record is None:
            logger.warning("SMS introuvable id=%s", sms_id)
            continue
        telephone = record.destinataire.telephone if record.destinataire else None
        if not telephone or not sms_gateway.normaliser_numero(telephone):
            await repo.update_statut(db, record, statut="echec", erreur="Destinataire sans téléphone")
            echecs += 1
            continue
        try:
            if settings.sms_gateway_url or settings.sms_gateway_wsdl:
                retour = await sms_gateway.envoyer_sms(telephone, record.contenu)
                logger.info("sendOneSignedSMS id=%s → %s", sms_id, retour[:200])
            else:
                logger.warning("SMS simulé (passerelle non configurée) id=%s to=%s", sms_id, telephone)
        except Exception as exc:  # noqa: BLE001 — l'échec est tracé sur le SMS
            derniere_erreur = exc
            await repo.update_statut(db, record, statut="echec", erreur=str(exc)[:500])
            echecs += 1
            continue
        await repo.update_statut(db, record, statut="envoye", sent_at=datetime.now())
        envoyes += 1

    if derniere_erreur is not None:
        raise derniere_erreur
    return {"envoyes": envoyes, "echecs": echecs}


async def send_sms_record(db: AsyncSession, sms_id: int) -> dict[str, str]:
    """Envoi d'un seul SMS (compatibilité)."""
    record = await repo.get_by_id(db, sms_id)
    if record is None:
        raise ValueError(f"SMS introuvable: id={sms_id}")
    resultat = await send_sms_lot(db, [sms_id])
    return {"statut": "envoye" if resultat["envoyes"] else "echec"}
