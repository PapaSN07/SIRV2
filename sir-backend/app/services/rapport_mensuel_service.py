"""Service — collecte données rapport mensuel distribution (Sprint 6.2)."""

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.schemas.indicateurs import (
    EndIndicateurResponse,
    SaifiIndicateurResponse,
    SaidiIndicateurResponse,
    TopFeedersResponse,
)
from app.services import indicateurs_service

_DEFAULT_TOP_FEEDERS_LIMIT = 10
_MAX_TOP_FEEDERS_LIMIT = 50


def _clamp_top_feeders_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_TOP_FEEDERS_LIMIT))


@dataclass(frozen=True)
class MensuelDistributionReportData:
    annee: int
    mois: int
    region_id: int | None
    top_feeders_limit: int
    end: EndIndicateurResponse
    saifi: SaifiIndicateurResponse
    saidi: SaidiIndicateurResponse
    top_feeders: TopFeedersResponse


async def collect_mensuel_distribution_data(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None,
    top_feeders_limit: int = _DEFAULT_TOP_FEEDERS_LIMIT,
) -> MensuelDistributionReportData:
    """Agrège END / SAIFI / SAIDI + top feeders via indicateurs_service."""
    clamped_limit = _clamp_top_feeders_limit(top_feeders_limit)
    end = await indicateurs_service.get_end(
        db,
        redis,
        user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        include_services=True,
        page=1,
        page_size=500,
    )
    saifi = await indicateurs_service.get_saifi(
        db,
        redis,
        user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        include_services=True,
        page=1,
        page_size=500,
    )
    saidi = await indicateurs_service.get_saidi(
        db,
        redis,
        user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        include_services=True,
        page=1,
        page_size=500,
    )
    top_feeders = await indicateurs_service.get_top_feeders(
        db,
        redis,
        user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        limit=clamped_limit,
    )

    return MensuelDistributionReportData(
        annee=annee,
        mois=mois,
        region_id=region_id,
        top_feeders_limit=clamped_limit,
        end=end,
        saifi=saifi,
        saidi=saidi,
        top_feeders=top_feeders,
    )
