"""Service — collecte données rapport mensuel transport HTB (Sprint 6.3)."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import rapport_transport_repository as repo

_DEFAULT_TOP_EQUIPEMENTS_LIMIT = 10
_MAX_TOP_EQUIPEMENTS_LIMIT = 50


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_TOP_EQUIPEMENTS_LIMIT))


@dataclass(frozen=True)
class MensuelTransportReportData:
    annee: int
    mois: int
    top_equipements_limit: int
    end_cumulee_mwh: float
    nombre_interruptions: int
    interruptions: list[repo.TransportInterruptionRow]
    top_equipements: list[repo.TransportEquipementRow]


async def collect_mensuel_transport_data(
    db: AsyncSession,
    *,
    annee: int,
    mois: int,
    top_equipements_limit: int = _DEFAULT_TOP_EQUIPEMENTS_LIMIT,
) -> MensuelTransportReportData:
    clamped_limit = _clamp_limit(top_equipements_limit)
    interruptions = await repo.list_interruptions_for_month(db, annee=annee, mois=mois)
    top_equipements = await repo.aggregate_equipements_for_month(
        db,
        annee=annee,
        mois=mois,
        limit=clamped_limit,
    )
    end_cumulee = sum(row.end_mwh for row in interruptions)

    return MensuelTransportReportData(
        annee=annee,
        mois=mois,
        top_equipements_limit=clamped_limit,
        end_cumulee_mwh=end_cumulee,
        nombre_interruptions=len(interruptions),
        interruptions=interruptions,
        top_equipements=top_equipements,
    )
