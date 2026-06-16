"""Repository — données rapport mensuel transport HTB."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.indicateurs import EnergieNd
from app.models.interruptions import Interruption, InterruptionTransport
from app.models.reseau import EquipementTransport, SourceTransport

_TRANSPORT_TYPES = ("transport", "omvg")


@dataclass(frozen=True)
class TransportInterruptionRow:
    id: int
    numero_interruption: int
    type_direction: str
    statut: str
    date_apparition: datetime
    date_remise: datetime | None
    equipement_code: str | None
    equipement_libelle: str | None
    source_libelle: str | None
    end_mwh: float
    puissance_transit_mw: float | None
    duree_minutes: int | None


@dataclass(frozen=True)
class TransportEquipementRow:
    equipement_id: int
    code: str
    libelle: str
    nombre_interruptions: int
    end_mwh: float


def _month_filters(annee: int, mois: int):
    return (
        extract("year", Interruption.date_apparition) == annee,
        extract("month", Interruption.date_apparition) == mois,
    )


def _end_value_expr():
    return func.coalesce(
        EnergieNd.valeur_mwh,
        InterruptionTransport.energie_non_fournie_mwh,
        0,
    )


async def list_interruptions_for_month(
    db: AsyncSession,
    *,
    annee: int,
    mois: int,
) -> list[TransportInterruptionRow]:
    query = (
        select(Interruption)
        .options(
            joinedload(Interruption.energie_nd),
            joinedload(Interruption.interruption_transport).joinedload(
                InterruptionTransport.equipement_transport
            ),
            joinedload(Interruption.interruption_transport).joinedload(
                InterruptionTransport.source_transport
            ),
        )
        .join(
            InterruptionTransport,
            InterruptionTransport.interruption_id == Interruption.id,
        )
        .where(
            Interruption.type_direction.in_(_TRANSPORT_TYPES),
            *_month_filters(annee, mois),
        )
        .order_by(Interruption.date_apparition.asc())
    )

    result = await db.execute(query)
    interruptions = result.unique().scalars().all()
    rows: list[TransportInterruptionRow] = []

    for item in interruptions:
        end_mwh = 0.0
        if item.energie_nd is not None:
            end_mwh = float(item.energie_nd.valeur_mwh)
        elif item.interruption_transport and item.interruption_transport.energie_non_fournie_mwh:
            end_mwh = float(item.interruption_transport.energie_non_fournie_mwh)

        transport = item.interruption_transport
        equipement = transport.equipement_transport if transport else None
        source = transport.source_transport if transport else None

        rows.append(
            TransportInterruptionRow(
                id=item.id,
                numero_interruption=item.numero_interruption,
                type_direction=item.type_direction,
                statut=item.statut,
                date_apparition=item.date_apparition,
                date_remise=item.date_remise,
                equipement_code=equipement.code if equipement else None,
                equipement_libelle=equipement.libelle if equipement else None,
                source_libelle=source.libelle if source else None,
                end_mwh=end_mwh,
                puissance_transit_mw=float(transport.puissance_transit_mw)
                if transport and transport.puissance_transit_mw is not None
                else None,
                duree_minutes=item.duree_minutes,
            )
        )
    return rows


async def aggregate_equipements_for_month(
    db: AsyncSession,
    *,
    annee: int,
    mois: int,
    limit: int = 10,
) -> list[TransportEquipementRow]:
    query = (
        select(
            EquipementTransport.id,
            EquipementTransport.code,
            EquipementTransport.libelle,
            func.count(Interruption.id).label("nb"),
            func.coalesce(func.sum(_end_value_expr()), 0).label("end_mwh"),
        )
        .join(
            InterruptionTransport,
            InterruptionTransport.equipement_transport_id == EquipementTransport.id,
        )
        .join(Interruption, Interruption.id == InterruptionTransport.interruption_id)
        .outerjoin(EnergieNd, EnergieNd.interruption_id == Interruption.id)
        .where(
            Interruption.type_direction.in_(_TRANSPORT_TYPES),
            InterruptionTransport.equipement_transport_id.isnot(None),
            *_month_filters(annee, mois),
        )
        .group_by(
            EquipementTransport.id,
            EquipementTransport.code,
            EquipementTransport.libelle,
        )
        .order_by(func.coalesce(func.sum(_end_value_expr()), 0).desc())
        .limit(limit)
    )

    result = await db.execute(query)
    return [
        TransportEquipementRow(
            equipement_id=row.id,
            code=row.code,
            libelle=row.libelle,
            nombre_interruptions=int(row.nb),
            end_mwh=float(row.end_mwh),
        )
        for row in result.all()
    ]


async def aggregate_end_for_month(
    db: AsyncSession,
    *,
    annee: int,
    mois: int,
) -> float:
    query = (
        select(func.coalesce(func.sum(_end_value_expr()), 0))
        .select_from(Interruption)
        .join(
            InterruptionTransport,
            InterruptionTransport.interruption_id == Interruption.id,
        )
        .outerjoin(EnergieNd, EnergieNd.interruption_id == Interruption.id)
        .where(
            Interruption.type_direction.in_(_TRANSPORT_TYPES),
            *_month_filters(annee, mois),
        )
    )
    result = await db.execute(query)
    return float(result.scalar_one())
