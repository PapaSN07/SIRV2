"""Repository — correspondances FIS administrées.

Les cibles (nature, cause, siège, signalisation) sont chargées par jointure avec la
correspondance (`lazy="joined"`) : aucun chargement paresseux en async.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correspondance_fis import CorrespondanceFis
from app.models.referentiel import Cause, Nature, Siege, Signalisation

_MODELES_CIBLES: dict[str, type[Nature] | type[Cause] | type[Siege] | type[Signalisation]] = {
    "nature": Nature,
    "cause": Cause,
    "siege": Siege,
    "signalisation": Signalisation,
}

COLONNES_CIBLES: dict[str, str] = {
    "nature": "nature_id",
    "cause": "cause_id",
    "siege": "siege_id",
    "signalisation": "signalisation_id",
}


async def dictionnaire(db: AsyncSession) -> dict[tuple[str, str], CorrespondanceFis]:
    """Toutes les correspondances, par (catégorie, libellé FIS normalisé) — lu par l'import FIS."""
    requete = select(CorrespondanceFis).order_by(CorrespondanceFis.id)
    lignes = list(await db.scalars(requete))
    return {(ligne.categorie, ligne.libelle_fis): ligne for ligne in lignes}


async def lister(db: AsyncSession, categorie: str | None = None) -> list[CorrespondanceFis]:
    requete = select(CorrespondanceFis)
    if categorie is not None:
        requete = requete.where(CorrespondanceFis.categorie == categorie)
    requete = requete.order_by(CorrespondanceFis.categorie, CorrespondanceFis.libelle_fis, CorrespondanceFis.id)
    return list(await db.scalars(requete))


async def get_by_id(db: AsyncSession, correspondance_id: int) -> CorrespondanceFis | None:
    return await db.scalar(select(CorrespondanceFis).where(CorrespondanceFis.id == correspondance_id))


async def existe(db: AsyncSession, categorie: str, libelle_fis: str) -> bool:
    identifiant = await db.scalar(
        select(CorrespondanceFis.id)
        .where(CorrespondanceFis.categorie == categorie, CorrespondanceFis.libelle_fis == libelle_fis)
        .limit(1)
    )
    return identifiant is not None


async def get_cible(
    db: AsyncSession, categorie: str, referentiel_id: int
) -> Nature | Cause | Siege | Signalisation | None:
    """Entrée du Référentiel visée (active ou non : le service contrôle)."""
    modele = _MODELES_CIBLES[categorie]
    return await db.scalar(select(modele).where(modele.id == referentiel_id))


async def creer(
    db: AsyncSession,
    *,
    categorie: str,
    libelle_fis: str,
    referentiel_id: int,
    is_force_majeure: bool | None,
    created_by_id: int,
) -> CorrespondanceFis:
    ligne = CorrespondanceFis(
        categorie=categorie,
        libelle_fis=libelle_fis,
        is_force_majeure=is_force_majeure,
        created_by_id=created_by_id,
    )
    setattr(ligne, COLONNES_CIBLES[categorie], referentiel_id)
    db.add(ligne)
    await db.flush()
    await db.refresh(ligne, ["created_at"])
    return ligne


async def supprimer(db: AsyncSession, ligne: CorrespondanceFis) -> None:
    await db.delete(ligne)
    await db.flush()
