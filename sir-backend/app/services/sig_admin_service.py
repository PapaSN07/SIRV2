"""Service — consultation de la topologie SIG (Administration → SIG). Lecture seule."""

import json
import re
from collections import defaultdict
from datetime import date, datetime

from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import sig_admin_repository as repo
from app.repositories.pilotage_repository import _lon_lat
from app.schemas.common import PaginatedResponse
from app.schemas.sig import (
    CategorieSigResponse,
    Defauts100KmLigne,
    Defauts100KmNature,
    Defauts100KmResponse,
    FeederSigResponse,
    NoeudSigAdminResponse,
    StationSigResponse,
    SyntheseSigResponse,
    TronconSigAdminResponse,
)
from app.services.rapport_hebdo_dd_service import _norme
from app.services.sig_service import _ensure_sig_read
from app.utils.pagination import clamp_page_size

T = TypeVar("T", bound=BaseModel)


SIG_CACHE_TTL_SECONDES = 6 * 3600  # données SIG : changent seulement à l'import


async def _avec_cache(redis: Redis | None, cle: str, modele: type[T], calcul: Callable[[], Awaitable[T]]) -> T:
    """Résultat en cache Redis (clé ``sig:…``) ; Redis indisponible → calcul direct."""
    if redis is not None:
        try:
            brut = await redis.get(cle)
            if brut:
                return modele.model_validate_json(brut)
        except Exception:  # noqa: BLE001 — le cache ne doit jamais bloquer l'écran
            pass
    resultat = await calcul()
    if redis is not None:
        try:
            await redis.setex(cle, SIG_CACHE_TTL_SECONDES, resultat.model_dump_json(by_alias=True))
        except Exception:  # noqa: BLE001
            pass
    return resultat


def _cle_cache(*parties: object) -> str:
    return "sig:v3:" + ":".join(str(p if p is not None else "") for p in parties)


def _cle(valeur: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norme(str(valeur or "")))


def _infos_feeder_sig(ligne: object | None) -> dict[str, object]:
    if ligne is None:
        return {}
    try:
        attributs = json.loads(getattr(ligne, "attributs", None) or "{}")
    except ValueError:
        attributs = {}
    bas = {str(k).lower(): v for k, v in attributs.items()}
    km = bas.get("nombre_km")
    try:
        km = round(float(str(km).replace(",", ".")), 2) if km not in (None, "") else None
    except ValueError:
        km = None
    mise = bas.get("date_mise_en_service")
    return {
        "code_sig": getattr(ligne, "code", None),
        "poste_source_sig": getattr(ligne, "poste_source", None),
        "delegation": getattr(ligne, "delegation", None),
        "categorie_sig": str(bas["categories"]).strip().upper() if bas.get("categories") not in (None, "") else None,
        "km_sig": km,
        "mise_en_service": str(mise)[:10] if mise else None,
        "attributs": attributs or None,
    }


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    return max(1, page), clamp_page_size(page_size)


def _paginee(items: list, total: int, page: int, page_size: int) -> PaginatedResponse:
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


async def synthese(db: AsyncSession, user: Utilisateur, redis: Redis | None = None) -> SyntheseSigResponse:
    _ensure_sig_read(user)
    return await _avec_cache(redis, _cle_cache("synthese"), SyntheseSigResponse, lambda: _synthese(db))


