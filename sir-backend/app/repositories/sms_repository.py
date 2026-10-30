"""Repository — traces SMS envoyés."""

from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications import Destinataire, SmsEnvoye


async def get_by_id(db: AsyncSession, sms_id: int) -> SmsEnvoye | None:
    result = await db.execute(
        select(SmsEnvoye)
        .options(
            selectinload(SmsEnvoye.destinataire).selectinload(Destinataire.utilisateur),
        )
        .where(SmsEnvoye.id == sms_id)
    )
    return result.scalar_one_or_none()


async def create_pending(
    db: AsyncSession,
    *,
    destinataire_id: int,
    entity_type: str | None,
    entity_id: int | None,
    contenu: str,
    envoye_par_id: int | None = None,
) -> SmsEnvoye:
    record = SmsEnvoye(
        destinataire_id=destinataire_id,
        entity_type=entity_type,
        entity_id=entity_id,
        contenu=contenu,
        statut="en_attente",
        envoye_par_id=envoye_par_id,
    )
    db.add(record)
    await db.flush()
    return record


async def update_statut(
    db: AsyncSession,
    record: SmsEnvoye,
    *,
    statut: str,
    sent_at: datetime | None = None,
    erreur: str | None = None,
    code_retour: str | None = None,
    message_id: str | None = None,
) -> SmsEnvoye:
    record.statut = statut
    if sent_at is not None:
        record.sent_at = sent_at
    if erreur is not None:
        record.erreur = erreur
    if code_retour is not None:
        record.code_retour = code_retour[:20]
    if message_id is not None:
        record.message_id = message_id[:50]
    await db.flush()
    return record


async def has_recent_send(
    db: AsyncSession,
    *,
    destinataire_id: int,
    entity_type: str | None,
    entity_id: int | None,
    event_marker: str,
    window_minutes: int = 5,
) -> bool:
    since = datetime.now() - timedelta(minutes=window_minutes)
    query = select(SmsEnvoye.id).where(
        SmsEnvoye.destinataire_id == destinataire_id,
        SmsEnvoye.entity_type == entity_type,
        SmsEnvoye.entity_id == entity_id,
        SmsEnvoye.statut == "envoye",
        SmsEnvoye.created_at >= since,
        SmsEnvoye.contenu.contains(event_marker),
    )
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


def build_list_query(
    *,
    entity_type: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
    destinataire_ids: list[int] | None,
) -> Select[tuple[SmsEnvoye]]:
    query = select(SmsEnvoye).order_by(SmsEnvoye.id.desc()).options(
        selectinload(SmsEnvoye.destinataire).selectinload(Destinataire.utilisateur),
    )

    if entity_type is not None:
        query = query.where(SmsEnvoye.entity_type == entity_type)
    if statut is not None:
        query = query.where(SmsEnvoye.statut == statut)
    if date_debut is not None:
        query = query.where(SmsEnvoye.created_at >= date_debut)
    if date_fin is not None:
        query = query.where(SmsEnvoye.created_at <= date_fin)
    if destinataire_ids is not None:
        if not destinataire_ids:
            query = query.where(SmsEnvoye.id == -1)
        else:
            query = query.where(SmsEnvoye.destinataire_id.in_(destinataire_ids))

    return query
