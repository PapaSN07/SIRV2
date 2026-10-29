"""Repository — données du rapport hebdomadaire d'exploitation (Direction de la Distribution)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import BigInteger, cast, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Region, Service
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder


@dataclass(frozen=True)
class LigneHebdo:
    """Une interruption distribution, avec ce qu'il faut pour la classer et la décrire."""

    id: int
    numero: int
    statut: str
    date_apparition: datetime
    date_remise: datetime | None
    duree_minutes: int | None
    service_id: int | None
    service_code: str | None
    region_libelle: str | None
    feeder: str | None
    nature: str | None
    cause: str | None
    end_mwh: float
    clients: int
    localisation: str | None


async def lister_interruptions(
    db: AsyncSession, debut: datetime, fin: datetime, *, detail: bool = True
) -> list[LigneHebdo]:
    """Interruptions distribution apparues dans [debut, fin[, tous statuts.

    `detail=False` (cumuls annuels) : sans les clients des postes, plus léger.
    """
    clients_sq = (
        select(
            PosteInterruption.interruption_id.label("interruption_id"),
            func.sum(
                cast(
                    func.coalesce(
                        PosteInterruption.nombre_clients_estime, PosteInterruption.nombre_clients_touches, 0
                    ),
                    BigInteger,
                )
            ).label("clients"),
        )
        .join(Interruption, Interruption.id == PosteInterruption.interruption_id)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .group_by(PosteInterruption.interruption_id)
        .subquery()
    )
    colonnes = [
        Interruption.id,
        Interruption.numero_interruption,
        Interruption.statut,
        Interruption.date_apparition,
        Interruption.date_remise,
        Interruption.duree_minutes,
        Interruption.service_id,
        Service.code.label("service_code"),
        Region.libelle.label("region_libelle"),
        Feeder.libelle.label("feeder"),
        Nature.libelle.label("nature"),
        Cause.libelle.label("cause"),
        func.coalesce(InterruptionDistribution.end_mwh, 0).label("end_mwh"),
        Interruption.localisation,
    ]
    if detail:
        colonnes.append(func.coalesce(clients_sq.c.clients, 0).label("clients"))
    stmt = (
        select(*colonnes)
        .select_from(Interruption)
        .outerjoin(Service, Service.id == Interruption.service_id)
        .outerjoin(Region, Region.id == Service.region_id)
        .outerjoin(Feeder, Feeder.id == Interruption.feeder_id)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
        .outerjoin(InterruptionDistribution, InterruptionDistribution.interruption_id == Interruption.id)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .order_by(Interruption.date_apparition)
    )
    if detail:
        stmt = stmt.outerjoin(clients_sq, clients_sq.c.interruption_id == Interruption.id)
    rows = (await db.execute(stmt)).all()
    return [
        LigneHebdo(
            id=int(r.id),
            numero=int(r.numero_interruption),
            statut=str(r.statut),
            date_apparition=r.date_apparition,
            date_remise=r.date_remise,
            duree_minutes=r.duree_minutes,
            service_id=r.service_id,
            service_code=r.service_code,
            region_libelle=r.region_libelle,
            feeder=r.feeder,
            nature=r.nature,
            cause=r.cause,
            end_mwh=float(r.end_mwh or 0),
            clients=int(r.clients or 0) if detail else 0,
            localisation=r.localisation,
        )
        for r in rows
    ]


async def objectif_end_annuel(db: AsyncSession, annee: int) -> float | None:
    """Objectif END national de l'année (MWh), saisi dans Pilotage."""
    from app.models.indicateurs import ObjectifIndicateur

    valeur = await db.scalar(
        select(ObjectifIndicateur.valeur_annuelle).where(
            ObjectifIndicateur.annee == annee,
            ObjectifIndicateur.code == "END",
            ObjectifIndicateur.region_id.is_(None),
        )
    )
    return float(valeur) if valeur is not None else None


async def services_distribution(db: AsyncSession) -> list[tuple[int, str, str | None]]:
    """(id, code, libellé de région) des services actifs."""
    rows = (
        await db.execute(
            select(Service.id, Service.code, Region.libelle)
            .outerjoin(Region, Region.id == Service.region_id)
            .where(Service.is_active == true())
            .order_by(Service.code)
        )
    ).all()
    return [(int(r[0]), str(r[1]), r[2]) for r in rows]
