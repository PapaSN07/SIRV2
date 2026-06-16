"""Service — collecte données rapport annuel (Sprint 6.4)."""

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import rapport_transport_repository as transport_repo
from app.schemas.indicateurs import HistoriqueResponse
from app.services import indicateurs_service

_ANNUEL_DIRECTIONS = frozenset({"distribution", "transport", "consolide"})
_DEFAULT_TOP_LIMIT = 10
_MAX_TOP_LIMIT = 50

# TODO(CRSE): objectifs annuels à valider avec l'équipe SAQS.
_OBJECTIFS_CRSE_PLACEHOLDER = "Objectifs CRSE non configurés — validation SAQS requise."


@dataclass(frozen=True)
class AnnuelMonthlyPoint:
    mois: int
    end_mwh: float
    saifi: float | None = None
    saidi: float | None = None


@dataclass(frozen=True)
class AnnuelFeederRank:
    feeder_id: int
    code: str
    libelle: str
    end_mwh: float
    nombre_interruptions: int


@dataclass(frozen=True)
class AnnuelEquipementRank:
    equipement_id: int
    code: str
    libelle: str
    end_mwh: float
    nombre_interruptions: int


@dataclass(frozen=True)
class AnnuelReportData:
    annee: int
    direction: str
    region_id: int | None
    top_limit: int
    serie_civile: list[AnnuelMonthlyPoint]
    transport_serie: list[AnnuelMonthlyPoint] | None
    historique_end: HistoriqueResponse | None
    historique_saifi: HistoriqueResponse | None
    historique_saidi: HistoriqueResponse | None
    top_feeders: list[AnnuelFeederRank]
    top_equipements: list[AnnuelEquipementRank]
    total_end_annee: float
    objectifs_note: str


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_TOP_LIMIT))


async def _distribution_serie_civile(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    region_id: int | None,
) -> list[AnnuelMonthlyPoint]:
    points: list[AnnuelMonthlyPoint] = []
    for mois in range(1, 13):
        end = await indicateurs_service.get_end(
            db, redis, user, annee=annee, mois=mois, region_id=region_id
        )
        saifi = await indicateurs_service.get_saifi(
            db, redis, user, annee=annee, mois=mois, region_id=region_id
        )
        saidi = await indicateurs_service.get_saidi(
            db, redis, user, annee=annee, mois=mois, region_id=region_id
        )
        points.append(
            AnnuelMonthlyPoint(
                mois=mois,
                end_mwh=end.aggregate.end_mwh,
                saifi=saifi.aggregate.saifi,
                saidi=saidi.aggregate.saidi,
            )
        )
    return points


async def _transport_serie_civile(
    db: AsyncSession,
    *,
    annee: int,
) -> list[AnnuelMonthlyPoint]:
    points: list[AnnuelMonthlyPoint] = []
    for mois in range(1, 13):
        end_mwh = await transport_repo.aggregate_end_for_month(db, annee=annee, mois=mois)
        points.append(AnnuelMonthlyPoint(mois=mois, end_mwh=end_mwh))
    return points


async def _aggregate_top_feeders_year(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    region_id: int | None,
    limit: int,
) -> list[AnnuelFeederRank]:
    merged: dict[int, AnnuelFeederRank] = {}
    for mois in range(1, 13):
        response = await indicateurs_service.get_top_feeders(
            db,
            redis,
            user,
            annee=annee,
            mois=mois,
            region_id=region_id,
            limit=_MAX_TOP_LIMIT,
        )
        for item in response.items:
            existing = merged.get(item.feeder_id)
            if existing is None:
                merged[item.feeder_id] = AnnuelFeederRank(
                    feeder_id=item.feeder_id,
                    code=item.code,
                    libelle=item.libelle,
                    end_mwh=item.end_mwh,
                    nombre_interruptions=item.nombre_interruptions,
                )
            else:
                merged[item.feeder_id] = AnnuelFeederRank(
                    feeder_id=existing.feeder_id,
                    code=existing.code,
                    libelle=existing.libelle,
                    end_mwh=existing.end_mwh + item.end_mwh,
                    nombre_interruptions=existing.nombre_interruptions + item.nombre_interruptions,
                )
    ranked = sorted(merged.values(), key=lambda row: row.end_mwh, reverse=True)
    return ranked[:limit]


