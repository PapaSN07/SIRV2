"""Service — consultation de la topologie SIG (Administration → SIG). Lecture seule."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import sig_admin_repository as repo
from app.repositories.pilotage_repository import _lon_lat
from app.schemas.common import PaginatedResponse
from app.schemas.sig import (
    CategorieSigResponse,
    FeederSigResponse,
    NoeudSigAdminResponse,
    StationSigResponse,
    SyntheseSigResponse,
    TronconSigAdminResponse,
)
from app.services.sig_service import _ensure_sig_read
from app.utils.pagination import clamp_page_size


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    return max(1, page), clamp_page_size(page_size)


def _paginee(items: list, total: int, page: int, page_size: int) -> PaginatedResponse:
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


async def synthese(db: AsyncSession, user: Utilisateur) -> SyntheseSigResponse:
    _ensure_sig_read(user)
    s = await repo.synthese(db)
    return SyntheseSigResponse(
        noeuds=s.noeuds,
        noeuds_localises=s.noeuds_localises,
        noeuds_rattaches=s.noeuds_rattaches,
        troncons=s.troncons,
        longueur_km=round(s.longueur_km, 1),
        feeders_sig=s.feeders_sig,
        feeders_rattaches=s.feeders_rattaches,
        stations=s.stations,
        dernier_chargement=s.dernier_chargement,
        categories=[CategorieSigResponse(categorie=c, nombre=n) for c, n in s.categories],
    )


async def stations(
    db: AsyncSession, user: Utilisateur, *, recherche: str | None, page: int, page_size: int
) -> PaginatedResponse[StationSigResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    rows, total = await repo.lister_stations(db, recherche=recherche, page=page, page_size=page_size)
    sirv2 = await repo.postes_sources_sirv2(db, [r.station for r in rows])
    items = []
    for r in rows:
        lon, lat = _lon_lat(r.x, r.y)
        items.append(
            StationSigResponse(
                station=r.station,
                noeuds=int(r.noeuds),
                feeders=int(r.feeders),
                latitude=lat,
                longitude=lon,
                poste_source_sirv2=sirv2.get(r.station.upper()),
            )
        )
    return _paginee(items, total, page, page_size)


async def feeders(
    db: AsyncSession,
    user: Utilisateur,
    *,
    recherche: str | None,
    rattachement: str | None,
    page: int,
    page_size: int,
) -> PaginatedResponse[FeederSigResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    rows, total = await repo.lister_feeders(
        db, recherche=recherche, rattachement=rattachement, page=page, page_size=page_size
    )
    sirv2 = await repo.feeders_sirv2(db, [r.feeder_id for r in rows if r.feeder_id is not None])
    noeuds = await repo.noeuds_par_feeder(db, [r.nom_feeder for r in rows])
    items = []
    for r in rows:
        libelle, poste_source = sirv2.get(r.feeder_id, (None, None)) if r.feeder_id else (None, None)
        nb, nb_loc = noeuds.get(r.nom_feeder, (0, 0))
        items.append(
            FeederSigResponse(
                nom_feeder=r.nom_feeder,
                troncons=int(r.troncons),
                longueur_km=round(float(r.longueur_m or 0) / 1000.0, 2),
                tension_kv=float(r.tension_kv) if r.tension_kv is not None else None,
                noeuds=nb,
                noeuds_localises=nb_loc,
                feeder_id=r.feeder_id,
                feeder_libelle=libelle,
                poste_source_libelle=poste_source,
                date_chargement=r.date_chargement,
            )
        )
    return _paginee(items, total, page, page_size)


async def troncons(
    db: AsyncSession,
    user: Utilisateur,
    *,
    recherche: str | None,
    nom_feeder: str | None,
    tri: str | None,
    page: int,
    page_size: int,
) -> PaginatedResponse[TronconSigAdminResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    rows, total = await repo.lister_troncons(
        db, recherche=recherche, nom_feeder=nom_feeder, tri=tri, page=page, page_size=page_size
    )
    items = [
        TronconSigAdminResponse(
            **{
                **r._mapping,
                "tension_kv": float(r.tension_kv) if r.tension_kv is not None else None,
                "longueur_m": float(r.longueur_m) if r.longueur_m is not None else None,
            }
        )
        for r in rows
    ]
    return _paginee(items, total, page, page_size)


def _noeud(r: object) -> NoeudSigAdminResponse:
    lon, lat = _lon_lat(r.coord_x, r.coord_y)  # type: ignore[attr-defined]
    return NoeudSigAdminResponse(**dict(r._mapping), latitude=lat, longitude=lon)  # type: ignore[attr-defined]


async def noeuds(
    db: AsyncSession,
    user: Utilisateur,
    *,
    recherche: str | None,
    nom_feeder: str | None,
    station: str | None,
    categorie: str | None,
    localisation: str | None,
    tri: str | None,
    page: int,
    page_size: int,
) -> PaginatedResponse[NoeudSigAdminResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    rows, total = await repo.lister_noeuds(
        db,
        recherche=recherche,
        nom_feeder=nom_feeder,
        station=station,
        categorie=categorie,
        localisation=localisation,
        tri=tri,
        page=page,
        page_size=page_size,
    )
    return _paginee([_noeud(r) for r in rows], total, page, page_size)


async def carte(
    db: AsyncSession, user: Utilisateur, *, nom_feeder: str | None, station: str | None
) -> list[NoeudSigAdminResponse]:
    """Nœuds localisés d'un départ ou d'une station (3 000 au plus), en WGS84."""
    _ensure_sig_read(user)
    if not nom_feeder and not station:
        return []
    rows = await repo.noeuds_carte(db, nom_feeder=nom_feeder, station=station)
    resultat = []
    for r in rows:
        lon, lat = _lon_lat(r.coord_x, r.coord_y)
        if lat is None:
            continue
        resultat.append(
            NoeudSigAdminResponse(
                id=r.id, legacy_fid=0, nom=r.nom, nom_feeder=r.nom_feeder, station=r.station,
                categorie=r.categorie, latitude=lat, longitude=lon,
            )
        )
    return resultat
