"""Seeder réseau distribution — jeu minimal dev lié au seed géographique.

Prérequis : seed_geo exécuté avant (régions + services).

Usage :
    from app.models.seed.seed_reseau import seed_reseau
    await seed_reseau(db)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Region, Service
from app.models.reseau import Feeder, Poste, PosteSource, SousFeeder, Troncon

_POSTES_SOURCES: list[tuple[str, str, str, float]] = [
    # (code, libelle, region_code, puissance_mva)
    ("PS-DKR-01", "Poste Source Plateau", "REG-DKR", 60.0),
    ("PS-THS-01", "Poste Source Thiès", "REG-THS", 40.0),
]

_FEEDERS: list[tuple[str, str, str, str, float]] = [
    # (code, libelle, poste_source_code, service_code, tension_kv)
    ("FD-DKR-01", "Feeder Plateau Nord", "PS-DKR-01", "SVC-DKR-01", 30.0),
    ("FD-THS-01", "Feeder Thiès Centre", "PS-THS-01", "SVC-THS-01", 30.0),
]

_POSTES: list[tuple[str, str, str, str, float]] = [
    ("PT-DKR-01", "Poste BT Plateau", "FD-DKR-01", "SVC-DKR-01", 250.0),
]

_TRONCONS: list[tuple[str, str, str, float]] = [
    ("TR-DKR-01", "Tronçon Plateau A", "FD-DKR-01", 1.5),
]

_SOUS_FEEDERS: list[tuple[str, str, str]] = [
    ("SF-DKR-01", "Sous-feeder Plateau A1", "FD-DKR-01"),
]


async def _get_region_id(db: AsyncSession, code: str) -> int:
    result = await db.execute(select(Region.id).where(Region.code == code))
    region_id = result.scalar_one_or_none()
    if region_id is None:
        raise ValueError(f"Région '{code}' introuvable — exécuter seed_geo d'abord")
    return region_id


async def _get_service_id(db: AsyncSession, code: str) -> int:
    result = await db.execute(select(Service.id).where(Service.code == code))
    service_id = result.scalar_one_or_none()
    if service_id is None:
        raise ValueError(f"Service '{code}' introuvable — exécuter seed_geo d'abord")
    return service_id


async def _upsert_poste_source(
    db: AsyncSession,
    code: str,
    libelle: str,
    region_id: int,
    puissance_mva: float,
) -> PosteSource:
    result = await db.execute(select(PosteSource).where(PosteSource.code == code))
    ps = result.scalar_one_or_none()
    if ps is None:
        ps = PosteSource(
            code=code,
            libelle=libelle,
            region_id=region_id,
            puissance_mva=puissance_mva,
            is_active=True,
        )
        db.add(ps)
        await db.flush()
    return ps


async def _upsert_feeder(
    db: AsyncSession,
    code: str,
    libelle: str,
    poste_source_id: int,
    service_id: int,
    tension_kv: float,
) -> Feeder:
    result = await db.execute(select(Feeder).where(Feeder.code == code))
    feeder = result.scalar_one_or_none()
    if feeder is None:
        feeder = Feeder(
            code=code,
            libelle=libelle,
            poste_source_id=poste_source_id,
            service_id=service_id,
            tension_kv=tension_kv,
            is_active=True,
        )
        db.add(feeder)
        await db.flush()
    return feeder


async def _upsert_poste(
    db: AsyncSession,
    code: str,
    libelle: str,
    feeder_id: int,
    service_id: int,
    puissance_kva: float,
) -> Poste:
    result = await db.execute(select(Poste).where(Poste.code == code))
    poste = result.scalar_one_or_none()
    if poste is None:
        poste = Poste(
            code=code,
            libelle=libelle,
            feeder_id=feeder_id,
            service_id=service_id,
            puissance_kva=puissance_kva,
            is_active=True,
        )
        db.add(poste)
        await db.flush()
    return poste


async def _upsert_troncon(
    db: AsyncSession,
    code: str,
    libelle: str,
    feeder_id: int,
    longueur_km: float,
) -> Troncon:
    result = await db.execute(select(Troncon).where(Troncon.code == code))
    troncon = result.scalar_one_or_none()
    if troncon is None:
        troncon = Troncon(
            code=code,
            libelle=libelle,
            feeder_id=feeder_id,
            longueur_km=longueur_km,
            is_active=True,
        )
        db.add(troncon)
        await db.flush()
    return troncon


async def _upsert_sous_feeder(
    db: AsyncSession,
    code: str,
    libelle: str,
    feeder_id: int,
) -> SousFeeder:
    result = await db.execute(select(SousFeeder).where(SousFeeder.code == code))
    sf = result.scalar_one_or_none()
    if sf is None:
        sf = SousFeeder(code=code, libelle=libelle, feeder_id=feeder_id, is_active=True)
        db.add(sf)
        await db.flush()
    return sf


async def seed_reseau(db: AsyncSession) -> None:
    """Charge le réseau distribution minimal (2 postes sources, 2 feeders, …)."""
    ps_map: dict[str, PosteSource] = {}
    for code, libelle, region_code, puissance in _POSTES_SOURCES:
        region_id = await _get_region_id(db, region_code)
        ps_map[code] = await _upsert_poste_source(db, code, libelle, region_id, puissance)

    feeder_map: dict[str, Feeder] = {}
    for code, libelle, ps_code, svc_code, tension in _FEEDERS:
        service_id = await _get_service_id(db, svc_code)
        feeder_map[code] = await _upsert_feeder(
            db, code, libelle, ps_map[ps_code].id, service_id, tension
        )

    for code, libelle, fd_code, svc_code, puissance in _POSTES:
        service_id = await _get_service_id(db, svc_code)
        await _upsert_poste(
            db, code, libelle, feeder_map[fd_code].id, service_id, puissance
        )

    for code, libelle, fd_code, longueur in _TRONCONS:
        await _upsert_troncon(db, code, libelle, feeder_map[fd_code].id, longueur)

    for code, libelle, fd_code in _SOUS_FEEDERS:
        await _upsert_sous_feeder(db, code, libelle, feeder_map[fd_code].id)

    await db.flush()
