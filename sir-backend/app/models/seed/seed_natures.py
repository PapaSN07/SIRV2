"""Seeder référentiel natures — codes FIS (tableau de bord).

Prérequis : aucun (idempotent).

Usage :
    from app.models.seed.seed_natures import seed_natures
    await seed_natures(db)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referentiel import Nature

# Ordre canonique FIS — voir docs/indicateurs_sirv2.md §4
_FIS_NATURES: list[tuple[str, str]] = [
    ("PERMANENT", "Défaut permanent"),
    ("SEMI_PERM", "Défaut semi-permanent"),
    ("FUGITIF", "Défaut fugitif"),
    ("DELESTAGE", "Délestage incident HTA"),
    ("COUPURE", "Coupure travaux"),
]


async def seed_natures(db: AsyncSession) -> None:
    """Charge les natures FIS dans le référentiel (upsert par code)."""
    for code, libelle in _FIS_NATURES:
        result = await db.execute(select(Nature).where(Nature.code == code))
        row = result.scalar_one_or_none()
        if row is None:
            db.add(Nature(code=code, libelle=libelle, is_active=True))
        else:
            row.libelle = libelle
            row.is_active = True
    await db.flush()
