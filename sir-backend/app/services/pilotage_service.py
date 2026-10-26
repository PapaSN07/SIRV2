"""Pilotage des indicateurs : objectifs, défauts aux 100 km, carte et tendance."""

from calendar import monthrange
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import indicateurs_repository as indicateurs_repo
from app.repositories import pilotage_repository as repo
from app.schemas.indicateurs import (
    Defauts100KmResponse,
    IndicateurSuiviResponse,
    ObjectifsPilotageUpdate,
    PilotageResponse,
    PosteOuvertResponse,
    TendancePointResponse,
    TendanceResponse,
    TopFeederItemResponse,
    TopPosteResponse,
    ZonePerturbeeResponse,
)
from app.services.indicateurs_cache_service import get_cached, set_cached
from app.services.indicateurs_service import _load_service_ids, _resolve_period, _resolve_scope

_EDITEURS = frozenset({"ADMIN_SCR", "ADMIN_SAQS"})
_CODES = {
    "end_mwh": "END",
    "saifi": "SAIFI",
    "saidi": "SAIDI",
    "defauts_100km": "DEFAUTS_100KM",
}


def defauts_pour_100_km(nombre: int, longueur_km: float) -> float | None:
    """Nombre de défauts rapporté à 100 km de réseau."""
    if longueur_km <= 0:
        return None
    return round(nombre / longueur_km * 100, 2)


def jours_de_annee(annee: int) -> int:
    return 366 if annee % 4 == 0 and (annee % 100 != 0 or annee % 400 == 0) else 365


def decouper_objectif(
    annuel: float | None,
    jours_ecoules: int,
    jours_annee: int,
) -> tuple[float | None, float | None]:
    """Retourne (objectif du jour, objectif cumulé depuis le 1er janvier)."""
    if annuel is None or jours_annee <= 0:
        return None, None
    journalier = annuel / jours_annee
    cumul = annuel * jours_ecoules / jours_annee
    return journalier, cumul


def taux_realisation(realise: float | None, objectif: float | None) -> float | None:
    """Part de l'objectif déjà consommée. Au-dessus de 100, l'objectif est dépassé."""
    if realise is None or objectif is None or objectif == 0:
        return None
    return round(realise / objectif * 100, 1)


def tendance_lineaire(values: list[float]) -> tuple[float, float, str]:
    """Pente et ordonnée à l'origine d'une droite, et le sens de la série."""
    count = len(values)
    if count == 0:
        return 0.0, 0.0, "stable"
    if count == 1:
        return 0.0, values[0], "stable"
    mean_x = (count - 1) / 2
    mean_y = sum(values) / count
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
    denominator = sum((index - mean_x) ** 2 for index in range(count)) or 1.0
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    scale = max(abs(mean_y), 1.0)
    if slope > 0.02 * scale:
        sens = "hausse"
    elif slope < -0.02 * scale:
        sens = "baisse"
    else:
        sens = "stable"
    return slope, intercept, sens


