"""Repository — données rapport journalier (interruptions du jour)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.geo import Agence, Delegation, Service
from app.models.indicateurs import EnergieNd
from app.models.interruptions import Interruption, InterruptionTransport
from app.models.reseau import Feeder


def _day_bounds(report_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(report_date, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def _service_ids_in_region_subquery(region_id: int):
    return (
        select(Service.id)
        .join(Agence, Service.agence_id == Agence.id)
        .join(Delegation, Agence.delegation_id == Delegation.id)
        .where(Delegation.region_id == region_id)
    )


def _apply_scope(
    query,
    *,
    service_id: int | None,
    region_id: int | None,
):
    if service_id is not None:
        return query.where(Interruption.service_id == service_id)
    if region_id is not None:
        return query.where(
            Interruption.service_id.in_(_service_ids_in_region_subquery(region_id))
        )
    return query


@dataclass(frozen=True)
class JournalierInterruptionRow:
    id: int
    numero_interruption: int
    type_direction: str
    statut: str
    date_apparition: datetime
    date_remise: datetime | None
    feeder_code: str | None
    feeder_libelle: str | None
    end_mwh: float
    nombre_clients: int | None
    service_id: int | None
    libelle_reseau: str | None


@dataclass(frozen=True)
class JournalierFeederRow:
    feeder_id: int
    code: str
    libelle: str
    nombre_interruptions: int
    end_mwh: float


async def list_interruptions_for_day(
    db: AsyncSession,
    *,
    report_date: date,
    service_id: int | None = None,
    region_id: int | None = None,
    include_transport: bool = False,
) -> list[JournalierInterruptionRow]:
    start, end = _day_bounds(report_date)
    type_values = ["distribution"]
    if include_transport:
        type_values.extend(["transport", "omvg"])

    query = (
        select(Interruption)
        .options(
            joinedload(Interruption.feeder),
            joinedload(Interruption.energie_nd),
            joinedload(Interruption.interruption_transport).joinedload(
                InterruptionTransport.equipement_transport
            ),
        )
        .where(
            Interruption.type_direction.in_(type_values),
            Interruption.date_apparition >= start,
            Interruption.date_apparition < end,
        )
    )
    query = _apply_scope(query, service_id=service_id, region_id=region_id)
    query = query.order_by(Interruption.date_apparition.asc())

    result = await db.execute(query)
    interruptions = result.unique().scalars().all()

    rows: list[JournalierInterruptionRow] = []
    for item in interruptions:
        end_mwh = 0.0
        if item.energie_nd is not None:
            end_mwh = float(item.energie_nd.valeur_mwh)
        elif item.interruption_transport is not None and item.interruption_transport.energie_non_fournie_mwh:
            end_mwh = float(item.interruption_transport.energie_non_fournie_mwh)

        libelle_reseau = None
        if item.type_direction == "distribution" and item.feeder is not None:
            libelle_reseau = item.feeder.libelle
        elif item.interruption_transport and item.interruption_transport.equipement_transport:
            libelle_reseau = item.interruption_transport.equipement_transport.libelle

        rows.append(
            JournalierInterruptionRow(
                id=item.id,
                numero_interruption=item.numero_interruption,
                type_direction=item.type_direction,
                statut=item.statut,
                date_apparition=item.date_apparition,
                date_remise=item.date_remise,
                feeder_code=item.feeder.code if item.feeder else None,
                feeder_libelle=item.feeder.libelle if item.feeder else None,
                end_mwh=end_mwh,
                nombre_clients=item.nombre_clients_touches,
                service_id=item.service_id,
                libelle_reseau=libelle_reseau,
            )
        )
    return rows


async def aggregate_feeders_for_day(
    db: AsyncSession,
    *,
    report_date: date,
    service_id: int | None = None,
    region_id: int | None = None,
) -> list[JournalierFeederRow]:
    start, end = _day_bounds(report_date)

    query = (
        select(
            Feeder.id,
            Feeder.code,
            Feeder.libelle,
            func.count(Interruption.id).label("nb"),
            func.coalesce(func.sum(EnergieNd.valeur_mwh), 0).label("end_mwh"),
        )
        .join(Interruption, Interruption.feeder_id == Feeder.id)
        .outerjoin(EnergieNd, EnergieNd.interruption_id == Interruption.id)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.feeder_id.isnot(None),
            Interruption.date_apparition >= start,
            Interruption.date_apparition < end,
        )
        .group_by(Feeder.id, Feeder.code, Feeder.libelle)
        .order_by(func.coalesce(func.sum(EnergieNd.valeur_mwh), 0).desc())
    )
    query = _apply_scope(query, service_id=service_id, region_id=region_id)

    result = await db.execute(query)
    return [
        JournalierFeederRow(
            feeder_id=row.id,
            code=row.code,
            libelle=row.libelle,
            nombre_interruptions=int(row.nb),
            end_mwh=float(row.end_mwh),
        )
        for row in result.all()
    ]
