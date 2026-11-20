"""Accès aux schémas unifilaires (schéma, postes, tuiles)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only

from app.models.reseau import Poste
from app.models.schema_unifilaire import SchemaUnifilaire, SchemaUnifilairePoste, SchemaUnifilaireTuile

_COLONNES_SCHEMA = (
    SchemaUnifilaire.id,
    SchemaUnifilaire.nom,
    SchemaUnifilaire.fichier,
    SchemaUnifilaire.region_id,
    SchemaUnifilaire.largeur,
    SchemaUnifilaire.hauteur,
    SchemaUnifilaire.zoom_max,
    SchemaUnifilaire.nb_postes,
    SchemaUnifilaire.is_active,
    SchemaUnifilaire.importe_le,
)


async def lister(db: AsyncSession) -> list[SchemaUnifilaire]:
    """Schémas actifs, sans le graphe (lourd)."""
    result = await db.execute(
        select(SchemaUnifilaire)
        .options(load_only(*_COLONNES_SCHEMA), joinedload(SchemaUnifilaire.region))
        .where(SchemaUnifilaire.is_active == True)  # noqa: E712
        .order_by(SchemaUnifilaire.nom)
    )
    return list(result.unique().scalars().all())


async def obtenir(db: AsyncSession, schema_id: int) -> SchemaUnifilaire | None:
    result = await db.execute(
        select(SchemaUnifilaire)
        .options(load_only(*_COLONNES_SCHEMA), joinedload(SchemaUnifilaire.region))
        .where(SchemaUnifilaire.id == schema_id)
    )
    return result.unique().scalar_one_or_none()


async def graphe(db: AsyncSession, schema_id: int) -> bytes | None:
    return await db.scalar(select(SchemaUnifilaire.graphe).where(SchemaUnifilaire.id == schema_id))


async def postes(db: AsyncSession, schema_id: int) -> list[SchemaUnifilairePoste]:
    result = await db.execute(
        select(SchemaUnifilairePoste)
        .options(joinedload(SchemaUnifilairePoste.poste).load_only(Poste.id, Poste.code, Poste.libelle))
        .where(SchemaUnifilairePoste.schema_id == schema_id)
        .order_by(SchemaUnifilairePoste.rang)
    )
    return list(result.unique().scalars().all())


async def poste(db: AsyncSession, schema_id: int, poste_schema_id: int) -> SchemaUnifilairePoste | None:
    return await db.scalar(
        select(SchemaUnifilairePoste).where(
            SchemaUnifilairePoste.schema_id == schema_id, SchemaUnifilairePoste.id == poste_schema_id
        )
    )


async def tuile(db: AsyncSession, schema_id: int, z: int, x: int, y: int) -> bytes | None:
    return await db.scalar(
        select(SchemaUnifilaireTuile.contenu).where(
            SchemaUnifilaireTuile.schema_id == schema_id,
            SchemaUnifilaireTuile.z == z,
            SchemaUnifilaireTuile.x == x,
            SchemaUnifilaireTuile.y == y,
        )
    )


async def associer(
    db: AsyncSession, poste_schema_id: int, poste_id: int | None, rapprochement: str | None
) -> None:
    await db.execute(
        update(SchemaUnifilairePoste)
        .where(SchemaUnifilairePoste.id == poste_schema_id)
        .values(poste_id=poste_id, rapprochement=rapprochement)
    )
