"""Service — envoi des SMS enregistrés via la passerelle SENELEC (sendManySMS).

Les SMS d'un même message sont regroupés : un seul appel ``sendManySMS`` par lot
(``SMS_GATEWAY_LOT_MAX`` numéros au plus). Sans ``SMS_GATEWAY_URL``, l'envoi est simulé.
"""

import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notifications import SmsEnvoye
from app.repositories import sms_repository as repo
from app.services import sms_gateway

logger = logging.getLogger(__name__)


async def send_sms_lot(db: AsyncSession, sms_ids: list[int]) -> dict[str, int]:
    """Envoie les SMS ``sms_ids`` et met à jour leur statut (envoye / echec).

    Lève ``SmsGatewayError`` après avoir tracé les échecs si au moins un lot a échoué,
    pour que la tâche Celery le signale.
    """
    a_envoyer: dict[str, list[SmsEnvoye]] = defaultdict(list)
    echecs = 0
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
        a_envoyer[record.contenu].append(record)

    envoyes = 0
    derniere_erreur: Exception | None = None
    taille = max(1, settings.sms_gateway_lot_max)
    for contenu, records in a_envoyer.items():
        for i in range(0, len(records), taille):
            lot = records[i : i + taille]
            numeros = [r.destinataire.telephone for r in lot]
            try:
                if settings.sms_gateway_url or settings.sms_gateway_wsdl:
                    retour = await sms_gateway.envoyer_lot(numeros, contenu)
                    logger.info("sendManySMS %s numéro(s) → %s", len(lot), retour[:200])
                else:
                    logger.warning("SMS simulé (passerelle non configurée) to=%s contenu=%s", numeros, contenu)
            except Exception as exc:  # noqa: BLE001 — chaque échec est tracé sur les SMS du lot
                derniere_erreur = exc
                for r in lot:
                    await repo.update_statut(db, r, statut="echec", erreur=str(exc)[:500])
                echecs += len(lot)
                continue
            for r in lot:
                await repo.update_statut(db, r, statut="envoye", sent_at=datetime.now())
            envoyes += len(lot)

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
