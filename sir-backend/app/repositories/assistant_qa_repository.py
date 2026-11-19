"""Repository — questions en langage courant posées à l'Assistant (statistiques d'exploitation)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, Select, cast, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Service
from app.models.interruptions import STATUTS_CLOTURES, Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder, Poste, PosteSource


@dataclass(frozen=True)
class Filtre:
    """Périmètre d'une question : période (apparition), services du compte, départs cités."""

    debut: datetime
    fin: datetime
    service_ids: list[int] | None = None
    feeder_ids: list[int] | None = None


def _conditions(f: Filtre, *, par_remise: bool = False, avec_periode: bool = True) -> list[Any]:
    conditions: list[Any] = [Interruption.type_direction == "distribution"]
    if avec_periode:
        colonne = Interruption.date_remise if par_remise else Interruption.date_apparition
        conditions += [colonne >= f.debut, colonne < f.fin]
    if f.service_ids is not None:
        conditions.append(Interruption.service_id.in_(f.service_ids))
    if f.feeder_ids:
        conditions.append(Interruption.feeder_id.in_(f.feeder_ids))
    return conditions


async def lister_services(db: AsyncSession) -> list[tuple[int, str, str]]:
    rows = (await db.execute(select(Service.id, Service.code, Service.libelle).where(Service.is_active == true()))).all()
    return [(int(r.id), str(r.code or ""), str(r.libelle or "")) for r in rows]


async def postes_plus_impactes(db: AsyncSession, f: Filtre, limite: int) -> list[Any]:
    """Postes coupés le plus souvent : interruptions distinctes, clients cumulés, heures de coupure."""
    clients = cast(
        func.coalesce(PosteInterruption.nombre_clients_estime, PosteInterruption.nombre_clients_touches, 0),
        BigInteger,
    )
    duree_h = cast(func.coalesce(Interruption.duree_minutes, 0), Float) / 60.0
    query: Select[Any] = (
        select(
            Poste.libelle.label("poste"),
            Poste.code.label("code"),
            Feeder.libelle.label("feeder"),
            func.count(func.distinct(Interruption.id)).label("nombre"),
            func.sum(clients).label("clients"),
            func.sum(duree_h).label("heures"),
        )
        .select_from(PosteInterruption)
        .join(Interruption, Interruption.id == PosteInterruption.interruption_id)
        .join(Poste, Poste.id == PosteInterruption.poste_id)
        .outerjoin(Feeder, Feeder.id == Interruption.feeder_id)
        .where(*_conditions(f))
        .group_by(Poste.libelle, Poste.code, Feeder.libelle)
        .order_by(func.count(func.distinct(Interruption.id)).desc(), Poste.libelle)
        .limit(limite)
    )
    return list((await db.execute(query)).all())


async def feeders_plus_perturbes(db: AsyncSession, f: Filtre, limite: int) -> list[Any]:
    end = cast(func.coalesce(InterruptionDistribution.end_mwh, 0), Float)
    query = (
        select(
            Feeder.libelle.label("feeder"),
            PosteSource.libelle.label("poste_source"),
            func.count(Interruption.id).label("nombre"),
            func.sum(end).label("end_mwh"),
            func.sum(cast(func.coalesce(Interruption.duree_minutes, 0), Float)).label("minutes"),
        )
        .select_from(Interruption)
        .join(Feeder, Feeder.id == Interruption.feeder_id)
        .outerjoin(PosteSource, PosteSource.id == Feeder.poste_source_id)
        .outerjoin(InterruptionDistribution, InterruptionDistribution.interruption_id == Interruption.id)
        .where(*_conditions(f), Interruption.is_force_majeure == False)  # noqa: E712
        .group_by(Feeder.libelle, PosteSource.libelle)
        .order_by(func.count(Interruption.id).desc(), Feeder.libelle)
        .limit(limite)
    )
    return list((await db.execute(query)).all())


async def end_mwh(db: AsyncSession, f: Filtre) -> tuple[float, int]:
    """END des interruptions remises dans la période, clôturées ou validées, hors force majeure
    (même définition que la carte « END HTA » du tableau de bord)."""
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(cast(InterruptionDistribution.end_mwh, Float)), 0.0),
                func.count(Interruption.id),
            )
            .select_from(Interruption)
            .join(InterruptionDistribution, InterruptionDistribution.interruption_id == Interruption.id)
            .where(
                *_conditions(f, par_remise=True),
                Interruption.statut.in_(STATUTS_CLOTURES),
                Interruption.is_force_majeure == False,  # noqa: E712
            )
        )
    ).one()
    return float(row[0] or 0), int(row[1] or 0)


async def compter(db: AsyncSession, f: Filtre, *, statut: str | None = None, sans_periode: bool = False) -> int:
    conditions = _conditions(f, avec_periode=not sans_periode)
    if statut:
        conditions.append(Interruption.statut == statut)
    return int(await db.scalar(select(func.count(Interruption.id)).where(*conditions)) or 0)


async def par_nature(db: AsyncSession, f: Filtre) -> list[Any]:
    return list(
        (
            await db.execute(
                select(func.coalesce(Nature.libelle, "Non renseignée").label("libelle"), func.count(Interruption.id).label("nombre"))
                .select_from(Interruption)
                .outerjoin(Nature, Nature.id == Interruption.nature_id)
                .where(*_conditions(f))
                .group_by(func.coalesce(Nature.libelle, "Non renseignée"))
                .order_by(func.count(Interruption.id).desc())
            )
        ).all()
    )


async def causes(db: AsyncSession, f: Filtre, limite: int) -> list[Any]:
    return list(
        (
            await db.execute(
                select(func.coalesce(Cause.libelle, "Non renseignée").label("libelle"), func.count(Interruption.id).label("nombre"))
                .select_from(Interruption)
                .outerjoin(Cause, Cause.id == Interruption.cause_id)
                .where(*_conditions(f))
                .group_by(func.coalesce(Cause.libelle, "Non renseignée"))
                .order_by(func.count(Interruption.id).desc())
                .limit(limite)
            )
        ).all()
    )


async def duree_moyenne_minutes(db: AsyncSession, f: Filtre) -> tuple[float | None, int]:
    row = (
        await db.execute(
            select(func.avg(cast(Interruption.duree_minutes, Float)), func.count(Interruption.duree_minutes)).where(
                *_conditions(f), Interruption.duree_minutes.isnot(None)
            )
        )
    ).one()
    return (float(row[0]) if row[0] is not None else None), int(row[1] or 0)


async def interruptions_recentes(db: AsyncSession, f: Filtre, limite: int, *, en_cours: bool = False) -> list[Any]:
    conditions = _conditions(f, avec_periode=not en_cours)
    if en_cours:
        conditions.append(Interruption.statut == "en_cours")
    return list(
        (
            await db.execute(
                select(
                    Interruption.numero_interruption,
                    Interruption.date_apparition,
                    Interruption.date_remise,
                    Interruption.duree_minutes,
                    Feeder.libelle.label("feeder"),
                    func.coalesce(Cause.libelle, "").label("cause"),
                )
                .select_from(Interruption)
                .outerjoin(Feeder, Feeder.id == Interruption.feeder_id)
                .outerjoin(Cause, Cause.id == Interruption.cause_id)
                .where(*conditions)
                .order_by(Interruption.date_apparition.desc())
                .limit(limite)
            )
        ).all()
    )