async def _aggregate_top_equipements_year(
    db: AsyncSession,
    *,
    annee: int,
    limit: int,
) -> list[AnnuelEquipementRank]:
    merged: dict[int, AnnuelEquipementRank] = {}
    for mois in range(1, 13):
        rows = await transport_repo.aggregate_equipements_for_month(
            db, annee=annee, mois=mois, limit=_MAX_TOP_LIMIT
        )
        for row in rows:
            existing = merged.get(row.equipement_id)
            if existing is None:
                merged[row.equipement_id] = AnnuelEquipementRank(
                    equipement_id=row.equipement_id,
                    code=row.code,
                    libelle=row.libelle,
                    end_mwh=row.end_mwh,
                    nombre_interruptions=row.nombre_interruptions,
                )
            else:
                merged[row.equipement_id] = AnnuelEquipementRank(
                    equipement_id=existing.equipement_id,
                    code=existing.code,
                    libelle=existing.libelle,
                    end_mwh=existing.end_mwh + row.end_mwh,
                    nombre_interruptions=existing.nombre_interruptions + row.nombre_interruptions,
                )
    ranked = sorted(merged.values(), key=lambda row: row.end_mwh, reverse=True)
    return ranked[:limit]


async def collect_annuel_data(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    direction: str,
    region_id: int | None,
    top_limit: int = _DEFAULT_TOP_LIMIT,
) -> AnnuelReportData:
    if direction not in _ANNUEL_DIRECTIONS:
        raise ValueError(f"direction invalide: {direction}")

    clamped_limit = _clamp_limit(top_limit)
    include_distribution = direction in {"distribution", "consolide"}
    include_transport = direction in {"transport", "consolide"}

    serie_civile: list[AnnuelMonthlyPoint] = []
    transport_serie: list[AnnuelMonthlyPoint] | None = None
    historique_end: HistoriqueResponse | None = None
    historique_saifi: HistoriqueResponse | None = None
    historique_saidi: HistoriqueResponse | None = None
    top_feeders: list[AnnuelFeederRank] = []
    top_equipements: list[AnnuelEquipementRank] = []

    if include_distribution:
        serie_civile = await _distribution_serie_civile(
            db, redis, user, annee=annee, region_id=region_id
        )
        historique_end = await indicateurs_service.get_historique(
            db, redis, user, indicateur_type="end", annees=1, region_id=region_id
        )
        historique_saifi = await indicateurs_service.get_historique(
            db, redis, user, indicateur_type="saifi", annees=1, region_id=region_id
        )
        historique_saidi = await indicateurs_service.get_historique(
            db, redis, user, indicateur_type="saidi", annees=1, region_id=region_id
        )
        top_feeders = await _aggregate_top_feeders_year(
            db,
            redis,
            user,
            annee=annee,
            region_id=region_id,
            limit=clamped_limit,
        )

    if include_transport:
        transport_serie = await _transport_serie_civile(db, annee=annee)
        top_equipements = await _aggregate_top_equipements_year(
            db, annee=annee, limit=clamped_limit
        )
        if direction == "transport":
            serie_civile = transport_serie
            transport_serie = None

    total_end = sum(point.end_mwh for point in serie_civile)
    if transport_serie is not None:
        total_end += sum(point.end_mwh for point in transport_serie)

    return AnnuelReportData(
        annee=annee,
        direction=direction,
        region_id=region_id,
        top_limit=clamped_limit,
        serie_civile=serie_civile,
        transport_serie=transport_serie,
        historique_end=historique_end,
        historique_saifi=historique_saifi,
        historique_saidi=historique_saidi,
        top_feeders=top_feeders,
        top_equipements=top_equipements,
        total_end_annee=total_end,
        objectifs_note=_OBJECTIFS_CRSE_PLACEHOLDER,
    )
