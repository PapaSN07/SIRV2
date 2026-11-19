"""Repository — consultation de la topologie SIG (Administration → SIG).

Lecture seule : nœuds et tronçons importés du SIG (tables HFSQL Noeud_SIG / Troncon_SIG).
Chaque import ajoute un instantané de tronçons (``date_chargement``) : seuls les tronçons du dernier
chargement de leur départ sont retenus, comme pour le tronçonnement.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, Select, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.geo import Service
from app.models.interruptions import Interruption
from app.models.referentiel import Nature
from app.models.reseau import Feeder, PosteSource
from app.models.sig import FeederSig, NoeudSig, PosteSourceSig, TronconSig

_TRIS_TRONCONS = {"nom_troncon", "nom_feeder", "longueur_m", "tension_kv"}
_TRIS_NOEUDS = {"nom", "nom_feeder", "station", "categorie"}


def _motif(mot: str) -> str:
    return "%" + mot.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _recherche(colonnes: list[Any], texte: str | None) -> Any | None:
    """Chaque mot saisi doit apparaître dans l'une des colonnes (sans casse)."""
    mots = [m for m in (texte or "").strip().lower().split() if m][:5]
    if not mots:
        return None
    return and_(*(or_(*(func.lower(c).like(_motif(m), escape="\\") for c in colonnes)) for m in mots))


def _dernier_chargement() -> Any:
    """Tronçon du dernier chargement SIG de son départ (ou sans date de chargement)."""
    recent = aliased(TronconSig)
    dernier = (
        select(func.max(recent.date_chargement))
        .where(recent.nom_feeder == TronconSig.nom_feeder)
        .correlate(TronconSig)
        .scalar_subquery()
    )
    return or_(TronconSig.date_chargement.is_(None), TronconSig.date_chargement == dernier)


@dataclass(frozen=True)
class SyntheseSig:
    noeuds: int
    noeuds_localises: int
    noeuds_rattaches: int
    troncons: int
    longueur_km: float
    feeders_sig: int
    feeders_rattaches: int
    stations: int
    dernier_chargement: datetime | None
    categories: list[tuple[str, int]]


async def synthese(db: AsyncSession) -> SyntheseSig:
    noeuds = (
        await db.execute(
            select(
                func.count(NoeudSig.id),
                func.count(NoeudSig.coord_x),
                func.count(NoeudSig.feeder_id),
                func.count(func.distinct(NoeudSig.station)),
            )
        )
    ).one()
    troncons = (
        await db.execute(
            select(
                func.count(TronconSig.id),
                func.coalesce(func.sum(cast(TronconSig.longueur_m, Float)), 0.0),
                func.count(func.distinct(TronconSig.nom_feeder)),
                func.max(TronconSig.date_chargement),
            ).where(_dernier_chargement())
        )
    ).one()
    # Départs SIG rattachés à un feeder SIRV2 (au moins un tronçon avec feeder_id)
    rattaches = await db.scalar(
        select(func.count(func.distinct(TronconSig.nom_feeder))).where(
            _dernier_chargement(), TronconSig.feeder_id.isnot(None)
        )
    )
    categories = (
        await db.execute(
            select(func.coalesce(NoeudSig.categorie, "(sans catégorie)"), func.count(NoeudSig.id))
            .group_by(func.coalesce(NoeudSig.categorie, "(sans catégorie)"))
            .order_by(func.count(NoeudSig.id).desc())
        )
    ).all()
    return SyntheseSig(
        noeuds=int(noeuds[0]),
        noeuds_localises=int(noeuds[1]),
        noeuds_rattaches=int(noeuds[2]),
        stations=int(noeuds[3]),
        troncons=int(troncons[0]),
        longueur_km=float(troncons[1] or 0) / 1000.0,
        feeders_sig=int(troncons[2]),
        dernier_chargement=troncons[3],
        feeders_rattaches=int(rattaches or 0),
        categories=[(str(c), int(n)) for c, n in categories],
    )


async def _page(db: AsyncSession, query: Select[Any], page: int, page_size: int) -> tuple[list[Any], int]:
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()
    return list(rows), int(total or 0)


