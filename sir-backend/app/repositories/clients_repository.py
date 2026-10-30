"""Repository — base clients SAIFI/SAIDI (contrats par unité de relève, lien poste ↔ UR)."""

from typing import Any

from sqlalchemy import BigInteger, Float, case, cast, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clients import ContratsUniteReleve, PosteUniteReleve
from app.models.geo import Agence, Service
from app.models.indicateurs import NombreClientMois
from app.models.reseau import Poste

_LOT = 1000
# Un lien proposé à l'ajout ne compte qu'une fois validé ; une suppression proposée compte encore
_STATUTS_COMPTES = ("valide", "suppression_proposee")


async def agences_par_code(db: AsyncSession) -> dict[str, int]:
    """Code agence H2MC (« 110 ») → agence SIRV2 (code reprise « AG110 »)."""
    rows = (await db.execute(select(Agence.id, Agence.code))).all()
    resultat: dict[str, int] = {}
    for ident, code in rows:
        brut = code[2:] if code and code.startswith("AG") else code
        if brut:
            resultat[brut] = int(ident)
    return resultat


async def remplacer_contrats(db: AsyncSession, annee: int, mois: int, lignes: list[dict[str, Any]]) -> None:
    """Remplace la photo du mois (une ligne par UR)."""
    await db.execute(
        delete(ContratsUniteReleve).where(ContratsUniteReleve.annee == annee, ContratsUniteReleve.mois == mois)
    )
    for i in range(0, len(lignes), _LOT):
        await db.execute(insert(ContratsUniteReleve), lignes[i : i + _LOT])


async def contrats_par_agence(db: AsyncSession, annee: int, mois: int) -> list[tuple[int | None, int]]:
    stmt = (
        select(ContratsUniteReleve.agence_id, func.sum(cast(ContratsUniteReleve.nb_contrats, BigInteger)))
        .where(ContratsUniteReleve.annee == annee, ContratsUniteReleve.mois == mois)
        .group_by(ContratsUniteReleve.agence_id)
    )
    return [(a, int(n or 0)) for a, n in (await db.execute(stmt)).all()]


async def services_par_agence(db: AsyncSession) -> dict[int, int]:
    """Service porteur des clients d'une agence (même règle que la reprise de NombreClientMois)."""
    rows = (await db.execute(select(Service.agence_id, func.min(Service.id)).group_by(Service.agence_id))).all()
    return {int(a): int(s) for a, s in rows if a is not None}


async def clients_par_poste(db: AsyncSession, annee: int, mois: int) -> dict[int, int]:
    """Clients de chaque poste : contrats de ses UR, une UR partagée entre n postes comptant pour 1/n."""
    comptes = PosteUniteReleve.statut.in_(_STATUTS_COMPTES)
    partage = (
        select(PosteUniteReleve.unite_releve, func.count().label("n"))
        .where(comptes)
        .group_by(PosteUniteReleve.unite_releve)
        .subquery()
    )
    stmt = (
        select(
            PosteUniteReleve.poste_id,
            func.sum(cast(ContratsUniteReleve.nb_contrats, Float) / cast(partage.c.n, Float)),
        )
        .join(partage, partage.c.unite_releve == PosteUniteReleve.unite_releve)
        .join(
            ContratsUniteReleve,
            (ContratsUniteReleve.unite_releve == PosteUniteReleve.unite_releve)
            & (ContratsUniteReleve.annee == annee)
            & (ContratsUniteReleve.mois == mois),
        )
        .where(comptes)
        .group_by(PosteUniteReleve.poste_id)
    )
    return {int(p): int(round(n or 0)) for p, n in (await db.execute(stmt)).all()}


async def mettre_a_jour_clients_postes(db: AsyncSession, valeurs: dict[int, int]) -> None:
    for poste_id, clients in valeurs.items():
        await db.execute(update(Poste).where(Poste.id == poste_id).values(nombre_clients=clients))


async def remplacer_nombre_client_mois(db: AsyncSession, annee: int, mois: int, par_service: dict[int, int]) -> None:
    await db.execute(delete(NombreClientMois).where(NombreClientMois.annee == annee, NombreClientMois.mois == mois))
    lignes = [
        {"service_id": s, "annee": annee, "mois": mois, "nombre_clients": n} for s, n in sorted(par_service.items())
    ]
    if lignes:
        await db.execute(insert(NombreClientMois), lignes)


async def resume_periodes(db: AsyncSession, limite: int = 24) -> list[dict[str, Any]]:
    """Par mois : UR, contrats, contrats sans agence, UR et contrats rattachés à au moins un poste."""
    ur_rattachees = (
        select(PosteUniteReleve.unite_releve)
        .where(PosteUniteReleve.statut.in_(_STATUTS_COMPTES))
        .distinct()
        .subquery()
    )
    rattachee = ContratsUniteReleve.unite_releve.in_(select(ur_rattachees.c.unite_releve))
    contrats = cast(ContratsUniteReleve.nb_contrats, BigInteger)
    stmt = (
        select(
            ContratsUniteReleve.annee,
            ContratsUniteReleve.mois,
            func.count().label("ur"),
            func.sum(contrats).label("contrats"),
            func.sum(case((ContratsUniteReleve.agence_id.is_(None), contrats), else_=0)).label("contrats_sans_agence"),
            func.sum(case((rattachee, 1), else_=0)).label("ur_rattachees"),
            func.sum(case((rattachee, contrats), else_=0)).label("contrats_rattaches"),
            func.max(ContratsUniteReleve.date_maj).label("date_maj"),
            func.max(ContratsUniteReleve.source).label("source"),
        )
        .group_by(ContratsUniteReleve.annee, ContratsUniteReleve.mois)
        .order_by(ContratsUniteReleve.annee.desc(), ContratsUniteReleve.mois.desc())
        .limit(limite)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]


async def compter_liens(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(select(PosteUniteReleve.statut, func.count()).group_by(PosteUniteReleve.statut))
    ).all()
    return {str(s): int(n) for s, n in rows}

