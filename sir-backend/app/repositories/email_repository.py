"""Repository — traces emails envoyés."""

from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications import EmailEnvoye


async def get_by_id(db: AsyncSession, email_id: int) -> EmailEnvoye | None:
    result = await db.execute(
        select(EmailEnvoye)
        .options(selectinload(EmailEnvoye.destinataire))
        .where(EmailEnvoye.id == email_id)
    )
    return result.scalar_one_or_none()


async def create_pending(
    db: AsyncSession,
    *,
    destinataire_id: int,
    entity_type: str | None,
    entity_id: int | None,
    sujet: str,
    corps: str,
) -> EmailEnvoye:
    record = EmailEnvoye(
        destinataire_id=destinataire_id,
        entity_type=entity_type,
        entity_id=entity_id,
        sujet=sujet,
        corps=corps,
        statut="en_attente",
    )
    db.add(record)
    await db.flush()
    return record


async def update_statut(
    db: AsyncSession,
    record: EmailEnvoye,
    *,
    statut: str,
    sent_at: datetime | None = None,
    erreur: str | None = None,
) -> EmailEnvoye:
    record.statut = statut
    if sent_at is not None:
        record.sent_at = sent_at
    if erreur is not None:
        record.erreur = erreur
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
    query = select(EmailEnvoye.id).where(
        EmailEnvoye.destinataire_id == destinataire_id,
        EmailEnvoye.entity_type == entity_type,
        EmailEnvoye.entity_id == entity_id,
        EmailEnvoye.statut == "envoye",
        EmailEnvoye.created_at >= since,
        EmailEnvoye.sujet.contains(event_marker),
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
) -> Select[tuple[EmailEnvoye]]:
    query = select(EmailEnvoye).order_by(EmailEnvoye.id.desc())

    if entity_type is not None:
        query = query.where(EmailEnvoye.entity_type == entity_type)
    if statut is not None:
        query = query.where(EmailEnvoye.statut == statut)
    if date_debut is not None:
        query = query.where(EmailEnvoye.created_at >= date_debut)
    if date_fin is not None:
        query = query.where(EmailEnvoye.created_at <= date_fin)
    if destinataire_ids is not None:
        if not destinataire_ids:
            query = query.where(EmailEnvoye.id == -1)
        else:
            query = query.where(EmailEnvoye.destinataire_id.in_(destinataire_ids))

    return query