def _fmt(value: float, digits: int = 1) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", " ")


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _round(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _ecart(realise: float | None, objectif: float | None) -> float | None:
    if realise is None or objectif is None:
        return None
    return round(realise - objectif, 2)


def _month_bounds(annee: int, mois: int) -> tuple[datetime, datetime]:
    start = datetime(annee, mois, 1)
    if mois == 12:
        return start, datetime(annee + 1, 1, 1)
    return start, datetime(annee, mois + 1, 1)


def _shift_month(annee: int, mois: int, delta: int) -> tuple[int, int]:
    index = annee * 12 + (mois - 1) + delta
    return index // 12, index % 12 + 1


def _peut_modifier(user: Utilisateur) -> bool:
    if is_superadmin(user):
        return True
    return any(ur.role.nom in _EDITEURS for ur in user.user_roles)


def _suivi(
    *,
    code: str,
    libelle: str,
    unite: str,
    annuel: float | None,
    realise_jour: float | None,
    realise_cumul: float | None,
    note_jour: str,
    note_cumul: str,
    jours_ecoules: int,
    jours_annee: int,
    digits: int,
) -> IndicateurSuiviResponse:
    journalier, cumul = decouper_objectif(annuel, jours_ecoules, jours_annee)
    return IndicateurSuiviResponse(
        code=code,
        libelle=libelle,
        unite=unite,
        objectif_annuel=_round(annuel, digits),
        objectif_journalier=_round(journalier, digits),
        realise_jour=_round(realise_jour, digits),
        ecart_jour=_ecart(realise_jour, journalier),
        taux_jour=taux_realisation(realise_jour, journalier),
        note_jour=note_jour,
        objectif_cumul=_round(cumul, digits),
        realise_cumul=_round(realise_cumul, digits),
        ecart_cumul=_ecart(realise_cumul, cumul),
        taux_cumul=taux_realisation(realise_cumul, cumul),
        note_cumul=note_cumul,
    )


async def _region_objectif(
    db: AsyncSession,
    scope_niveau: str,
    scope_id: int | None,
) -> int | None:
    if scope_niveau == "region":
        return scope_id
    if scope_niveau == "service" and scope_id is not None:
        return await repo.region_id_du_service(db, scope_id)
    return None


async def _objectifs_map(
    db: AsyncSession,
    annee: int,
    region_id: int | None,
) -> dict[str, float]:
    rows = await repo.list_objectifs(db, annee, region_id)
    if not rows and region_id is not None:
        rows = await repo.list_objectifs(db, annee, None)
    return {row.code: float(row.valeur_annuelle) for row in rows}


async def _build_pilotage(
    db: AsyncSession,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None,
) -> PilotageResponse:
    scope = _resolve_scope(user, region_id=region_id)
    service_ids = await _load_service_ids(db, scope)
    today = date.today()
    annee_objectif = today.year
    jours_annee = jours_de_annee(annee_objectif)
    jours_ecoules = today.timetuple().tm_yday
    debut_jour = datetime(today.year, today.month, today.day)
    fin_jour = debut_jour + timedelta(days=1)
    debut_annee = datetime(annee_objectif, 1, 1)
    debut_mois, fin_mois = _month_bounds(annee, mois)

    longueur = await repo.longueur_reseau_km(db, service_ids)
    defauts_mois = await repo.compter_defauts(db, service_ids, debut_mois, fin_mois)
    defauts_jour = await repo.compter_defauts(db, service_ids, debut_jour, fin_jour)
    defauts_cumul = await repo.compter_defauts(db, service_ids, debut_annee, fin_jour)
    valeur_mois = defauts_pour_100_km(defauts_mois, longueur)
    valeur_jour = defauts_pour_100_km(defauts_jour, longueur)
    valeur_cumul = defauts_pour_100_km(defauts_cumul, longueur)

    end_jour = await repo.sommer_end_mwh(db, service_ids, debut_jour, fin_jour)
    end_cumul = await repo.sommer_end_mwh(db, service_ids, debut_annee, fin_jour)
    clients_jour = await repo.sommer_clients(db, service_ids, debut_jour, fin_jour)
    clients_cumul = await repo.sommer_clients(db, service_ids, debut_annee, fin_jour)
    reference = await repo.clients_reference(db, service_ids, today.year, today.month)

    def _ratio(numerateur: float) -> float | None:
        if reference <= 0:
            return None
        return numerateur / reference

    saifi_jour = _ratio(clients_jour.clients)
    saidi_jour = _ratio(clients_jour.client_minutes)
    saifi_cumul = _ratio(clients_cumul.clients)
    saidi_cumul = _ratio(clients_cumul.client_minutes)

    region_objectif = await _region_objectif(db, scope.niveau, scope.scope_id)
    objectifs = await _objectifs_map(db, annee_objectif, region_objectif)
    km_label = _fmt(longueur, 1)

    indicateurs = [
        _suivi(
            code="END",
            libelle="END",
            unite="MWh",
            annuel=objectifs.get("END"),
            realise_jour=end_jour,
            realise_cumul=end_cumul,
            note_jour=f"{_fmt(end_jour, 2)} MWh remis aujourd'hui",
            note_cumul=f"{_fmt(end_cumul, 2)} MWh depuis janvier",
            jours_ecoules=jours_ecoules,
            jours_annee=jours_annee,
            digits=2,
        ),
        _suivi(
            code="SAIFI",
            libelle="SAIFI",
            unite="",
            annuel=objectifs.get("SAIFI"),
            realise_jour=saifi_jour,
            realise_cumul=saifi_cumul,
            note_jour=f"{_fmt_int(clients_jour.clients)} clients / {_fmt_int(reference)}",
            note_cumul=f"{_fmt_int(clients_cumul.clients)} clients / {_fmt_int(reference)}",
            jours_ecoules=jours_ecoules,
            jours_annee=jours_annee,
            digits=3,
        ),
        _suivi(
            code="SAIDI",
            libelle="SAIDI",
            unite="min",
            annuel=objectifs.get("SAIDI"),
            realise_jour=saidi_jour,
            realise_cumul=saidi_cumul,
            note_jour=f"{_fmt(clients_jour.client_minutes, 0)} clients × min",
            note_cumul=f"{_fmt(clients_cumul.client_minutes, 0)} clients × min",
            jours_ecoules=jours_ecoules,
            jours_annee=jours_annee,
            digits=1,
        ),
        _suivi(
            code="DEFAUTS_100KM",
            libelle="Défauts aux 100 km",
            unite="/100 km",
            annuel=objectifs.get("DEFAUTS_100KM"),
            realise_jour=valeur_jour,
            realise_cumul=valeur_cumul,
            note_jour=f"{_fmt_int(defauts_jour)} défauts sur {km_label} km",
            note_cumul=f"{_fmt_int(defauts_cumul)} défauts sur {km_label} km",
            jours_ecoules=jours_ecoules,
            jours_annee=jours_annee,
            digits=2,
        ),
    ]

    ouverts = await repo.list_postes_impactes(db, service_ids, debut_mois, fin_mois)
    noms = [item.libelle for item in ouverts] + [item.code for item in ouverts]
    coords = await repo.coords_par_nom(db, noms)
    postes_ouverts = []
    for item in ouverts:
        point = coords.get(item.libelle.casefold()) or coords.get(item.code.casefold())
        postes_ouverts.append(
            PosteOuvertResponse(
                poste_id=item.poste_id,
                code=item.code,
                libelle=item.libelle,
                interruption_id=item.interruption_id,
                numero_interruption=item.numero_interruption,
                date_apparition=item.date_apparition,
                feeder_libelle=item.feeder_libelle,
                service_libelle=item.service_libelle,
                sans_remise=item.sans_remise,
                longitude=point[0] if point else None,
                latitude=point[1] if point else None,
            )
        )

    top_poste_rows = await repo.top_postes(db, service_ids, debut_mois, fin_mois, 10)
    feeder_rows = await indicateurs_repo.aggregate_end_by_feeders(
        db,
        service_ids=service_ids,
        annee=annee,
        mois=mois,
        limit=10,
    )
    par_region = scope.niveau == "national"
    zone_rows = await repo.zones_perturbees(
        db,
        service_ids,
        debut_mois,
        fin_mois,
        par_region=par_region,
    )
    refs = await repo.clients_reference_par_zone(
        db,
        service_ids,
        annee,
        mois,
        par_region=par_region,
    )
    zones = []
    for zone in zone_rows:
        ref = refs.get(zone.zone_id, 0)
        zones.append(
            ZonePerturbeeResponse(
                zone_id=zone.zone_id,
                code=zone.code,
                libelle=zone.libelle,
                nombre=zone.nombre,
                end_mwh=round(zone.end_mwh, 3),
                saifi=round(zone.clients / ref, 3) if ref else None,
                saidi=round(zone.client_minutes / ref, 1) if ref else None,
            )
        )

    return PilotageResponse(
        niveau=scope.niveau,
        scope_id=scope.scope_id,
        annee=annee,
        mois=mois,
        annee_objectif=annee_objectif,
        jour=today.isoformat(),
        jours_ecoules=jours_ecoules,
        jours_annee=jours_annee,
        peut_modifier_objectifs=_peut_modifier(user),
        defauts_100km_mois=Defauts100KmResponse(
            nombre_defauts=defauts_mois,
            longueur_km=round(longueur, 1),
            valeur=valeur_mois,
        ),
        indicateurs=indicateurs,
        postes_ouverts=postes_ouverts,
        top_postes=[
            TopPosteResponse(
                poste_id=row.poste_id,
                code=row.code,
                libelle=row.libelle,
                nombre=row.nombre,
                clients=row.clients,
                end_mwh=round(row.end_mwh, 3),
            )
            for row in top_poste_rows
        ],
        top_feeders=[
            TopFeederItemResponse(
                feeder_id=row.feeder_id,
                code=row.code,
                libelle=row.libelle,
                service_id=row.service_id,
                end_mwh=row.end_mwh,
                nombre_interruptions=row.nombre_interruptions,
            )
            for row in feeder_rows
        ],
        zone_niveau="region" if par_region else "service",
        zones=zones,
    )


def _cache_key(region_id: int, annee: int, mois: int, jour: date) -> str:
    return f"indicateurs:pilotage:{region_id}:{annee}:{mois}:{jour.isoformat()}"


async def get_pilotage(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    periode: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
    region_id: int | None = None,
) -> PilotageResponse:
    resolved_annee, resolved_mois = _resolve_period(periode=periode, annee=annee, mois=mois)
    scope = _resolve_scope(user, region_id=region_id)
    key = _cache_key(scope.cache_region_id, resolved_annee, resolved_mois, date.today())
    if scope.niveau != "service":
        cached = await get_cached(redis, key)
        if isinstance(cached, dict) and cached.get("indicateurs"):
            payload = PilotageResponse.model_validate(cached)
            payload.peut_modifier_objectifs = _peut_modifier(user)
            return payload
    payload = await _build_pilotage(
        db,
        user,
        annee=resolved_annee,
        mois=resolved_mois,
        region_id=region_id,
    )
    if scope.niveau != "service":
        await set_cached(redis, key, payload.model_dump(mode="json"))
    return payload


async def update_objectifs(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    body: ObjectifsPilotageUpdate,
    *,
    region_id: int | None = None,
) -> PilotageResponse:
    if not _peut_modifier(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Seuls les profils nationaux peuvent enregistrer les objectifs",
            },
        )
    valeurs = {
        _CODES[field]: getattr(body, field)
        for field in _CODES
        if getattr(body, field) is not None
    }
    if not valeurs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Indiquez au moins un objectif annuel",
            },
        )
    scope = _resolve_scope(user, region_id=region_id)
    cible = await _region_objectif(db, scope.niveau, scope.scope_id)
    for code, valeur in valeurs.items():
        await repo.upsert_objectif(
            db,
            annee=body.annee,
            code=code,
            valeur_annuelle=float(valeur),
            region_id=cible,
        )
    await db.flush()
    for mois in range(1, 13):
        await redis.delete(_cache_key(scope.cache_region_id, body.annee, mois, date.today()))
    return await _build_pilotage(
        db,
        user,
        annee=body.annee,
        mois=date.today().month,
        region_id=region_id,
    )


