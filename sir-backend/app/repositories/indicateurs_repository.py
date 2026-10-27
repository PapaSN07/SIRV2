"""Repository — requêtes agrégées indicateurs END / SAIFI / SAIDI (Sprint 5.4)."""

from dataclasses import dataclass

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Service
from app.models.indicateurs import EnergieNd, SaifiSaidi
from app.models.interruptions import Interruption, InterruptionDistribution, STATUTS_CLOTURES
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder
from app.repositories import saifi_saidi_repository as saifi_repo


@dataclass(frozen=True)
class EndServiceRow:
    service_id: int
    end_mwh: float
    nombre_interruptions: int


@dataclass(frozen=True)
class CauseRepartitionRow:
    label: str
    nombre: int


@dataclass(frozen=True)
class NatureRepartitionRow:
    """Agrégat par nature — aligne sur le format Tableau de Bord FIS."""
    code: str
    libelle: str
    nombre: int
    end_mwh: float


@dataclass(frozen=True)
class NatureServiceRow:
    """Agrégat nature × service — nombre d'interruptions et END."""

    nature_code: str
    nature_libelle: str
    service_id: int
    service_code: str
    service_libelle: str
    nombre: int
    end_mwh: float


async def aggregate_end_by_services(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> list[EndServiceRow]:
    if not service_ids:
        return []

    # Données migrées HFSQL : ENDD → interruptions_distribution.end_mwh
    result = await db.execute(
        select(
            Interruption.service_id,
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
            func.count(Interruption.id).label("nb"),
        )
        .join(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.service_id.in_(service_ids),
            Interruption.type_direction == "distribution",
            Interruption.statut.in_(STATUTS_CLOTURES),
            Interruption.is_force_majeure == False,  # noqa: E712
            Interruption.date_remise.isnot(None),
            extract("year", Interruption.date_remise) == annee,
            extract("month", Interruption.date_remise) == mois,
            InterruptionDistribution.end_mwh.isnot(None),
        )
        .group_by(Interruption.service_id)
    )

    rows = [
        EndServiceRow(
            service_id=row.service_id,
            end_mwh=float(row.end_mwh),
            nombre_interruptions=int(row.nb),
        )
        for row in result.all()
    ]
    if rows:
        return rows

    # Repli : détail EnergieND si présent (futur import poste_interruption)
    result_nd = await db.execute(
        select(
            Interruption.service_id,
            func.coalesce(func.sum(EnergieNd.valeur_mwh), 0).label("end_mwh"),
            func.count(EnergieNd.id).label("nb"),
        )
        .join(EnergieNd, EnergieNd.interruption_id == Interruption.id)
        .where(
            Interruption.service_id.in_(service_ids),
            Interruption.statut.in_(STATUTS_CLOTURES),
            EnergieNd.est_force_majeure == False,  # noqa: E712
            Interruption.date_remise.isnot(None),
            extract("year", Interruption.date_remise) == annee,
            extract("month", Interruption.date_remise) == mois,
        )
        .group_by(Interruption.service_id)
    )
    return [
        EndServiceRow(
            service_id=row.service_id,
            end_mwh=float(row.end_mwh),
            nombre_interruptions=int(row.nb),
        )
        for row in result_nd.all()
    ]


@dataclass(frozen=True)
class EndFeederRow:
    feeder_id: int
    code: str
    libelle: str
    service_id: int | None
    end_mwh: float
    nombre_interruptions: int


async def aggregate_end_by_feeders(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
    limit: int,
) -> list[EndFeederRow]:
    if not service_ids:
        return []

    result = await db.execute(
        select(
            Feeder.id,
            Feeder.code,
            Feeder.libelle,
            Feeder.service_id,
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
            func.count(Interruption.id).label("nb"),
        )
        .join(Interruption, Interruption.feeder_id == Feeder.id)
        .join(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.type_direction == "distribution",
            Interruption.feeder_id.isnot(None),
            Interruption.service_id.in_(service_ids),
            Interruption.statut.in_(STATUTS_CLOTURES),
            Interruption.is_force_majeure == False,  # noqa: E712
            Interruption.date_remise.isnot(None),
            extract("year", Interruption.date_remise) == annee,
            extract("month", Interruption.date_remise) == mois,
            InterruptionDistribution.end_mwh.isnot(None),
        )
        .group_by(Feeder.id, Feeder.code, Feeder.libelle, Feeder.service_id)
        .order_by(func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).desc())
        .limit(limit)
    )

    return [
        EndFeederRow(
            feeder_id=row.id,
            code=row.code,
            libelle=row.libelle,
            service_id=row.service_id,
            end_mwh=float(row.end_mwh),
            nombre_interruptions=int(row.nb),
        )
        for row in result.all()
    ]


async def list_service_ids_for_region(db: AsyncSession, region_id: int) -> list[int]:
    return await saifi_repo.list_service_ids_for_region(db, region_id)


