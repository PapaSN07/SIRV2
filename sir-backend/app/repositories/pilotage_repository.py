"""Requêtes du pilotage indicateurs : défauts aux 100 km, objectifs, carte, classements."""

import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Region, Service
from app.models.indicateurs import NombreClientMois, ObjectifIndicateur
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption, STATUTS_CLOTURES
from app.models.reseau import Feeder, Poste, Troncon
from app.models.sig import NoeudSig, TronconSig

_CLOSED = STATUTS_CLOTURES


@dataclass(frozen=True)
class ClientsDureeRow:
    clients: int
    client_heures: float
    nombre: int


@dataclass(frozen=True)
class PosteOuvertRow:
    poste_id: int
    code: str
    libelle: str
    interruption_id: int
    numero_interruption: int
    date_apparition: datetime
    feeder_libelle: str | None
    service_libelle: str | None
    sans_remise: bool


@dataclass(frozen=True)
class TopPosteRow:
    poste_id: int
    code: str
    libelle: str
    nombre: int
    clients: int
    end_mwh: float


@dataclass(frozen=True)
class ZoneRow:
    zone_id: int
    code: str
    libelle: str
    nombre: int
    end_mwh: float
    clients: int
    client_heures: float


@dataclass(frozen=True)
class MoisPointRow:
    annee: int
    mois: int
    nombre: int
    end_mwh: float


def _clients_par_interruption():
    """NombreClient (formule SENELEC) : Σ clients estimés des postes impactés, par interruption."""
    return (
        select(
            PosteInterruption.interruption_id.label("interruption_id"),
            func.sum(
                func.coalesce(
                    PosteInterruption.nombre_clients_estime,
                    PosteInterruption.nombre_clients_touches,
                    0,
                )
            ).label("clients"),
        )
        .group_by(PosteInterruption.interruption_id)
        .subquery()
    )


def _distribution_saifi_saidi():
    """Interruptions comptées dans SAIFI/SAIDI : clôturées (durée connue), sans exclusion."""
    return (
        Interruption.type_direction == "distribution",
        Interruption.statut.in_(_CLOSED),
        Interruption.date_remise.isnot(None),
    )


def _closed_distribution():
    return (
        Interruption.type_direction == "distribution",
        Interruption.statut.in_(_CLOSED),
        Interruption.is_force_majeure == False,  # noqa: E712
        Interruption.date_remise.isnot(None),
    )


async def longueur_reseau_km(db: AsyncSession, service_ids: list[int]) -> float:
    """Longueur MT du périmètre : tronçons SIG, sinon tronçons du référentiel."""
    if not service_ids:
        return 0.0
    metres = await db.scalar(
        select(func.coalesce(func.sum(TronconSig.longueur_m), 0))
        .join(Feeder, Feeder.id == TronconSig.feeder_id)
        .where(Feeder.service_id.in_(service_ids))
    )
    if metres and float(metres) > 0:
        return float(metres) / 1000.0
    km = await db.scalar(
        select(func.coalesce(func.sum(Troncon.longueur_km), 0))
        .join(Feeder, Feeder.id == Troncon.feeder_id)
        .where(Feeder.service_id.in_(service_ids))
    )
    return float(km or 0)


async def compter_defauts(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
) -> int:
    """Interruptions distribution hors force majeure, datées par l'apparition."""
    if not service_ids:
        return 0
    total = await db.scalar(
        select(func.count(Interruption.id)).where(
            Interruption.service_id.in_(service_ids),
            Interruption.type_direction == "distribution",
            Interruption.is_force_majeure == False,  # noqa: E712
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
    )
    return int(total or 0)


async def sommer_end_mwh(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
) -> float:
    if not service_ids:
        return 0.0
    total = await db.scalar(
        select(func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0))
        .select_from(Interruption)
        .join(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.service_id.in_(service_ids),
            *_closed_distribution(),
            Interruption.date_remise >= debut,
            Interruption.date_remise < fin,
        )
    )
    return float(total or 0)


