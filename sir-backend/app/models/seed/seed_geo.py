"""Seeder géographique — jeu minimal dev pour la hiérarchie SENELEC.

Idempotent : upsert par code unique sur chaque niveau.

Usage :
    from app.models.seed.seed_geo import seed_geo
    await seed_geo(db)

CLI :
    python -m scripts.run_seed_geo
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Agence, Delegation, Region, Service

# (code, libelle)
_REGIONS: list[tuple[str, str]] = [
    ("REG-DKR", "Dakar"),
    ("REG-THS", "Thiès"),
]

# region_code → [(delegation_code, libelle), ...]
_DELEGATIONS: dict[str, list[tuple[str, str]]] = {
    "REG-DKR": [
        ("DEL-DKR-01", "Délégation Dakar Centre"),
    ],
    "REG-THS": [
        ("DEL-THS-01", "Délégation Thiès"),
    ],
}

# delegation_code → [(agence_code, libelle), ...]
_AGENCES: dict[str, list[tuple[str, str]]] = {
    "DEL-DKR-01": [
        ("AGC-DKR-01", "Agence Dakar Plateau"),
    ],
    "DEL-THS-01": [
        ("AGC-THS-01", "Agence Thiès Ville"),
    ],
}

# agence_code → [(service_code, libelle), ...]
_SERVICES: dict[str, list[tuple[str, str]]] = {
    "AGC-DKR-01": [
        ("SVC-DKR-01", "Service Distribution Plateau"),
    ],
    "AGC-THS-01": [
        ("SVC-THS-01", "Service Distribution Thiès"),
    ],
}


async def _upsert_region(db: AsyncSession, code: str, libelle: str) -> Region:
    result = await db.execute(select(Region).where(Region.code == code))
    region = result.scalar_one_or_none()
    if region is None:
        region = Region(code=code, libelle=libelle, is_active=True)
        db.add(region)
        await db.flush()
    return region


async def _upsert_delegation(
    db: AsyncSession,
    region_id: int,
    code: str,
    libelle: str,
) -> Delegation:
    result = await db.execute(select(Delegation).where(Delegation.code == code))
    delegation = result.scalar_one_or_none()
    if delegation is None:
        delegation = Delegation(
            region_id=region_id,
            code=code,
            libelle=libelle,
            is_active=True,
        )
        db.add(delegation)
        await db.flush()
    return delegation


async def _upsert_agence(
    db: AsyncSession,
    delegation_id: int,
    code: str,
    libelle: str,
) -> Agence:
    result = await db.execute(select(Agence).where(Agence.code == code))
    agence = result.scalar_one_or_none()
    if agence is None:
        agence = Agence(
            delegation_id=delegation_id,
            code=code,
            libelle=libelle,
            is_active=True,
        )
        db.add(agence)
        await db.flush()
    return agence


async def _upsert_service(
    db: AsyncSession,
    agence_id: int,
    region_id: int,
    code: str,
    libelle: str,
) -> Service:
    result = await db.execute(select(Service).where(Service.code == code))
    service = result.scalar_one_or_none()
    if service is None:
        service = Service(
            agence_id=agence_id,
            region_id=region_id,
            code=code,
            libelle=libelle,
            is_active=True,
        )
        db.add(service)
        await db.flush()
    elif service.region_id != region_id:
        service.region_id = region_id
        await db.flush()
    return service


async def seed_geo(db: AsyncSession) -> None:
    """Charge la hiérarchie géographique minimale (2 régions, chaîne complète)."""
    region_map: dict[str, Region] = {}
    for code, libelle in _REGIONS:
        region_map[code] = await _upsert_region(db, code, libelle)

    delegation_map: dict[str, Delegation] = {}
    for region_code, delegations in _DELEGATIONS.items():
        region = region_map[region_code]
        for del_code, del_libelle in delegations:
            delegation_map[del_code] = await _upsert_delegation(
                db, region.id, del_code, del_libelle
            )

    agence_map: dict[str, Agence] = {}
    for delegation_code, agences in _AGENCES.items():
        delegation = delegation_map[delegation_code]
        for agc_code, agc_libelle in agences:
            agence_map[agc_code] = await _upsert_agence(
                db, delegation.id, agc_code, agc_libelle
            )

    for agence_code, services in _SERVICES.items():
        agence = agence_map[agence_code]
        delegation_code = next(
            dcode for dcode, agences in _AGENCES.items() if any(a[0] == agence_code for a in agences)
        )
        region_id = delegation_map[delegation_code].region_id
        for svc_code, svc_libelle in services:
            await _upsert_service(db, agence.id, region_id, svc_code, svc_libelle)

    await db.flush()
