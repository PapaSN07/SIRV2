"""Service métier — lecture indicateurs END / SAIFI / SAIDI (Sprint 5.4+)."""

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_region_scope, check_service_scope
from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import indicateurs_repository as repo
from app.schemas.common import PaginatedResponse
from app.schemas.indicateurs import (
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
    if scope.service_ids:
        return scope.service_ids
    if scope.niveau == "region" and scope.scope_id is not None:
        return await repo.list_service_ids_for_region(db, scope.scope_id)
    return await repo.list_all_service_ids(db)


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
    return response_type.model_validate(
        await get_or_load(redis, indicateur_type, cache_region_id, annee, mois, loader)
    )


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
        rows = await repo.aggregate_end_by_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        result = _aggregate_end_rows(rows, scope=scope, annee=annee, mois=mois)
        return result.model_dump()

    response = await _load_cached(
        redis, "end", scope.cache_region_id, annee, mois, scope, _loader, EndIndicateurResponse
    )

    if include_services and scope.niveau != "service":
        service_ids = await _load_service_ids(db, scope)
        rows = await repo.aggregate_end_by_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
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
        records = await repo.list_saifi_saidi_for_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        saifi, _, nb, total_clients = saifi_saidi_service.aggregate_saifi_saidi_weighted(
            records
        )
        aggregate = SaifiSaidiAggregateResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=annee,
            mois=mois,
            saifi=float(saifi),
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
        records = await repo.list_saifi_saidi_for_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
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
        records = await repo.list_saifi_saidi_for_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        _, saidi, nb, total_clients = saifi_saidi_service.aggregate_saifi_saidi_weighted(
            records
        )
        aggregate = SaifiSaidiAggregateResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=annee,
            mois=mois,
            saifi=0.0,
            saidi=float(saidi),
            nombre_interruptions=nb,
            total_clients_reference=total_clients,
        )
        return SaidiIndicateurResponse(aggregate=aggregate, services=None).model_dump()

    response = await _load_cached(
        redis, "saidi", scope.cache_region_id, annee, mois, scope, _loader, SaidiIndicateurResponse
    )

    if include_services and scope.niveau != "service":
        service_ids = await _load_service_ids(db, scope)
        records = await repo.list_saifi_saidi_for_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
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
        )

    if "transport" in directions and scope.niveau == "national":
        total += await repo.count_transport_interruptions(
            db,
            statut=statut,
            annee=annee,
            mois=mois,
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
            cellules.append(
                NatureServiceCellResponse(nombre=int(nombre), end_kwh=round(float(end_mwh) * 1000, 2))
            )
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
    resolved_annee, resolved_mois = _resolve_period(
        periode=periode, annee=annee, mois=mois
    )
    scope = _resolve_scope(user, region_id=region_id)

    async def _loader() -> dict:
        end = await get_end(
            db, redis, user, annee=resolved_annee, mois=resolved_mois, region_id=region_id
        )
        saifi = await get_saifi(
            db, redis, user, annee=resolved_annee, mois=resolved_mois, region_id=region_id
        )
        saidi = await get_saidi(
            db, redis, user, annee=resolved_annee, mois=resolved_mois, region_id=region_id
        )
        nb_actives = await _count_interruptions_for_scope(
            db, scope, user, statut="en_cours"
        )
        nb_mois = await _count_interruptions_for_scope(
            db,
            scope,
            user,
            annee=resolved_annee,
            mois=resolved_mois,
        )
        service_ids = await _load_service_ids(db, scope)
        cause_rows = await repo.aggregate_interruptions_by_cause(
            db,
            service_ids=service_ids,
            annee=resolved_annee,
            mois=resolved_mois,
        )
        cause_total = sum(r.nombre for r in cause_rows) or nb_mois or 1
        causes = [
            CauseRepartitionItemResponse(
                label=row.label,
                nombre=row.nombre,
                percent=round(row.nombre * 100.0 / cause_total, 1),
            )
            for row in cause_rows
        ]

        # Répartition par nature (format Tableau de Bord FIS)
        nature_rows = await repo.aggregate_interruptions_by_nature(
            db,
            service_ids=service_ids,
            annee=resolved_annee,
            mois=resolved_mois,
        )
        nature_total = sum(r.nombre for r in nature_rows) or nb_mois or 1
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
            await repo.aggregate_interruptions_by_nature_and_service(
                db,
                service_ids=service_ids,
                annee=resolved_annee,
                mois=resolved_mois,
            )
        )

        payload = TableauDeBordResponse(
            niveau=scope.niveau,
            scope_id=scope.scope_id,
            annee=resolved_annee,
            mois=resolved_mois,
            end_mois=end.aggregate.end_mwh,
            saifi=saifi.aggregate.saifi,
            saidi=saidi.aggregate.saidi,
            nb_interruptions_actives=nb_actives,
            nb_interruptions_mois=nb_mois,
            causes_repartition=causes,
            natures_repartition=natures,
            nature_service=nature_service,
        )
        return payload.model_dump()

    if scope.niveau == "service":
        return TableauDeBordResponse.model_validate(await _loader())

    cache_key = build_cache_key(
        "tableau-de-bord",
        scope.cache_region_id,
        resolved_annee,
        resolved_mois,
    )
    cached = await get_cached(redis, cache_key)
    if not isinstance(cached, dict) or "nature_service" not in cached:
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
        rows = await repo.aggregate_end_by_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        return sum(r.end_mwh for r in rows)

    records = await repo.list_saifi_saidi_for_services(
        db, service_ids=service_ids, annee=annee, mois=mois
    )
    saifi, saidi, _, _ = saifi_saidi_service.aggregate_saifi_saidi_weighted(records)
    if indicateur_type == "saifi":
        return float(saifi)
    return float(saidi)


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
        points: list[HistoriquePointResponse] = []
        for point_annee, point_mois in _iter_months_back(clamped_annees, end=end):
            valeur = await _historique_valeur_for_month(
                db,
                indicateur_type=indicateur_type,
                service_ids=service_ids,
                annee=point_annee,
                mois=point_mois,
            )
            points.append(
                HistoriquePointResponse(annee=point_annee, mois=point_mois, valeur=valeur)
            )
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
    resolved_annee, resolved_mois = _resolve_period(
        periode=periode, annee=annee, mois=mois
    )
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
