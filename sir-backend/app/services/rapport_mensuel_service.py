"""Service — collecte données rapport mensuel distribution (Sprint 6.2)."""

import logging
import statistics
from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.schemas.indicateurs import (
    EndIndicateurResponse,
    SaifiIndicateurResponse,
    SaidiIndicateurResponse,
    TopFeedersResponse,
)
from app.repositories import pilotage_repository
from app.services import indicateurs_service

_DEFAULT_TOP_FEEDERS_LIMIT = 10
_MAX_TOP_FEEDERS_LIMIT = 50


def _clamp_top_feeders_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_TOP_FEEDERS_LIMIT))


@dataclass(frozen=True)
class ServiceCarteEnd:
    """Un service sur la carte du poids de l'END : position (centre de ses nœuds SIG) et part."""

    service_id: int
    code: str
    libelle: str
    end_mwh: float
    part_pct: float
    nombre_interruptions: int
    longitude: float | None
    latitude: float | None


@dataclass(frozen=True)
class CarteEnd:
    services: list[ServiceCarteEnd]
    # Nœuds SIG échantillonnés : fond de carte (le réseau dessine le pays)
    fond: list[tuple[float, float]] = field(default_factory=list)


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
    carte_end: CarteEnd | None = None


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
        carte_end=await _carte_end_ou_rien(db, end),
    )


_FOND_MAX = 6000
logger = logging.getLogger(__name__)


async def _carte_end_ou_rien(db: AsyncSession, end: EndIndicateurResponse) -> CarteEnd | None:
    """La carte est un complément : sans données SIG exploitables, le rapport sort sans elle."""
    try:
        return await construire_carte_end(db, end)
    except Exception:  # noqa: BLE001
        logger.exception("Carte du poids de l'END non construite")
        return None


async def construire_carte_end(db: AsyncSession, end: EndIndicateurResponse) -> CarteEnd:
    """Poids de l'END par service (part du total du périmètre) et position de chaque service."""
    items = [i for i in (end.services.items if end.services else []) if i.end_mwh > 0]
    total = sum(i.end_mwh for i in items)
    libelles = await pilotage_repository.libelles_services(db, [i.service_id for i in items])
    points = await pilotage_repository.points_sig_par_service(db)
    return assembler_carte_end(items, total, libelles, points)


def assembler_carte_end(
    items: list,
    total: float,
    libelles: dict[int, tuple[str, str]],
    points: list[tuple[int, float, float]],
) -> CarteEnd:
    par_service: dict[int, list[tuple[float, float]]] = {}
    for service_id, lon, lat in points:
        par_service.setdefault(service_id, []).append((lon, lat))
    services: list[ServiceCarteEnd] = []
    for item in sorted(items, key=lambda i: -i.end_mwh):
        coords = par_service.get(item.service_id)
        code, libelle = libelles.get(item.service_id, (str(item.service_id), str(item.service_id)))
        services.append(
            ServiceCarteEnd(
                service_id=item.service_id,
                code=code,
                libelle=libelle,
                end_mwh=item.end_mwh,
                part_pct=round(100 * item.end_mwh / total, 1) if total else 0.0,
                nombre_interruptions=item.nombre_interruptions,
                # médiane : robuste aux nœuds isolés loin du service
                longitude=statistics.median(c[0] for c in coords) if coords else None,
                latitude=statistics.median(c[1] for c in coords) if coords else None,
            )
        )
    pas = max(1, len(points) // _FOND_MAX)
    return CarteEnd(services=services, fond=[(lon, lat) for _, lon, lat in points[::pas]])
