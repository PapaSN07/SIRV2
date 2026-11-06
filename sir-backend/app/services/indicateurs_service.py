"""Service métier — lecture indicateurs END / SAIFI / SAIDI (Sprint 5.4+)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_region_scope, check_service_scope
from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import indicateurs_repository as repo
from app.repositories import pilotage_repository
from app.schemas.common import PaginatedResponse
from app.schemas.indicateurs import (
    SaifiSaidiValeurs,
    SyntheseSaifiSaidiPeriode,
    SyntheseSaifiSaidiResponse,
    EndAggregateResponse,
    EndIndicateurResponse,
    EndServiceItemResponse,
    SaifiIndicateurResponse,
    SaifiSaidiAggregateResponse,
    SaifiServiceItemResponse,
    SaidiIndicateurResponse,
    SaidiServiceItemResponse,
    TableauDeBordResponse,
    HistoriquePointResponse,
    HistoriqueResponse,
    TopFeederItemResponse,
    TopFeedersResponse,
    CauseRepartitionItemResponse,
    NatureRepartitionItemResponse,
    NatureServiceCellResponse,
    NatureServiceColumnResponse,
    NatureServiceLigneResponse,
    NatureServiceRepartitionResponse,
)
from app.services import saifi_saidi_service
from app.services.indicateurs_cache_service import (
    build_cache_key,
    get_cached,
    get_or_load,
    get_or_load_historique,
    get_or_load_top_feeders,
    set_cached,
)
from app.utils.pagination import clamp_page_size
from app.repositories.perimetre import definir_region

_NATIONAL_ROLES = frozenset({"ADMIN_SCR", "ADMIN_SAQS"})
_REGION_ROLES = frozenset({"BCC", "BRC"})
_SERVICE_ROLES = frozenset({"SUPERVISEUR"})


@dataclass(frozen=True)
class _ScopeContext:
    niveau: str
    scope_id: int | None
    service_ids: list[int]
    cache_region_id: int


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _resolve_scope(
    user: Utilisateur,
    *,
    region_id: int | None,
) -> _ScopeContext:
    roles = _user_role_names(user)

    if is_superadmin(user) or roles.intersection(_NATIONAL_ROLES):
        if region_id is not None:
            return _ScopeContext(
                niveau="region",
                scope_id=region_id,
                service_ids=[],
                cache_region_id=region_id,
            )
        return _ScopeContext(
            niveau="national",
            scope_id=None,
            service_ids=[],
            cache_region_id=0,
        )

    if roles.intersection(_REGION_ROLES):
        user_region_id = user.user_roles[0].scope_service_id
        if user_region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre régional non configuré pour ce compte",
                },
            )
        if region_id is not None and region_id != user_region_id:
            check_region_scope(user, region_id)
        return _ScopeContext(
            niveau="region",
            scope_id=user_region_id,
            service_ids=[],
            cache_region_id=user_region_id,
        )

    if roles.intersection(_SERVICE_ROLES):
        service_id = user.user_roles[0].scope_service_id
        if service_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre de service non configuré pour ce compte",
                },
            )
        if region_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : filtre region_id non autorisé pour votre rôle",
                },
            )
        return _ScopeContext(
            niveau="service",
            scope_id=service_id,
            service_ids=[service_id],
            cache_region_id=-1,
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Permission manquante : indicateurs:read",
        },
    )


async def _load_service_ids(db: AsyncSession, scope: _ScopeContext) -> list[int]:
    """Services du périmètre ; pose aussi la région du calcul (app.repositories.perimetre).

    Région (Dakar BCC / Régions BRC) : tous les services, filtrés ensuite par la région de
    l'interruption et par celle des services qui portent la base clients.
    """
    if scope.niveau == "region" and scope.scope_id is not None:
        definir_region(scope.scope_id)
        return await repo.list_all_service_ids(db)
    definir_region(None)
    if scope.service_ids:
        return scope.service_ids
    return await repo.list_all_service_ids(db)


def _bornes_mois(annee: int, mois: int) -> tuple[datetime, datetime]:
    debut = datetime(annee, mois, 1)
    fin = datetime(annee + (mois == 12), mois % 12 + 1, 1)
    return debut, fin


def _paginate_items(items: list, page: int, page_size: int):
    page_size = clamp_page_size(page_size)
    page = max(1, page)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], len(items), page, page_size


def _aggregate_end_rows(
    rows: list,
    *,
    scope: _ScopeContext,
    annee: int,
    mois: int,
) -> EndIndicateurResponse:
    total_end = sum(r.end_mwh for r in rows)
    total_nb = sum(r.nombre_interruptions for r in rows)
    aggregate = EndAggregateResponse(
        niveau=scope.niveau,
        scope_id=scope.scope_id,
        annee=annee,
        mois=mois,
        end_mwh=total_end,
        nombre_interruptions=total_nb,
    )
    return EndIndicateurResponse(aggregate=aggregate, services=None)


async def _load_cached(
    redis: Redis,
    indicateur_type: str,
    cache_region_id: int,
    annee: int,
    mois: int,
    scope: _ScopeContext,
    loader,
    response_type: type,
):
    if scope.niveau == "service":
        return response_type.model_validate(await loader())
    return response_type.model_validate(await get_or_load(redis, indicateur_type, cache_region_id, annee, mois, loader))


async def get_end(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    include_services: bool = False,
) -> EndIndicateurResponse:
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        service_ids = await _load_service_ids(db, scope)
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        rows = await repo.aggregate_end_by_services(db, service_ids=service_ids, annee=annee, mois=mois)
        result = _aggregate_end_rows(rows, scope=scope, annee=annee, mois=mois)
        return result.model_dump()

    response = await _load_cached(
        redis, "end", scope.cache_region_id, annee, mois, scope, _loader, EndIndicateurResponse
    )

    if include_services and scope.niveau != "service":
        service_ids = await _load_service_ids(db, scope)
        rows = await repo.aggregate_end_by_services(db, service_ids=service_ids, annee=annee, mois=mois)
        items = [
            EndServiceItemResponse(
                service_id=r.service_id,
                end_mwh=r.end_mwh,
                nombre_interruptions=r.nombre_interruptions,
            )
            for r in sorted(rows, key=lambda row: row.service_id)
        ]
        slice_items, total, pg, ps = _paginate_items(items, page, page_size)
        response.services = PaginatedResponse(
            items=slice_items,
            total=total,
            page=pg,
            page_size=ps,
        )

    return response


async def get_saifi(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    include_services: bool = False,
) -> SaifiIndicateurResponse:
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        service_ids = await _load_service_ids(db, scope)
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        debut, fin = _bornes_mois(annee, mois)
        calcul = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut, fin)
        nb, total_clients = calcul.nombre_interruptions, calcul.total_clients_reference
        aggregate = SaifiSaidiAggregateResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=annee,
            mois=mois,
            saifi=calcul.saifi,
            saidi=0.0,
            nombre_interruptions=nb,
            total_clients_reference=total_clients,
        )
        return SaifiIndicateurResponse(aggregate=aggregate, services=None).model_dump()

    response = await _load_cached(
        redis, "saifi", scope.cache_region_id, annee, mois, scope, _loader, SaifiIndicateurResponse
    )

    if include_services and scope.niveau != "service":
        service_ids = await _load_service_ids(db, scope)
        records = await repo.list_saifi_saidi_for_services(db, service_ids=service_ids, annee=annee, mois=mois)
        items = [
            SaifiServiceItemResponse(
                service_id=r.service_id,
                saifi=float(r.saifi),
                nombre_interruptions=r.nombre_interruptions,
                total_clients_reference=r.total_clients_reference,
            )
            for r in sorted(records, key=lambda rec: rec.service_id)
        ]
        slice_items, total, pg, ps = _paginate_items(items, page, page_size)
        response.services = PaginatedResponse(
            items=slice_items,
            total=total,
            page=pg,
            page_size=ps,
        )

    return response


async def get_saidi(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    include_services: bool = False,
) -> SaidiIndicateurResponse:
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        service_ids = await _load_service_ids(db, scope)
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        debut, fin = _bornes_mois(annee, mois)
        calcul = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut, fin)
        nb, total_clients = calcul.nombre_interruptions, calcul.total_clients_reference
        aggregate = SaifiSaidiAggregateResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=annee,
            mois=mois,
            saifi=0.0,
            saidi=calcul.saidi,
            nombre_interruptions=nb,
            total_clients_reference=total_clients,
        )
        return SaidiIndicateurResponse(aggregate=aggregate, services=None).model_dump()

    response = await _load_cached(
        redis, "saidi", scope.cache_region_id, annee, mois, scope, _loader, SaidiIndicateurResponse
    )

    if include_services and scope.niveau != "service":
        service_ids = await _load_service_ids(db, scope)
        records = await repo.list_saifi_saidi_for_services(db, service_ids=service_ids, annee=annee, mois=mois)
        items = [
            SaidiServiceItemResponse(
                service_id=r.service_id,
                saidi=float(r.saidi),
                nombre_interruptions=r.nombre_interruptions,
                total_clients_reference=r.total_clients_reference,
            )
            for r in sorted(records, key=lambda rec: rec.service_id)
        ]
        slice_items, total, pg, ps = _paginate_items(items, page, page_size)
        response.services = PaginatedResponse(
            items=slice_items,
            total=total,
            page=pg,
            page_size=ps,
        )

    return response


def _type_directions_for_user(user: Utilisateur) -> tuple[str, ...]:
    if "ADMIN_SAQS" in _user_role_names(user):
        return ("distribution", "transport")
    return ("distribution",)


def _resolve_period(
    *,
    periode: str | None,
    annee: int | None,
    mois: int | None,
) -> tuple[int, int]:
    if annee is not None and mois is not None:
        return annee, mois
    if periode:
        year_str, month_str = periode.split("-", 1)
        return int(year_str), int(month_str)
    now = datetime.now()
    return now.year, now.month


async def _count_interruptions_for_scope(
    db: AsyncSession,
    scope: _ScopeContext,
    user: Utilisateur,
    *,
    statut: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
    debut: datetime | None = None,
    fin: datetime | None = None,
) -> int:
    directions = _type_directions_for_user(user)
    service_ids = await _load_service_ids(db, scope)
    total = 0

    if "distribution" in directions:
        total += await repo.count_distribution_interruptions(
            db,
            service_ids=service_ids,
            statut=statut,
            annee=annee,
            mois=mois,
            debut=debut,
            fin=fin,
        )

    if "transport" in directions and scope.niveau == "national":
        total += await repo.count_transport_interruptions(
            db,
            statut=statut,
            annee=annee,
            mois=mois,
            debut=debut,
            fin=fin,
        )

    return total


_NATURE_SERVICE_ORDER = ["COUPURE", "DELESTAGE", "FUGITIF", "PERMANENT", "SEMI_PERM"]


def build_nature_service_repartition(
    rows: list[repo.NatureServiceRow],
) -> NatureServiceRepartitionResponse:
    """Croise les agrégats nature × service pour le tableau de bord."""
    services: dict[int, tuple[str, str]] = {}
    by_nature: dict[str, dict[str, object]] = {}
    for row in rows:
        services[row.service_id] = (row.service_code, row.service_libelle)
        bucket = by_nature.setdefault(
            row.nature_code,
            {"libelle": row.nature_libelle, "cells": {}},
        )
        cells = bucket["cells"]
        assert isinstance(cells, dict)
        cells[row.service_id] = (row.nombre, row.end_mwh)

    ordered_services = sorted(services.items(), key=lambda item: (item[1][0], item[0]))

    def _nature_sort(code: str) -> tuple[int, str]:
        if code in _NATURE_SERVICE_ORDER:
            return (_NATURE_SERVICE_ORDER.index(code), code)
        return (len(_NATURE_SERVICE_ORDER), code)

    service_nombre = {service_id: 0 for service_id, _meta in ordered_services}
    service_end = {service_id: 0.0 for service_id, _meta in ordered_services}
    lignes: list[NatureServiceLigneResponse] = []

    for code in sorted(by_nature, key=_nature_sort):
        info = by_nature[code]
        cells = info["cells"]
        assert isinstance(cells, dict)
        cellules: list[NatureServiceCellResponse] = []
        row_nombre = 0
        row_end = 0.0
        for service_id, _meta in ordered_services:
            nombre, end_mwh = cells.get(service_id, (0, 0.0))
            cellules.append(NatureServiceCellResponse(nombre=int(nombre), end_kwh=round(float(end_mwh) * 1000, 2)))
            row_nombre += int(nombre)
            row_end += float(end_mwh)
            service_nombre[service_id] += int(nombre)
            service_end[service_id] += float(end_mwh)
        lignes.append(
            NatureServiceLigneResponse(
                code=code,
                libelle=str(info["libelle"]),
                cellules=cellules,
                nombre=row_nombre,
                end_kwh=round(row_end * 1000, 2),
            )
        )

    columns = [
        NatureServiceColumnResponse(
            service_id=service_id,
            code=code,
            libelle=libelle,
            nombre=service_nombre[service_id],
            end_kwh=round(service_end[service_id] * 1000, 2),
        )
        for service_id, (code, libelle) in ordered_services
    ]
    return NatureServiceRepartitionResponse(
        services=columns,
        lignes=lignes,
        total_nombre=sum(service_nombre.values()),
        total_end_kwh=round(sum(service_end.values()) * 1000, 2),
    )


Granularite = Literal["jour", "mois", "annee"]


@dataclass(frozen=True)
class PeriodeTableau:
    """Période du tableau de bord : jour, mois ou année ; bornes [debut, fin[."""

    granularite: Granularite
    debut: datetime
    fin: datetime

    @property
    def annee(self) -> int:
        return self.debut.year

    @property
    def mois(self) -> int:
        return self.debut.month

    @property
    def cle_cache(self) -> tuple[str, int, int]:
        if self.granularite == "jour":
            return "tableau-de-bord-jour", self.annee, int(self.debut.strftime("%m%d"))
        if self.granularite == "annee":
            return "tableau-de-bord-annee", self.annee, 0
        return "tableau-de-bord", self.annee, self.mois


def resoudre_periode_tableau(
    periode: str | None,
    annee: int | None = None,
    mois: int | None = None,
    aujourd_hui: date | None = None,
) -> PeriodeTableau:
    """« AAAA » → année, « AAAA-MM » → mois, « AAAA-MM-JJ » → jour ; défaut : mois en cours."""
    if periode and len(periode) == 10:
        jour = date.fromisoformat(periode)
        debut = datetime(jour.year, jour.month, jour.day)
        return PeriodeTableau("jour", debut, debut + timedelta(days=1))
    if periode and len(periode) == 4:
        a = int(periode)
        return PeriodeTableau("annee", datetime(a, 1, 1), datetime(a + 1, 1, 1))
    if periode is None and annee is None:
        ref = aujourd_hui or date.today()
        annee, mois = ref.year, ref.month
    a, m = _resolve_period(periode=periode, annee=annee, mois=mois)
    debut, fin = _bornes_mois(a, m)
    return PeriodeTableau("mois", debut, fin)


async def get_tableau_de_bord(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    periode: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
    region_id: int | None = None,
) -> TableauDeBordResponse:
    per = resoudre_periode_tableau(periode, annee, mois)
    scope = _resolve_scope(user, region_id=region_id)
    bornes = {"debut": per.debut, "fin": per.fin}

    async def _loader() -> dict:
        service_ids = await _load_service_ids(db, scope)
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        # Mêmes définitions que les indicateurs mensuels : END des interruptions remises
        # dans la période, SAIFI/SAIDI des interruptions apparues (formule SENELEC)
        end_mwh = await pilotage_repository.sommer_end_mwh(db, service_ids, per.debut, per.fin)
        calcul = await saifi_saidi_service.calculer_perimetre(db, service_ids, per.debut, per.fin)
        nb_actives = await _count_interruptions_for_scope(db, scope, user, statut="en_cours")
        nb_periode = await _count_interruptions_for_scope(db, scope, user, **bornes)
        cause_rows = await repo.aggregate_interruptions_by_cause(db, service_ids=service_ids, **bornes)
        cause_total = sum(r.nombre for r in cause_rows) or nb_periode or 1
        causes = [
            CauseRepartitionItemResponse(
                label=row.label,
                nombre=row.nombre,
                percent=round(row.nombre * 100.0 / cause_total, 1),
            )
            for row in cause_rows
        ]

        # Répartition par nature (format Tableau de Bord FIS)
        nature_rows = await repo.aggregate_interruptions_by_nature(db, service_ids=service_ids, **bornes)
        nature_total = sum(r.nombre for r in nature_rows) or nb_periode or 1
        natures = [
            NatureRepartitionItemResponse(
                code=row.code,
                libelle=row.libelle,
                nombre=row.nombre,
                end_kwh=round(row.end_mwh * 1000, 2),
                percent=round(row.nombre * 100.0 / nature_total, 1),
            )
            for row in nature_rows
        ]

        nature_service = build_nature_service_repartition(
            await repo.aggregate_interruptions_by_nature_and_service(db, service_ids=service_ids, **bornes)
        )

        payload = TableauDeBordResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=per.annee,
            mois=per.mois,
            granularite=per.granularite,
            debut=per.debut.date(),
            fin=(per.fin - timedelta(days=1)).date(),
            end_mois=round(end_mwh, 4),
            saifi=calcul.saifi,
            saidi=calcul.saidi,
            nb_interruptions_actives=nb_actives,
            nb_interruptions_mois=nb_periode,
            causes_repartition=causes,
            natures_repartition=natures,
            nature_service=nature_service,
        )
        return payload.model_dump(mode="json")

    # Service, ou journée en cours : pas de cache (les interruptions du jour bougent)
    if scope.niveau == "service" or (per.granularite == "jour" and per.fin > datetime.now()):
        return TableauDeBordResponse.model_validate(await _loader())

    type_cache, annee_cache, mois_cache = per.cle_cache
    cache_key = build_cache_key(type_cache, scope.cache_region_id, annee_cache, mois_cache)
    cached = await get_cached(redis, cache_key)
    if not isinstance(cached, dict) or "granularite" not in cached:
        cached = await _loader()
        await set_cached(redis, cache_key, cached)
    return TableauDeBordResponse.model_validate(cached)


_HISTORIQUE_TYPES = frozenset({"end", "saifi", "saidi"})
_MAX_HISTORIQUE_ANNEES = 3


def _iter_months_back(annees: int, *, end: datetime | None = None) -> list[tuple[int, int]]:
    ref = end or datetime.now()
    year, month = ref.year, ref.month
    total_months = annees * 12
    points: list[tuple[int, int]] = []
    for _ in range(total_months):
        points.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    points.reverse()
    return points


async def _historique_valeur_for_month(
    db: AsyncSession,
    *,
    indicateur_type: str,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> float:
    if indicateur_type == "end":
        rows = await repo.aggregate_end_by_services(db, service_ids=service_ids, annee=annee, mois=mois)
        return sum(r.end_mwh for r in rows)

    debut, fin = _bornes_mois(annee, mois)
    calcul = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut, fin)
    return calcul.saifi if indicateur_type == "saifi" else calcul.saidi


async def get_historique(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    indicateur_type: str,
    annees: int = 1,
    region_id: int | None = None,
    fin: str | None = None,
) -> HistoriqueResponse:
    """Série mensuelle sur `annees` ans, se terminant au mois `fin` (AAAA-MM, défaut : mois courant)."""
    if indicateur_type not in _HISTORIQUE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"type invalide : '{indicateur_type}'. Valeurs acceptées : end, saifi, saidi",
            },
        )

    clamped_annees = max(1, min(annees, _MAX_HISTORIQUE_ANNEES))
    scope = _resolve_scope(user, region_id=region_id)
    end: datetime | None = None
    if fin:
        try:
            end = datetime.strptime(fin, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"status": "error", "data": None, "error": "fin invalide : format AAAA-MM attendu"},
            ) from None
        if end > datetime.now():
            end = None  # mois futur : on s'arrête au mois courant
            fin = None

    async def _loader() -> dict:
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        service_ids = await _load_service_ids(db, scope)
        mois_serie = _iter_months_back(clamped_annees, end=end)
        serie = (
            await saifi_saidi_service.serie_perimetre(db, service_ids, mois_serie) if indicateur_type != "end" else {}
        )
        points: list[HistoriquePointResponse] = []
        for point_annee, point_mois in mois_serie:
            if indicateur_type == "end":
                valeur = await _historique_valeur_for_month(
                    db,
                    indicateur_type=indicateur_type,
                    service_ids=service_ids,
                    annee=point_annee,
                    mois=point_mois,
                )
            else:
                calcul = serie[(point_annee, point_mois)]
                valeur = calcul.saifi if indicateur_type == "saifi" else calcul.saidi
            points.append(HistoriquePointResponse(annee=point_annee, mois=point_mois, valeur=valeur))
        payload = HistoriqueResponse(
            type=indicateur_type,
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annees=clamped_annees,
            points=points,
        )
        return payload.model_dump()

    if scope.niveau == "service":
        return HistoriqueResponse.model_validate(await _loader())

    cached = await get_or_load_historique(
        redis,
        indicateur_type,
        scope.cache_region_id,
        clamped_annees,
        _loader,
        fin=fin,
    )
    return HistoriqueResponse.model_validate(cached)


_DEFAULT_TOP_FEEDERS_LIMIT = 10
_MAX_TOP_FEEDERS_LIMIT = 50


async def get_top_feeders(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    periode: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
    region_id: int | None = None,
    limit: int = _DEFAULT_TOP_FEEDERS_LIMIT,
) -> TopFeedersResponse:
    resolved_annee, resolved_mois = _resolve_period(periode=periode, annee=annee, mois=mois)
    clamped_limit = max(1, min(limit, _MAX_TOP_FEEDERS_LIMIT))
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        service_ids = await _load_service_ids(db, scope)
        rows = await repo.aggregate_end_by_feeders(
            db,
            service_ids=service_ids,
            annee=resolved_annee,
            mois=resolved_mois,
            limit=clamped_limit,
        )
        items = [
            TopFeederItemResponse(
                feeder_id=row.feeder_id,
                code=row.code,
                libelle=row.libelle,
                service_id=row.service_id,
                end_mwh=row.end_mwh,
                nombre_interruptions=row.nombre_interruptions,
            )
            for row in rows
        ]
        payload = TopFeedersResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=resolved_annee,
            mois=resolved_mois,
            limit=clamped_limit,
            items=items,
        )
        return payload.model_dump()

    if scope.niveau == "service":
        return TopFeedersResponse.model_validate(await _loader())

    cached = await get_or_load_top_feeders(
        redis,
        scope.cache_region_id,
        resolved_annee,
        resolved_mois,
        clamped_limit,
        _loader,
    )
    return TopFeedersResponse.model_validate(cached)


_MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def periodes_synthese(aujourd_hui: date) -> list[tuple[str, str, datetime, datetime]]:
    """(clé, libellé, début, fin exclue) : semaine passée, mois en cours, année en cours.

    Semaine d'exploitation SENELEC : samedi → vendredi (rapport hebdomadaire DD) ; la semaine
    passée est la dernière semaine complète. Les cumuls vont jusqu'à aujourd'hui inclus.
    """
    jour = datetime(aujourd_hui.year, aujourd_hui.month, aujourd_hui.day)
    fin_semaine = jour - timedelta(days=(aujourd_hui.weekday() - 5) % 7)  # dernier samedi ≤ aujourd'hui
    debut_semaine = fin_semaine - timedelta(days=7)
    demain = jour + timedelta(days=1)
    dernier = fin_semaine - timedelta(days=1)
    return [
        (
            "semaine",
            f"Semaine passée ({debut_semaine:%d/%m} → {dernier:%d/%m})",
            debut_semaine,
            fin_semaine,
        ),
        (
            "mois",
            f"Cumul {_MOIS_FR[aujourd_hui.month - 1]} {aujourd_hui.year}",
            datetime(jour.year, jour.month, 1),
            demain,
        ),
        ("annee", f"Cumul {aujourd_hui.year}", datetime(jour.year, 1, 1), demain),
    ]


async def get_synthese_saifi_saidi(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    region_id: int | None = None,
    aujourd_hui: date | None = None,
) -> SyntheseSaifiSaidiResponse:
    """SAIFI/SAIDI HTA, HTB et les deux confondus, sur la semaine passée, le mois et l'année.

    HTA : formule SENELEC du périmètre (``calculer_perimetre``). HTB : interruptions transport
    et OMVG, clients touchés saisis, rapportés à la même base clients (vue nationale seule).
    Total : somme des numérateurs sur la même base clients.
    """
    jour = aujourd_hui or date.today()
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        service_ids = await _load_service_ids(db, scope)
        if scope.niveau == "service" and scope.scope_id is not None:
            check_service_scope(user, scope.scope_id)
        periodes: list[SyntheseSaifiSaidiPeriode] = []
        reference = 0
        for cle, libelle, debut, fin in periodes_synthese(jour):
            hta = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut, fin, today=jour)
            reference = hta.total_clients_reference
            valeurs_hta = SaifiSaidiValeurs(
                saifi=hta.saifi, saidi=hta.saidi, nombre_interruptions=hta.nombre_interruptions
            )
            htb = total = None
            if scope.niveau == "national":
                trans = await pilotage_repository.sommer_clients_transport(db, debut, fin)
                htb = SaifiSaidiValeurs(
                    saifi=float(saifi_saidi_service.calcul_saifi(trans.clients, reference)),
                    saidi=float(saifi_saidi_service.calcul_saidi(trans.client_heures, reference)),
                    nombre_interruptions=trans.nombre,
                )
                total = SaifiSaidiValeurs(
                    saifi=round(hta.saifi + htb.saifi, 6),
                    saidi=round(hta.saidi + htb.saidi, 6),
                    nombre_interruptions=hta.nombre_interruptions + trans.nombre,
                )
            periodes.append(
                SyntheseSaifiSaidiPeriode(
                    cle=cle,  # type: ignore[arg-type]
                    libelle=libelle,
                    debut=debut.date(),
                    fin=(fin - timedelta(days=1)).date(),
                    hta=valeurs_hta,
                    htb=htb,
                    total=total,
                )
            )
        return SyntheseSaifiSaidiResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            total_clients_reference=reference,
            periodes=periodes,
        ).model_dump(mode="json")

    if scope.niveau == "service":
        return SyntheseSaifiSaidiResponse.model_validate(await _loader())
    cache_key = build_cache_key("synthese-saifi-saidi", scope.cache_region_id, jour.year, int(jour.strftime("%m%d")))
    cached = await get_cached(redis, cache_key)
    if not isinstance(cached, dict) or "periodes" not in cached:
        cached = await _loader()
        await set_cached(redis, cache_key, cached)
    return SyntheseSaifiSaidiResponse.model_validate(cached)