async def sommer_clients(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
) -> ClientsDureeRow:
    """NombreClient et Σ(NombreClient × dureeHeure), datés par l'apparition (formule SENELEC)."""
    if not service_ids:
        return ClientsDureeRow(0, 0.0, 0)
    clients = _clients_par_interruption()
    nb = func.coalesce(clients.c.clients, 0)
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(nb), 0).label("clients"),
                func.coalesce(
                    func.sum(nb * func.coalesce(Interruption.duree_minutes, 0) / 60.0), 0
                ).label("client_heures"),
                func.count(Interruption.id).label("nombre"),
            )
            .select_from(Interruption)
            .outerjoin(clients, clients.c.interruption_id == Interruption.id)
            .where(
                Interruption.service_id.in_(service_ids),
                *_distribution_saifi_saidi(),
                Interruption.date_apparition >= debut,
                Interruption.date_apparition < fin,
            )
        )
    ).one()
    return ClientsDureeRow(
        clients=int(row.clients or 0),
        client_heures=float(row.client_heures or 0),
        nombre=int(row.nombre or 0),
    )


async def mois_derniere_apparition(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
) -> tuple[int, int] | None:
    """(année, mois) de MAX(DateApparition) sur la période — mois du dénominateur SENELEC."""
    if not service_ids:
        return None
    derniere = await db.scalar(
        select(func.max(Interruption.date_apparition)).where(
            Interruption.service_id.in_(service_ids),
            *_distribution_saifi_saidi(),
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
    )
    return (derniere.year, derniere.month) if derniere else None


async def clients_reference_exacte(
    db: AsyncSession,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> int:
    """Σ NombreClientMois du mois demandé, sans repli (comme la mesure Power BI SENELEC)."""
    if not service_ids:
        return 0
    total = await db.scalar(
        select(func.coalesce(func.sum(NombreClientMois.nombre_clients), 0)).where(
            NombreClientMois.service_id.in_(service_ids),
            NombreClientMois.annee == annee,
            NombreClientMois.mois == mois,
        )
    )
    return int(total or 0)


async def clients_reference(
    db: AsyncSession,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> int:
    """Dénominateur SAIFI/SAIDI : clients du mois, sinon le dernier mois connu de l'année."""
    if not service_ids:
        return 0
    exact = await db.scalar(
        select(func.coalesce(func.sum(NombreClientMois.nombre_clients), 0)).where(
            NombreClientMois.service_id.in_(service_ids),
            NombreClientMois.annee == annee,
            NombreClientMois.mois == mois,
        )
    )
    if exact and int(exact) > 0:
        return int(exact)
    latest_month = await db.scalar(
        select(func.max(NombreClientMois.mois)).where(
            NombreClientMois.service_id.in_(service_ids),
            NombreClientMois.annee == annee,
            NombreClientMois.mois <= mois,
        )
    )
    if latest_month is None:
        return 0
    fallback = await db.scalar(
        select(func.coalesce(func.sum(NombreClientMois.nombre_clients), 0)).where(
            NombreClientMois.service_id.in_(service_ids),
            NombreClientMois.annee == annee,
            NombreClientMois.mois == int(latest_month),
        )
    )
    return int(fallback or 0)


async def list_objectifs(
    db: AsyncSession,
    annee: int,
    region_id: int | None,
) -> list[ObjectifIndicateur]:
    stmt = select(ObjectifIndicateur).where(ObjectifIndicateur.annee == annee)
    if region_id is None:
        stmt = stmt.where(ObjectifIndicateur.region_id.is_(None))
    else:
        stmt = stmt.where(ObjectifIndicateur.region_id == region_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def upsert_objectif(
    db: AsyncSession,
    *,
    annee: int,
    code: str,
    valeur_annuelle: float,
    region_id: int | None,
) -> None:
    stmt = select(ObjectifIndicateur).where(
        ObjectifIndicateur.annee == annee,
        ObjectifIndicateur.code == code,
    )
    if region_id is None:
        stmt = stmt.where(ObjectifIndicateur.region_id.is_(None))
    else:
        stmt = stmt.where(ObjectifIndicateur.region_id == region_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        db.add(
            ObjectifIndicateur(
                annee=annee,
                code=code,
                valeur_annuelle=valeur_annuelle,
                region_id=region_id,
                updated_at=datetime.utcnow(),
            )
        )
        return
    row.valeur_annuelle = valeur_annuelle
    row.updated_at = datetime.utcnow()


async def region_id_du_service(db: AsyncSession, service_id: int) -> int | None:
    return await db.scalar(select(Service.region_id).where(Service.id == service_id))


async def list_postes_impactes(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    limit: int = 400,
) -> list[PosteOuvertRow]:
    """Postes touchés sur la période. Un poste n'apparaît qu'une fois, via sa dernière interruption."""
    if not service_ids:
        return []
    result = await db.execute(
        select(
            Poste.id,
            Poste.code,
            Poste.libelle,
            Interruption.id.label("interruption_id"),
            Interruption.numero_interruption,
            Interruption.date_apparition,
            Interruption.date_remise,
            Feeder.libelle.label("feeder_libelle"),
            Service.libelle.label("service_libelle"),
        )
        .join(PosteInterruption, PosteInterruption.poste_id == Poste.id)
        .join(Interruption, Interruption.id == PosteInterruption.interruption_id)
        .outerjoin(Feeder, Feeder.id == Interruption.feeder_id)
        .outerjoin(Service, Service.id == Interruption.service_id)
        .where(
            Interruption.service_id.in_(service_ids),
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .order_by(Interruption.date_apparition.desc())
        .limit(limit * 4)
    )
    vus: set[int] = set()
    lignes: list[PosteOuvertRow] = []
    for row in result.all():
        if row.id in vus:
            continue
        vus.add(row.id)
        lignes.append(
            PosteOuvertRow(
                poste_id=row.id,
                code=row.code,
                libelle=row.libelle,
                interruption_id=row.interruption_id,
                numero_interruption=row.numero_interruption,
                date_apparition=row.date_apparition,
                feeder_libelle=row.feeder_libelle,
                service_libelle=row.service_libelle,
                sans_remise=row.date_remise is None,
            )
        )
        if len(lignes) >= limit:
            break
    return lignes


async def coords_par_nom(
    db: AsyncSession,
    noms: list[str],
) -> dict[str, tuple[float, float]]:
    """Coordonnées SIG indexées par nom, si elles tombent dans l'emprise du Sénégal."""
    cleaned = [nom for nom in noms if nom]
    if not cleaned:
        return {}
    result = await db.execute(
        select(NoeudSig.nom, NoeudSig.station, NoeudSig.coord_x, NoeudSig.coord_y).where(
            NoeudSig.coord_x.isnot(None),
            NoeudSig.coord_y.isnot(None),
            or_(NoeudSig.nom.in_(cleaned), NoeudSig.station.in_(cleaned)),
        )
    )
    found: dict[str, tuple[float, float]] = {}
    for row in result.all():
        longitude, latitude = _lon_lat(row.coord_x, row.coord_y)
        if longitude is None or latitude is None:
            continue
        for key in (row.nom, row.station):
            if key:
                found.setdefault(key.casefold(), (longitude, latitude))
    return found


def _lon_lat(x: float | None, y: float | None) -> tuple[float | None, float | None]:
    """Longitude, latitude. Les nœuds SIG SENELEC sont en UTM 28N, parfois déjà en degrés."""
    if x is None or y is None:
        return None, None
    for longitude, latitude in ((float(x), float(y)), (float(y), float(x))):
        if -20.0 <= longitude <= -10.0 and 12.0 <= latitude <= 17.0:
            return longitude, latitude
    for easting, northing in ((float(x), float(y)), (float(y), float(x))):
        converted = _utm28n_vers_wgs84(easting, northing)
        if converted is not None:
            return converted
    return None, None


def _utm28n_vers_wgs84(easting: float, northing: float) -> tuple[float, float] | None:
    if not (100_000.0 <= easting <= 900_000.0 and 1_200_000.0 <= northing <= 2_000_000.0):
        return None
    a = 6_378_137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = easting - 500_000.0
    meridional = northing / k0
    mu = meridional / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1 * e1 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    if cos_phi == 0:
        return None
    tan_phi = math.tan(phi)
    n = a / math.sqrt(1 - e2 * sin_phi * sin_phi)
    t = tan_phi * tan_phi
    c = ep2 * cos_phi * cos_phi
    radius = a * (1 - e2) / (1 - e2 * sin_phi * sin_phi) ** 1.5
    d = x / (n * k0)
    latitude = math.degrees(
        phi
        - (n * tan_phi / radius)
        * (
            d * d / 2
            - (5 + 3 * t + 10 * c - 4 * c * c - 9 * ep2) * d**4 / 24
            + (61 + 90 * t + 298 * c + 45 * t * t - 252 * ep2 - 3 * c * c) * d**6 / 720
        )
    )
    longitude = math.degrees(
        math.radians(-15.0)
        + (
            d
            - (1 + 2 * t + c) * d**3 / 6
            + (5 - 2 * c + 28 * t - 3 * c * c + 8 * ep2 + 24 * t * t) * d**5 / 120
        )
        / cos_phi
    )
    if -20.0 <= longitude <= -10.0 and 12.0 <= latitude <= 17.0:
        return longitude, latitude
    return None


async def top_postes(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    limit: int,
) -> list[TopPosteRow]:
    if not service_ids:
        return []
    result = await db.execute(
        select(
            Poste.id,
            Poste.code,
            Poste.libelle,
            func.count(func.distinct(Interruption.id)).label("nombre"),
            func.coalesce(func.sum(PosteInterruption.nombre_clients_touches), 0).label("clients"),
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
        )
        .join(PosteInterruption, PosteInterruption.poste_id == Poste.id)
        .join(Interruption, Interruption.id == PosteInterruption.interruption_id)
        .outerjoin(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.service_id.in_(service_ids),
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .group_by(Poste.id, Poste.code, Poste.libelle)
        .order_by(func.count(func.distinct(Interruption.id)).desc())
        .limit(limit)
    )
    return [
        TopPosteRow(
            poste_id=row.id,
            code=row.code,
            libelle=row.libelle,
            nombre=int(row.nombre or 0),
            clients=int(row.clients or 0),
            end_mwh=float(row.end_mwh or 0),
        )
        for row in result.all()
    ]


async def zones_perturbees(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    *,
    par_region: bool,
    limit: int = 8,
) -> list[ZoneRow]:
    if not service_ids:
        return []
    zone_id = Region.id if par_region else Service.id
    zone_code = Region.code if par_region else Service.code
    zone_libelle = Region.libelle if par_region else Service.libelle
    clients = _clients_par_interruption()
    stmt = (
        select(
            zone_id,
            zone_code,
            zone_libelle,
            func.count(Interruption.id).label("nombre"),
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
            func.coalesce(func.sum(func.coalesce(clients.c.clients, 0)), 0).label("clients"),
            func.coalesce(
                func.sum(
                    func.coalesce(clients.c.clients, 0)
                    * func.coalesce(Interruption.duree_minutes, 0)
                    / 60.0
                ),
                0,
            ).label("client_heures"),
        )
        .join(Service, Service.id == Interruption.service_id)
        .outerjoin(clients, clients.c.interruption_id == Interruption.id)
        .outerjoin(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.service_id.in_(service_ids),
            *_closed_distribution(),
            Interruption.date_remise >= debut,
            Interruption.date_remise < fin,
        )
    )
    if par_region:
        stmt = stmt.join(Region, Region.id == Service.region_id)
    stmt = (
        stmt.group_by(zone_id, zone_code, zone_libelle)
        .order_by(func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        ZoneRow(
            zone_id=row[0],
            code=row[1],
            libelle=row[2],
            nombre=int(row.nombre or 0),
            end_mwh=float(row.end_mwh or 0),
            clients=int(row.clients or 0),
            client_heures=float(row.client_heures or 0),
        )
        for row in result.all()
    ]


async def clients_par_zone(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    *,
    par_region: bool,
) -> dict[int, tuple[int, float]]:
    """Par zone : (NombreClient, Σ NombreClient × dureeHeure), règles de la formule SENELEC."""
    if not service_ids:
        return {}
    zone_id = Service.region_id if par_region else Service.id
    clients = _clients_par_interruption()
    nb = func.coalesce(clients.c.clients, 0)
    result = await db.execute(
        select(
            zone_id,
            func.coalesce(func.sum(nb), 0).label("clients"),
            func.coalesce(func.sum(nb * func.coalesce(Interruption.duree_minutes, 0) / 60.0), 0).label(
                "client_heures"
            ),
        )
        .select_from(Interruption)
        .join(Service, Service.id == Interruption.service_id)
        .outerjoin(clients, clients.c.interruption_id == Interruption.id)
        .where(
            Interruption.service_id.in_(service_ids),
            *_distribution_saifi_saidi(),
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
            zone_id.isnot(None),
        )
        .group_by(zone_id)
    )
    return {int(r[0]): (int(r.clients or 0), float(r.client_heures or 0)) for r in result.all()}


async def clients_reference_par_zone(
    db: AsyncSession,
    service_ids: list[int],
    annee: int,
    mois: int,
    *,
    par_region: bool,
) -> dict[int, int]:
    if not service_ids:
        return {}
    zone_id = Service.region_id if par_region else Service.id
    result = await db.execute(
        select(
            zone_id,
            func.coalesce(func.sum(NombreClientMois.nombre_clients), 0).label("clients"),
        )
        .join(Service, Service.id == NombreClientMois.service_id)
        .where(
            NombreClientMois.service_id.in_(service_ids),
            NombreClientMois.annee == annee,
            NombreClientMois.mois == mois,
            zone_id.isnot(None),
        )
        .group_by(zone_id)
    )
    return {int(row[0]): int(row.clients or 0) for row in result.all()}


async def serie_mensuelle(
    db: AsyncSession,
    *,
    cible: str,
    cible_id: int,
    debut: datetime,
    fin: datetime,
) -> list[MoisPointRow]:
    annee = func.extract("year", Interruption.date_apparition)
    mois = func.extract("month", Interruption.date_apparition)
    stmt = (
        select(
            annee.label("annee"),
            mois.label("mois"),
            func.count(func.distinct(Interruption.id)).label("nombre"),
            func.coalesce(func.sum(InterruptionDistribution.end_mwh), 0).label("end_mwh"),
        )
        .outerjoin(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
    )
    if cible == "feeder":
        stmt = stmt.where(Interruption.feeder_id == cible_id)
    else:
        stmt = stmt.join(
            PosteInterruption,
            PosteInterruption.interruption_id == Interruption.id,
        ).where(PosteInterruption.poste_id == cible_id)
    stmt = stmt.group_by(annee, mois).order_by(annee, mois)
    result = await db.execute(stmt)
    return [
        MoisPointRow(
            annee=int(row.annee),
            mois=int(row.mois),
            nombre=int(row.nombre or 0),
            end_mwh=float(row.end_mwh or 0),
        )
        for row in result.all()
    ]


async def libelle_cible(db: AsyncSession, cible: str, cible_id: int) -> tuple[str, str, int | None] | None:
    if cible == "feeder":
        row = (
            await db.execute(
                select(Feeder.code, Feeder.libelle, Feeder.service_id).where(Feeder.id == cible_id)
            )
        ).one_or_none()
    else:
        row = (
            await db.execute(
                select(Poste.code, Poste.libelle, Poste.service_id).where(Poste.id == cible_id)
            )
        ).one_or_none()
    if row is None:
        return None
    return row[0], row[1], row[2]