async def list_all_service_ids(db: AsyncSession) -> list[int]:
    return await saifi_repo.list_all_service_ids(db)



async def list_saifi_saidi_for_services(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> list[SaifiSaidi]:
    return await saifi_repo.list_saifi_saidi_for_services(
        db, service_ids=service_ids, annee=annee, mois=mois
    )


def _apply_interruption_filters(
    query,
    *,
    statut: str | None,
    annee: int | None,
    mois: int | None,
):
    if statut is not None:
        query = query.where(Interruption.statut == statut)
    if annee is not None and mois is not None:
        query = query.where(
            extract("year", Interruption.date_apparition) == annee,
            extract("month", Interruption.date_apparition) == mois,
        )
    return query


async def count_distribution_interruptions(
    db: AsyncSession,
    *,
    service_ids: list[int],
    statut: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
) -> int:
    if not service_ids:
        return 0

    query = select(func.count()).select_from(Interruption).where(
        Interruption.type_direction == "distribution",
        Interruption.service_id.in_(service_ids),
    )
    query = _apply_interruption_filters(query, statut=statut, annee=annee, mois=mois)
    result = await db.execute(query)
    return int(result.scalar_one())


async def aggregate_interruptions_by_cause(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
    limit: int = 5,
) -> list[CauseRepartitionRow]:
    if not service_ids:
        return []

    result = await db.execute(
        select(
            func.coalesce(Cause.libelle, "Non renseignée").label("label"),
            func.count(Interruption.id).label("nombre"),
        )
        .select_from(Interruption)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.service_id.in_(service_ids),
            extract("year", Interruption.date_apparition) == annee,
            extract("month", Interruption.date_apparition) == mois,
        )
        .group_by(Cause.libelle)
        .order_by(func.count(Interruption.id).desc())
        .limit(limit)
    )
    return [
        CauseRepartitionRow(label=row.label, nombre=int(row.nombre))
        for row in result.all()
    ]


async def aggregate_interruptions_by_nature(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> list[NatureRepartitionRow]:
    """Agregation par nature -- format Tableau de Bord FIS."""
    if not service_ids:
        return []

    result = await db.execute(
        select(
            func.coalesce(Nature.code, "AUTRE").label("code"),
            func.coalesce(Nature.libelle, "Non renseignee").label("libelle"),
            func.count(Interruption.id).label("nombre"),
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
        )
        .select_from(Interruption)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.type_direction == "distribution",
            Interruption.service_id.in_(service_ids),
            Interruption.statut.in_(STATUTS_CLOTURES),
            extract("year", Interruption.date_apparition) == annee,
            extract("month", Interruption.date_apparition) == mois,
        )
        .group_by(Nature.code, Nature.libelle)
        .order_by(func.count(Interruption.id).desc())
    )

    _ORDER = ["PERMANENT", "SEMI_PERM", "FUGITIF", "DELESTAGE", "COUPURE"]
    rows = [
        NatureRepartitionRow(
            code=row.code,
            libelle=row.libelle,
            nombre=int(row.nombre),
            end_mwh=float(row.end_mwh),
        )
        for row in result.all()
    ]
    rows.sort(key=lambda r: _ORDER.index(r.code) if r.code in _ORDER else len(_ORDER))
    return rows


async def aggregate_interruptions_by_nature_and_service(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> list[NatureServiceRow]:
    """Nombre d'interruptions et END par nature et par service (période mensuelle)."""
    if not service_ids:
        return []

    result = await db.execute(
        select(
            Nature.code.label("nature_code"),
            Nature.libelle.label("nature_libelle"),
            Service.id.label("service_id"),
            Service.code.label("service_code"),
            Service.libelle.label("service_libelle"),
            func.count(Interruption.id).label("nombre"),
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
        )
        .select_from(Interruption)
        .join(Service, Service.id == Interruption.service_id)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.type_direction == "distribution",
            Interruption.service_id.in_(service_ids),
            Interruption.statut.in_(STATUTS_CLOTURES),
            extract("year", Interruption.date_apparition) == annee,
            extract("month", Interruption.date_apparition) == mois,
        )
        .group_by(
            Nature.code,
            Nature.libelle,
            Service.id,
            Service.code,
            Service.libelle,
        )
    )
    return [
        NatureServiceRow(
            nature_code=row.nature_code or "AUTRE",
            nature_libelle=row.nature_libelle or "Non renseignee",
            service_id=int(row.service_id),
            service_code=row.service_code,
            service_libelle=row.service_libelle,
            nombre=int(row.nombre),
            end_mwh=float(row.end_mwh),
        )
        for row in result.all()
    ]


async def count_transport_interruptions(
    db: AsyncSession,
    *,
    statut: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
) -> int:
    query = select(func.count()).select_from(Interruption).where(
        Interruption.type_direction == "transport",
    )
    query = _apply_interruption_filters(query, statut=statut, annee=annee, mois=mois)
    result = await db.execute(query)
    return int(result.scalar_one())
