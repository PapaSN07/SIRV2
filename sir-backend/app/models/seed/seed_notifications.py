"""Seeder dev — destinataires notifications (Sprint 8)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Service
from app.models.notifications import Destinataire


async def seed_notifications(db: AsyncSession) -> None:
    """Crée des destinataires fictifs pour le service SVC-DKR-01."""
    result = await db.execute(select(Service).where(Service.code == "SVC-DKR-01"))
    service = result.scalar_one_or_none()
    if service is None:
        return

    seeds = [
        ("Alertes Distribution DKR", "+221770000001", "alertes.dkr@senelec.sn"),
        ("Supervision SAQS", None, "saqs.dev@senelec.sn"),
    ]

    for nom, telephone, email in seeds:
        existing = await db.execute(
            select(Destinataire).where(
                Destinataire.nom == nom,
                Destinataire.service_id == service.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        db.add(
            Destinataire(
                nom=nom,
                telephone=telephone,
                email=email,
                service_id=service.id,
                is_active=True,
            )
        )

    await db.flush()
