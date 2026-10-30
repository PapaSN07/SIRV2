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


async def mettre_a_jour_clients_postes(
    db: AsyncSession, valeurs: dict[int, int], postes_a_zero: set[int] | None = None
) -> None:
    """Met à jour les clients des postes ; ``postes_a_zero`` : postes qui n'ont plus d'UR comptée."""
    for poste_id, clients in valeurs.items():
        await db.execute(update(Poste).where(Poste.id == poste_id).values(nombre_clients=clients))
    for poste_id in (postes_a_zero or set()) - set(valeurs):
        await db.execute(update(Poste).where(Poste.id == poste_id).values(nombre_clients=0))


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
        select(PosteUniteReleve.unite_releve).where(PosteUniteReleve.statut.in_(_STATUTS_COMPTES)).distinct().subquery()
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
    rows = (await db.execute(select(PosteUniteReleve.statut, func.count()).group_by(PosteUniteReleve.statut))).all()
    return {str(s): int(n) for s, n in rows}


# ── Atelier : lien poste ↔ unité de relève ───────────────────────────────────


async def dernier_mois(db: AsyncSession) -> tuple[int, int] | None:
    row = (
        await db.execute(
            select(ContratsUniteReleve.annee, ContratsUniteReleve.mois)
            .order_by(ContratsUniteReleve.annee.desc(), ContratsUniteReleve.mois.desc())
            .limit(1)
        )
    ).first()
    return (int(row[0]), int(row[1])) if row else None


def _postes_du_perimetre(region_id: int | None) -> Any:
    """Sous-requête des postes de la région (BCC / BRC) ; None = national."""
    if region_id is None:
        return None
    return select(Service.id).where(Service.region_id == region_id)


async def region_du_poste(db: AsyncSession, poste_id: int) -> tuple[bool, int | None]:
    """(poste trouvé, région de son service)."""
    row = (
        await db.execute(
            select(Poste.id, Service.region_id)
            .outerjoin(Service, Service.id == Poste.service_id)
            .where(Poste.id == poste_id)
        )
    ).first()
    return (row is not None, row[1] if row else None)


async def rechercher_postes(
    db: AsyncSession, recherche: str, region_id: int | None, limite: int = 20
) -> list[dict[str, Any]]:
    motif = f"%{recherche.strip()}%"
    nb_ur = (
        select(func.count())
        .where(PosteUniteReleve.poste_id == Poste.id, PosteUniteReleve.statut.in_(_STATUTS_COMPTES))
        .correlate(Poste)
        .scalar_subquery()
    )
    stmt = (
        select(
            Poste.id,
            Poste.code,
            Poste.libelle,
            Service.libelle.label("service"),
            Poste.nombre_clients,
            nb_ur.label("nb_ur"),
        )
        .outerjoin(Service, Service.id == Poste.service_id)
        .where((Poste.code.ilike(motif)) | (Poste.libelle.ilike(motif)))
        .order_by(Poste.code)
        .limit(limite)
    )
    perimetre = _postes_du_perimetre(region_id)
    if perimetre is not None:
        stmt = stmt.where(Poste.service_id.in_(perimetre))
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]


async def rechercher_ur(
    db: AsyncSession, recherche: str, annee: int, mois: int, limite: int = 20
) -> list[dict[str, Any]]:
    motif = f"{recherche.strip().upper()}%"
    nb_postes = (
        select(func.count())
        .where(
            PosteUniteReleve.unite_releve == ContratsUniteReleve.unite_releve,
            PosteUniteReleve.statut.in_(_STATUTS_COMPTES),
        )
        .correlate(ContratsUniteReleve)
        .scalar_subquery()
    )
    stmt = (
        select(
            ContratsUniteReleve.unite_releve,
            ContratsUniteReleve.libelle,
            ContratsUniteReleve.nb_contrats,
            nb_postes.label("nb_postes"),
        )
        .where(
            ContratsUniteReleve.annee == annee,
            ContratsUniteReleve.mois == mois,
            ContratsUniteReleve.unite_releve.like(motif),
        )
        .order_by(ContratsUniteReleve.unite_releve)
        .limit(limite)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]