async def _synthese(db: AsyncSession) -> SyntheseSigResponse:
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
    db: AsyncSession,
    user: Utilisateur,
    *,
    recherche: str | None,
    page: int,
    page_size: int,
    redis: Redis | None = None,
) -> PaginatedResponse[StationSigResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    return await _avec_cache(
        redis,
        _cle_cache("stations", (recherche or "").strip().lower(), page, page_size),
        PaginatedResponse[StationSigResponse],
        lambda: _stations(db, recherche, page, page_size),
    )


async def _stations(
    db: AsyncSession, recherche: str | None, page: int, page_size: int
) -> PaginatedResponse[StationSigResponse]:
    rows, total = await repo.lister_stations(db, recherche=recherche, page=page, page_size=page_size)
    noms_feeders = await repo.feeders_par_station(db, [r.station for r in rows])
    # PosteSource_SIG : la station des nœuds peut être un identifiant ou un code → nom du poste source
    index: dict[str, object] = {}
    for ps in await repo.postes_sources_sig(db):
        for k in (ps.legacy_id, ps.code, ps.nom):
            if k:
                index.setdefault(_cle(k), ps)
    noms_ps = [r.station for r in rows] + [getattr(index.get(_cle(r.station)), "nom", None) or "" for r in rows]
    sirv2 = await repo.postes_sources_sirv2(db, [n for n in noms_ps if n])
    items = []
    for r in rows:
        lon, lat = _lon_lat(r.x, r.y)
        ps = index.get(_cle(r.station))
        nom = getattr(ps, "nom", None)
        items.append(
            StationSigResponse(
                station=r.station,
                nom=nom if nom and _cle(nom) != _cle(r.station) else None,
                delegation=getattr(ps, "delegation", None),
                region=getattr(ps, "region", None),
                noeuds=int(r.noeuds),
                feeders=int(r.feeders),
                feeders_noms=noms_feeders.get(r.station, []),
                latitude=lat,
                longitude=lon,
                poste_source_sirv2=sirv2.get(r.station.upper()) or (sirv2.get(nom.upper()) if nom else None),
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
    redis: Redis | None = None,
) -> PaginatedResponse[FeederSigResponse]:
    _ensure_sig_read(user)
    page, page_size = _pagination(page, page_size)
    return await _avec_cache(
        redis,
        _cle_cache("feeders", (recherche or "").strip().lower(), rattachement, page, page_size),
        PaginatedResponse[FeederSigResponse],
        lambda: _feeders(db, recherche, rattachement, page, page_size),
    )


async def _feeders(
    db: AsyncSession, recherche: str | None, rattachement: str | None, page: int, page_size: int
) -> PaginatedResponse[FeederSigResponse]:
    rows, total = await repo.lister_feeders(
        db, recherche=recherche, rattachement=rattachement, page=page, page_size=page_size
    )
    sirv2 = await repo.feeders_sirv2(db, [r.feeder_id for r in rows if r.feeder_id is not None])
    noeuds = await repo.noeuds_par_feeder(db, [r.nom_feeder for r in rows])
    table_sig = await repo.feeders_sig_par_nom(db, [r.nom_feeder for r in rows])
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
                **_infos_feeder_sig(table_sig.get(r.nom_feeder)),
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


def _est_permanent(nature: str) -> bool:
    """Nature « permanent » (pas « semi-permanent ») : même règle que les rapports DD."""
    return _norme(nature).startswith("PERMANENT")


def _pour_100km(nombre: int, km: float) -> float | None:
    return round(nombre * 100.0 / km, 2) if km > 0 else None


def bornes_periode(annee: int | None, mois: int | None, aujourd_hui: date | None = None) -> tuple[datetime, datetime]:
    """Année (cumul jusqu'à aujourd'hui pour l'année en cours) ou mois ; défaut : année en cours."""
    jour = aujourd_hui or date.today()
    a = annee or jour.year
    if mois:
        debut = datetime(a, mois, 1)
        return debut, datetime(a + (mois == 12), mois % 12 + 1, 1)
    return datetime(a, 1, 1), datetime(a + 1, 1, 1)


async def defauts_100km(
    db: AsyncSession,
    user: Utilisateur,
    *,
    annee: int | None,
    mois: int | None,
    limite_feeders: int = 300,
    redis: Redis | None = None,
) -> Defauts100KmResponse:
    _ensure_sig_read(user)
    debut, _ = bornes_periode(annee, mois)
    # Mois ou année en cours : les défauts bougent dans la journée → cache court
    return await _avec_cache(
        redis,
        _cle_cache("defauts", debut.year, mois, date.today().isoformat()),
        Defauts100KmResponse,
        lambda: _defauts_100km(db, annee, mois, limite_feeders),
    )


async def _defauts_100km(
    db: AsyncSession, annee: int | None, mois: int | None, limite_feeders: int
) -> Defauts100KmResponse:
    """Défauts aux 100 km de réseau : global, par service, par feeder SIG et par nature.

    Défaut = interruption distribution hors force majeure, datée par son apparition.
    Longueur = tronçons SIG du dernier chargement rattachés au feeder (ceux sans longueur SIG
    sont comptés à part, ils n'entrent pas dans les ratios).
    """
    debut, fin = bornes_periode(annee, mois)
    longueurs_m = await repo.longueurs_feeders(db)
    lignes = await repo.defauts_par_feeder_nature(db, debut, fin)
    infos = await repo.feeders_avec_service(db, list({r.feeder_id for r in lignes} | set(longueurs_m)))

    par_feeder: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # [défauts, permanents]
    par_nature: dict[str, int] = defaultdict(int)
    sans_longueur = 0
    for r in lignes:
        if longueurs_m.get(r.feeder_id, 0) <= 0:
            sans_longueur += int(r.nombre)
            continue
        par_feeder[r.feeder_id][0] += int(r.nombre)
        if _est_permanent(r.nature):
            par_feeder[r.feeder_id][1] += int(r.nombre)
        par_nature[r.nature] += int(r.nombre)

    km_total = sum(longueurs_m.values()) / 1000.0
    total = sum(v[0] for v in par_feeder.values())
    total_perm = sum(v[1] for v in par_feeder.values())

    def ligne(libelle: str, detail: str | None, nb: int, perm: int, km: float) -> Defauts100KmLigne:
        return Defauts100KmLigne(
            libelle=libelle,
            detail=detail,
            defauts=nb,
            permanents=perm,
            longueur_km=round(km, 1),
            defauts_100km=_pour_100km(nb, km),
            permanents_100km=_pour_100km(perm, km),
        )

    # Par service : somme des feeders du service (défauts et longueurs)
    services: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0.0])
    for feeder_id, metres in longueurs_m.items():
        service = (infos.get(feeder_id, (None, None, None))[2]) or "Sans service"
        nb, perm = par_feeder.get(feeder_id, [0, 0])
        services[service][0] += nb
        services[service][1] += perm
        services[service][2] += metres / 1000.0

    feeders = []
    for feeder_id, metres in longueurs_m.items():
        nb, perm = par_feeder.get(feeder_id, [0, 0])
        libelle, poste_source, service = infos.get(feeder_id, (f"Feeder #{feeder_id}", None, None))
        detail = " · ".join(x for x in (poste_source, service) if x) or None
        feeders.append(ligne(libelle, detail, nb, perm, metres / 1000.0))
    feeders.sort(key=lambda x: (x.defauts_100km or 0, x.defauts), reverse=True)

    return Defauts100KmResponse(
        debut=debut,
        fin=fin,
        global_=ligne("Réseau HTA (SIG)", None, total, total_perm, km_total),
        par_nature=sorted(
            (Defauts100KmNature(nature=n, defauts=c, defauts_100km=_pour_100km(c, km_total)) for n, c in par_nature.items()),
            key=lambda x: x.defauts,
            reverse=True,
        ),
        par_service=sorted(
            (ligne(nom, None, int(v[0]), int(v[1]), v[2]) for nom, v in services.items()),
            key=lambda x: x.defauts_100km or 0,
            reverse=True,
        ),
        par_feeder=feeders[:limite_feeders],
        defauts_sans_longueur=sans_longueur,
    )
