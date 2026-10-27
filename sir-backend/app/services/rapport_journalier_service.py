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
    # Rapport hebdomadaire : dernier jour inclus de la période (None = un seul jour)
    date_fin: date | None = None

    @property
    def titre_periode(self) -> str:
        if self.date_fin is None or self.date_fin == self.report_date:
            return f"Rapport journalier SIR — {self.report_date.strftime('%d/%m/%Y')}"
        return (
            f"Rapport hebdomadaire SIR — du {self.report_date.strftime('%d/%m/%Y')}"
            f" au {self.date_fin.strftime('%d/%m/%Y')}"
        )

    @property
    def multi_jours(self) -> bool:
        return self.date_fin is not None and self.date_fin != self.report_date


async def collect_journalier_data(
    db: AsyncSession,
    *,
    report_date: date,
    region_id: int | None,
    service_id: int | None,
    include_transport: bool,
    date_fin: date | None = None,
) -> JournalierReportData:
    interruptions = await repo.list_interruptions_for_day(
        db,
        report_date=report_date,
        service_id=service_id,
        region_id=region_id,
        include_transport=include_transport,
        date_fin=date_fin,
    )
    feeders = await repo.aggregate_feeders_for_day(
        db,
        report_date=report_date,
        service_id=service_id,
        region_id=region_id,
        date_fin=date_fin,
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
        date_fin=date_fin,
    )