async def lister_liens(
    db: AsyncSession,
    *,
    region_id: int | None,
    periode: tuple[int, int] | None,
    poste_id: int | None = None,
    statut: str | None = None,
    a_valider: bool = False,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    from sqlalchemy.orm import aliased

    from app.models.utilisateurs import Utilisateur

    modif = aliased(Utilisateur)
    valid = aliased(Utilisateur)
    partage = (
        select(PosteUniteReleve.unite_releve, func.count().label("n"))
        .where(PosteUniteReleve.statut.in_(_STATUTS_COMPTES))
        .group_by(PosteUniteReleve.unite_releve)
        .subquery()
    )
    annee, mois = periode or (0, 0)
    conditions = []
    perimetre = _postes_du_perimetre(region_id)
    if perimetre is not None:
        conditions.append(Poste.service_id.in_(perimetre))
    if poste_id is not None:
        conditions.append(PosteUniteReleve.poste_id == poste_id)
    if statut:
        conditions.append(PosteUniteReleve.statut == statut)
    if a_valider:
        conditions.append(PosteUniteReleve.statut != "valide")
    if recherche and recherche.strip():
        motif = f"%{recherche.strip()}%"
        conditions.append(
            Poste.code.ilike(motif) | Poste.libelle.ilike(motif) | PosteUniteReleve.unite_releve.ilike(motif)
        )
    base = select(PosteUniteReleve.id).join(Poste, Poste.id == PosteUniteReleve.poste_id).where(*conditions)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    stmt = (
        select(
            PosteUniteReleve.id,
            PosteUniteReleve.poste_id,
            Poste.code.label("poste_code"),
            Poste.libelle.label("poste_libelle"),
            Service.libelle.label("service"),
            PosteUniteReleve.unite_releve,
            ContratsUniteReleve.libelle.label("ur_libelle"),
            ContratsUniteReleve.nb_contrats,
            partage.c.n.label("nb_postes"),
            PosteUniteReleve.statut,
            (modif.prenom + " " + modif.nom).label("modifie_par"),
            PosteUniteReleve.modifie_le,
            (valid.prenom + " " + valid.nom).label("valide_par"),
            PosteUniteReleve.valide_le,
        )
        .join(Poste, Poste.id == PosteUniteReleve.poste_id)
        .outerjoin(Service, Service.id == Poste.service_id)
        .outerjoin(partage, partage.c.unite_releve == PosteUniteReleve.unite_releve)
        .outerjoin(
            ContratsUniteReleve,
            (ContratsUniteReleve.unite_releve == PosteUniteReleve.unite_releve)
            & (ContratsUniteReleve.annee == annee)
            & (ContratsUniteReleve.mois == mois),
        )
        .outerjoin(modif, modif.id == PosteUniteReleve.modifie_par_id)
        .outerjoin(valid, valid.id == PosteUniteReleve.valide_par_id)
        .where(*conditions)
        .order_by(Poste.code, PosteUniteReleve.unite_releve)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()], total


async def get_lien(db: AsyncSession, lien_id: int) -> PosteUniteReleve | None:
    return await db.get(PosteUniteReleve, lien_id)


async def get_lien_par_couple(db: AsyncSession, poste_id: int, unite_releve: str) -> PosteUniteReleve | None:
    return (
        await db.execute(
            select(PosteUniteReleve).where(
                PosteUniteReleve.poste_id == poste_id, PosteUniteReleve.unite_releve == unite_releve
            )
        )
    ).scalar_one_or_none()


async def ajouter_lien(db: AsyncSession, lien: PosteUniteReleve) -> PosteUniteReleve:
    db.add(lien)
    await db.flush()
    return lien


async def supprimer_lien(db: AsyncSession, lien: PosteUniteReleve) -> None:
    await db.delete(lien)
    await db.flush()


async def postes_partageant(db: AsyncSession, unite_releve: str) -> list[int]:
    rows = await db.execute(select(PosteUniteReleve.poste_id).where(PosteUniteReleve.unite_releve == unite_releve))
    return [int(p) for (p,) in rows.all()]
