"""Service — collecte données rapport journalier (Sprint 6.1)."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import rapport_journalier_repository as repo


@dataclass(frozen=True)
class JournalierReportData:
    report_date: date
    region_id: int | None
    service_id: int | None
    include_transport: bool
    end_cumulee_mwh: float
    nombre_interruptions: int
    interruptions: list[repo.JournalierInterruptionRow]
    feeders: list[repo.JournalierFeederRow]


async def collect_journalier_data(
    db: AsyncSession,
    *,
    report_date: date,
    region_id: int | None,
    service_id: int | None,
    include_transport: bool,
) -> JournalierReportData:
    interruptions = await repo.list_interruptions_for_day(
        db,
        report_date=report_date,
        service_id=service_id,
        region_id=region_id,
        include_transport=include_transport,
    )
    feeders = await repo.aggregate_feeders_for_day(
        db,
        report_date=report_date,
        service_id=service_id,
        region_id=region_id,
    )
    end_cumulee = sum(row.end_mwh for row in interruptions)

    return JournalierReportData(
        report_date=report_date,
        region_id=region_id,
        service_id=service_id,
        include_transport=include_transport,
        end_cumulee_mwh=end_cumulee,
        nombre_interruptions=len(interruptions),
        interruptions=interruptions,
        feeders=feeders,
    )