async def lister_stations(
    db: AsyncSession, *, recherche: str | None, page: int, page_size: int
) -> tuple[list[Any], int]:
    """Stations (postes sources) du SIG : nœuds, départs et position moyenne des nœuds localisés."""
    condition = _recherche([NoeudSig.station], recherche)
    query = (
        select(
            NoeudSig.station.label("station"),
            func.count(NoeudSig.id).label("noeuds"),
            func.count(func.distinct(NoeudSig.nom_feeder)).label("feeders"),
            func.avg(NoeudSig.coord_x).label("x"),
            func.avg(NoeudSig.coord_y).label("y"),
        )
        .where(NoeudSig.station.isnot(None))
        .group_by(NoeudSig.station)
        .order_by(NoeudSig.station)
    )
    if condition is not None:
        query = query.where(condition)
    return await _page(db, query, page, page_size)


async def postes_sources_sirv2(db: AsyncSession, noms: list[str]) -> dict[str, str]:
    """Poste source SIRV2 de même nom (sans casse) que les stations SIG données."""
    if not noms:
        return {}
    cles = sorted({n.upper() for n in noms if n})[:500]
    rows = (
        await db.execute(
            select(PosteSource.libelle).where(func.upper(PosteSource.libelle).in_(cles))
        )
    ).all()
    return {r.libelle.upper(): r.libelle for r in rows}


async def lister_feeders(
    db: AsyncSession,
    *,
    recherche: str | None,
    rattachement: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    """Départs du SIG (dernier chargement) : tronçons, longueur, tension et feeder SIRV2 rattaché."""
    query = (
        select(
            TronconSig.nom_feeder.label("nom_feeder"),
            func.count(TronconSig.id).label("troncons"),
            func.coalesce(func.sum(cast(TronconSig.longueur_m, Float)), 0.0).label("longueur_m"),
            func.max(TronconSig.tension_kv).label("tension_kv"),
            func.max(TronconSig.feeder_id).label("feeder_id"),
            func.max(TronconSig.date_chargement).label("date_chargement"),
        )
        .where(_dernier_chargement(), TronconSig.nom_feeder.isnot(None))
        .group_by(TronconSig.nom_feeder)
        .order_by(TronconSig.nom_feeder)
    )
    condition = _recherche([TronconSig.nom_feeder], recherche)
    if condition is not None:
        query = query.where(condition)
    if rattachement == "rattache":
        query = query.having(func.max(TronconSig.feeder_id).isnot(None))
    elif rattachement == "non_rattache":
        query = query.having(func.max(TronconSig.feeder_id).is_(None))
    return await _page(db, query, page, page_size)


async def feeders_sirv2(db: AsyncSession, ids: list[int]) -> dict[int, tuple[str, str | None]]:
    """Libellé du feeder SIRV2 et de son poste source, par identifiant."""
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(Feeder.id, Feeder.libelle, PosteSource.libelle.label("poste_source"))
            .outerjoin(PosteSource, PosteSource.id == Feeder.poste_source_id)
            .where(Feeder.id.in_(sorted(set(ids))))
        )
    ).all()
    return {r.id: (r.libelle, r.poste_source) for r in rows}


async def noeuds_par_feeder(db: AsyncSession, noms: list[str]) -> dict[str, tuple[int, int]]:
    """Nombre de nœuds et de nœuds localisés par départ SIG."""
    if not noms:
        return {}
    rows = (
        await db.execute(
            select(
                NoeudSig.nom_feeder,
                cast(func.count(NoeudSig.id), BigInteger),
                cast(func.count(NoeudSig.coord_x), BigInteger),
            )
            .where(NoeudSig.nom_feeder.in_(sorted(set(noms))))
            .group_by(NoeudSig.nom_feeder)
        )
    ).all()
    return {r[0]: (int(r[1]), int(r[2])) for r in rows}