async def get_tendance(
    db: AsyncSession,
    user: Utilisateur,
    *,
    cible: str,
    cible_id: int,
    annees: int,
    region_id: int | None = None,
) -> TendanceResponse:
    if cible not in {"feeder", "poste"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "data": None, "error": "La cible doit être feeder ou poste"},
        )
    scope = _resolve_scope(user, region_id=region_id)
    service_ids = await _load_service_ids(db, scope)
    identite = await repo.libelle_cible(db, cible, cible_id)
    if identite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Ouvrage introuvable"},
        )
    code, libelle, service_id = identite
    if scope.niveau != "national" and service_id not in service_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Ouvrage introuvable"},
        )

    clamped = max(2, min(annees, 3))
    today = date.today()
    debut_annee, debut_mois = _shift_month(today.year, today.month, -(clamped * 12 - 1))
    debut = datetime(debut_annee, debut_mois, 1)
    fin = datetime(today.year, today.month, monthrange(today.year, today.month)[1]) + timedelta(days=1)
    rows = await repo.serie_mensuelle(
        db, cible=cible, cible_id=cible_id, debut=debut, fin=fin
    )
    by_key = {(row.annee, row.mois): row for row in rows}
    points: list[TendancePointResponse] = []
    nombres: list[float] = []
    cursor_year, cursor_month = debut_annee, debut_mois
    while (cursor_year, cursor_month) <= (today.year, today.month):
        row = by_key.get((cursor_year, cursor_month))
        nombre = row.nombre if row else 0
        end_mwh = row.end_mwh if row else 0.0
        nombres.append(float(nombre))
        points.append(
            TendancePointResponse(
                annee=cursor_year,
                mois=cursor_month,
                nombre=nombre,
                end_kwh=round(end_mwh * 1000, 1),
                tendance_nombre=0,
            )
        )
        cursor_year, cursor_month = _shift_month(cursor_year, cursor_month, 1)

    slope, intercept, sens = tendance_lineaire(nombres)
    for index, point in enumerate(points):
        point.tendance_nombre = round(max(0.0, intercept + slope * index), 2)

    previsions: list[TendancePointResponse] = []
    next_year, next_month = _shift_month(today.year, today.month, 1)
    for offset in range(3):
        year, month = _shift_month(next_year, next_month, offset)
        forecast = max(0.0, intercept + slope * (len(points) + offset))
        previsions.append(
            TendancePointResponse(
                annee=year,
                mois=month,
                nombre=int(round(forecast)),
                end_kwh=0,
                tendance_nombre=round(forecast, 2),
            )
        )

    ouvrage = "feeder" if cible == "feeder" else "poste"
    sens_texte = {"hausse": "en hausse", "baisse": "en baisse", "stable": "stable"}[sens]
    pente = f"{slope:+.2f}".replace(".", ",")
    lecture = (
        f"Sur {clamped} ans, les interruptions du {ouvrage} {libelle} sont {sens_texte} "
        f"(environ {pente} interruption par mois)."
    )
    return TendanceResponse(
        cible=cible,
        cible_id=cible_id,
        code=code,
        libelle=libelle,
        annees=clamped,
        sens=sens,
        pente_mensuelle=round(slope, 3),
        lecture=lecture,
        points=points,
        previsions=previsions,
    )
