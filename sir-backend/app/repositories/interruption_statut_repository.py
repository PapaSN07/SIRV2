"""Repository — historique des statuts, gel mensuel, détection des retards."""

from datetime import datetime

from sqlalchemy import delete, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.indicateurs import EnergieNd
from app.models.interruption_statut_historique import ACTION_CLOTURE, InterruptionStatutHistorique
from app.models.interruptions import Interruption, InterruptionDistribution, InterruptionTransport


async def ajouter(
    db: AsyncSession,
    *,
    interruption_id: int,
    action: str,
    ancien_statut: str | None,
    nouveau_statut: str,
    utilisateur_id: int,
    motif: str | None = None,
) -> InterruptionStatutHistorique:
    row = InterruptionStatutHistorique(
        interruption_id=interruption_id,
        action=action,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        utilisateur_id=utilisateur_id,
        motif=motif,
    )
    db.add(row)
    await db.flush()
    return row


async def lister(db: AsyncSession, interruption_id: int) -> list[InterruptionStatutHistorique]:
    result = await db.execute(
        select(InterruptionStatutHistorique)
        .options(joinedload(InterruptionStatutHistorique.utilisateur))
        .where(InterruptionStatutHistorique.interruption_id == interruption_id)
        .order_by(InterruptionStatutHistorique.created_at, InterruptionStatutHistorique.id)
    )
    return list(result.scalars().all())


async def dates_cloture(db: AsyncSession, interruption_ids: list[int]) -> dict[int, datetime]:
    """Date de la dernière clôture de chaque interruption (ancienneté dans la file de validation)."""
    if not interruption_ids:
        return {}
    result = await db.execute(
        select(
            InterruptionStatutHistorique.interruption_id,
            func.max(InterruptionStatutHistorique.created_at),
        )
        .where(
            InterruptionStatutHistorique.interruption_id.in_(interruption_ids),
            InterruptionStatutHistorique.action == ACTION_CLOTURE,
        )
        .group_by(InterruptionStatutHistorique.interruption_id)
    )
    return {int(i): d for i, d in result.all()}


async def supprimer_end(db: AsyncSession, interruption_id: int) -> None:
    """Après un renvoi en correction, l'END n'a plus de date de remise : on l'efface."""
    await db.execute(delete(EnergieNd).where(EnergieNd.interruption_id == interruption_id))
    for model in (InterruptionDistribution, InterruptionTransport):
        row = (
            await db.execute(select(model).where(model.interruption_id == interruption_id))
        ).scalar_one_or_none()
        if row is not None and hasattr(row, "end_mwh"):
            row.end_mwh = None
    await db.flush()


async def lister_validees_du_mois(
    db: AsyncSession,
    *,
    type_direction: str,
    annee: int,
    mois: int,
    service_ids: list[int] | None = None,
) -> list[Interruption]:
    query = select(Interruption).where(
        Interruption.type_direction == type_direction,
        Interruption.statut == "valide",
        extract("year", Interruption.date_apparition) == annee,
        extract("month", Interruption.date_apparition) == mois,
    )
    if service_ids is not None:
        query = query.where(Interruption.service_id.in_(service_ids))
    return list((await db.execute(query)).scalars().all())


async def compter_non_validees_du_mois(
    db: AsyncSession, *, type_direction: str, annee: int, mois: int
) -> int:
    return int(
        await db.scalar(
            select(func.count(Interruption.id)).where(
                Interruption.type_direction == type_direction,
                Interruption.statut.in_(("en_cours", "cloture")),
                extract("year", Interruption.date_apparition) == annee,
                extract("month", Interruption.date_apparition) == mois,
            )
        )
        or 0
    )


async def lister_en_retard(db: AsyncSession, *, avant: datetime) -> list[tuple[Interruption, str]]:
    """Interruptions en cours apparues avant `avant`, et clôturées avant `avant` non validées."""
    en_cours = (
        await db.execute(
            select(Interruption).where(
                Interruption.statut == "en_cours", Interruption.date_apparition < avant
            )
        )
    ).scalars().all()
    derniere_cloture = (
        select(
            InterruptionStatutHistorique.interruption_id.label("iid"),
            func.max(InterruptionStatutHistorique.created_at).label("le"),
        )
        .where(InterruptionStatutHistorique.action == ACTION_CLOTURE)
        .group_by(InterruptionStatutHistorique.interruption_id)
        .subquery()
    )
    # Sans historique (clôtures antérieures à cette version) : date de dernière mise à jour
    clotures = (
        await db.execute(
            select(Interruption)
            .outerjoin(derniere_cloture, derniere_cloture.c.iid == Interruption.id)
            .where(
                Interruption.statut == "cloture",
                func.coalesce(derniere_cloture.c.le, Interruption.updated_at) < avant,
            )
        )
    ).scalars().all()
    return [(i, "en_cours") for i in en_cours] + [(i, "non_validee") for i in clotures]


async def appliquer(db: AsyncSession, interruption: Interruption, **valeurs: object) -> None:
    """Met à jour les colonnes d'une interruption déjà chargée (statut_id suit via l'événement ORM)."""
    for nom, valeur in valeurs.items():
        setattr(interruption, nom, valeur)
    await db.flush()