async def lister_troncons(
    db: AsyncSession,
    *,
    recherche: str | None,
    nom_feeder: str | None,
    tri: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    query = select(
        TronconSig.id,
        TronconSig.nom_troncon,
        TronconSig.nom_feeder,
        TronconSig.feeder_id,
        TronconSig.nom_noeud_amont,
        TronconSig.code_noeud_amont,
        TronconSig.nom_noeud_aval,
        TronconSig.code_noeud_aval,
        TronconSig.tension_kv,
        TronconSig.longueur_m,
        TronconSig.date_chargement,
        TronconSig.imat_feeder,
        TronconSig.section,
        TronconSig.poste_source,
        TronconSig.type_conducteur,
        TronconSig.delegation,
        TronconSig.date_maj,
    ).where(_dernier_chargement())
    if nom_feeder:
        query = query.where(TronconSig.nom_feeder == nom_feeder)
    condition = _recherche(
        [
            TronconSig.nom_troncon,
            TronconSig.nom_feeder,
            TronconSig.nom_noeud_amont,
            TronconSig.nom_noeud_aval,
            TronconSig.code_noeud_amont,
            TronconSig.code_noeud_aval,
        ],
        recherche,
    )
    if condition is not None:
        query = query.where(condition)
    colonne = (tri or "").lstrip("-")
    if colonne in _TRIS_TRONCONS:
        attribut = getattr(TronconSig, colonne)
        query = query.order_by(attribut.desc() if (tri or "").startswith("-") else attribut.asc(), TronconSig.id)
    else:
        query = query.order_by(TronconSig.nom_feeder, TronconSig.nom_troncon, TronconSig.id)
    return await _page(db, query, page, page_size)


async def lister_noeuds(
    db: AsyncSession,
    *,
    recherche: str | None,
    nom_feeder: str | None,
    station: str | None,
    categorie: str | None,
    localisation: str | None,
    tri: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    query = select(
        NoeudSig.id,
        NoeudSig.legacy_fid,
        NoeudSig.nom,
        NoeudSig.nom_feeder,
        NoeudSig.feeder_id,
        NoeudSig.station,
        NoeudSig.categorie,
        NoeudSig.coord_x,
        NoeudSig.coord_y,
        NoeudSig.delegation,
        NoeudSig.region,
        NoeudSig.puissance,
        NoeudSig.famille_poste,
        NoeudSig.cellule,
    )
    if nom_feeder:
        query = query.where(NoeudSig.nom_feeder == nom_feeder)
    if station:
        query = query.where(NoeudSig.station == station)
    if categorie:
        query = query.where(NoeudSig.categorie == categorie)
    if localisation == "localise":
        query = query.where(NoeudSig.coord_x.isnot(None), NoeudSig.coord_y.isnot(None))
    elif localisation == "non_localise":
        query = query.where(or_(NoeudSig.coord_x.is_(None), NoeudSig.coord_y.is_(None)))
    condition = _recherche([NoeudSig.nom, NoeudSig.nom_feeder, NoeudSig.station], recherche)
    if condition is not None:
        query = query.where(condition)
    colonne = (tri or "").lstrip("-")
    if colonne in _TRIS_NOEUDS:
        attribut = getattr(NoeudSig, colonne)
        query = query.order_by(attribut.desc() if (tri or "").startswith("-") else attribut.asc(), NoeudSig.id)
    else:
        query = query.order_by(NoeudSig.nom, NoeudSig.id)
    return await _page(db, query, page, page_size)


async def noeuds_carte(
    db: AsyncSession,
    *,
    nom_feeder: str | None,
    station: str | None,
    limite: int = 3000,
) -> list[Any]:
    """Nœuds localisés d'un départ ou d'une station, pour la carte."""
    query = select(
        NoeudSig.id, NoeudSig.nom, NoeudSig.nom_feeder, NoeudSig.station, NoeudSig.categorie,
        NoeudSig.coord_x, NoeudSig.coord_y,
    ).where(NoeudSig.coord_x.isnot(None), NoeudSig.coord_y.isnot(None))
    if nom_feeder:
        query = query.where(NoeudSig.nom_feeder == nom_feeder)
    if station:
        query = query.where(NoeudSig.station == station)
    return list((await db.execute(query.order_by(NoeudSig.id).limit(limite))).all())


# ── Défauts aux 100 km ──────────────────────────────────────────────────────────


async def longueurs_feeders(db: AsyncSession) -> dict[int, float]:
    """Longueur SIG (mètres, dernier chargement) de chaque feeder SIRV2 rattaché."""
    rows = (
        await db.execute(
            select(TronconSig.feeder_id, func.coalesce(func.sum(cast(TronconSig.longueur_m, Float)), 0.0))
            .where(_dernier_chargement(), TronconSig.feeder_id.isnot(None))
            .group_by(TronconSig.feeder_id)
        )
    ).all()
    return {int(r[0]): float(r[1] or 0) for r in rows}


async def defauts_par_feeder_nature(db: AsyncSession, debut: datetime, fin: datetime) -> list[Any]:
    """Interruptions distribution (hors force majeure), par feeder et par nature, datées par l'apparition."""
    return list(
        (
            await db.execute(
                select(
                    Interruption.feeder_id,
                    func.coalesce(Nature.libelle, "Non renseignée").label("nature"),
                    func.count(Interruption.id).label("nombre"),
                )
                .outerjoin(Nature, Nature.id == Interruption.nature_id)
                .where(
                    Interruption.type_direction == "distribution",
                    Interruption.is_force_majeure == False,  # noqa: E712
                    Interruption.feeder_id.isnot(None),
                    Interruption.date_apparition >= debut,
                    Interruption.date_apparition < fin,
                )
                .group_by(Interruption.feeder_id, func.coalesce(Nature.libelle, "Non renseignée"))
            )
        ).all()
    )


async def feeders_avec_service(db: AsyncSession, ids: list[int]) -> dict[int, tuple[str, str | None, str | None]]:
    """Feeder SIRV2 → (libellé, poste source, service)."""
    if not ids:
        return {}
    resultat: dict[int, tuple[str, str | None, str | None]] = {}
    tries = sorted(set(ids))
    for debut in range(0, len(tries), 1000):
        rows = (
            await db.execute(
                select(
                    Feeder.id,
                    Feeder.libelle,
                    PosteSource.libelle.label("poste_source"),
                    Service.libelle.label("service"),
                )
                .outerjoin(PosteSource, PosteSource.id == Feeder.poste_source_id)
                .outerjoin(Service, Service.id == Feeder.service_id)
                .where(Feeder.id.in_(tries[debut : debut + 1000]))
            )
        ).all()
        resultat.update({r.id: (r.libelle, r.poste_source, r.service) for r in rows})
    return resultat


async def feeders_par_station(db: AsyncSession, stations: list[str]) -> dict[str, list[str]]:
    """Noms des départs SIG de chaque station (d'après les nœuds), triés."""
    if not stations:
        return {}
    rows = (
        await db.execute(
            select(NoeudSig.station, NoeudSig.nom_feeder)
            .where(NoeudSig.station.in_(sorted(set(stations))), NoeudSig.nom_feeder.isnot(None))
            .group_by(NoeudSig.station, NoeudSig.nom_feeder)
        )
    ).all()
    resultat: dict[str, list[str]] = {}
    for station, feeder in rows:
        resultat.setdefault(station, []).append(feeder)
    return {k: sorted(v) for k, v in resultat.items()}


async def postes_sources_sig(db: AsyncSession) -> list[PosteSourceSig]:
    """Postes sources de la table SIG PosteSource_SIG (petite table : lue en entier)."""
    return list((await db.execute(select(PosteSourceSig).order_by(PosteSourceSig.nom))).scalars().all())


async def feeders_sig_par_nom(db: AsyncSession, noms: list[str]) -> dict[str, FeederSig]:
    """Départs de la table SIG FEEDERS_SIG, par nom exact (départs listés à l'écran)."""
    if not noms:
        return {}
    rows = (await db.execute(select(FeederSig).where(FeederSig.nom.in_(sorted(set(noms)))))).scalars().all()
    return {r.nom: r for r in rows if r.nom}
