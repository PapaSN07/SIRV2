"""Menu « Suivi incidents » : résolution des filtres communs aux onglets.

Périmètre : même règle que les indicateurs (``indicateurs_service._resolve_scope``) — rôles
nationaux libres, BCC / BRC limités à leur région (``scope_service_id`` = région), SUPERVISEUR
limité à son service. Les valeurs imposées par le rôle remplacent celles de la requête.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import suivi_incidents_repository as repo
from app.schemas.suivi_incidents import (
    CategorieNature,
    ClassementSuivi,
    FiltresIncidents,
    FiltresResolus,
    KpiSuivi,
    LigneClassement,
    PeriodeSuivi,
    PerimetreSuivi,
    RepartitionNature,
    RepartitionReseau,
    SemaineSenelecSchema,
    VueEnsemble,
)
from app.services import indicateurs_cache_service as cache
from app.services import rapport_hebdo_dd_service as hebdo
from app.services.indicateurs_service import _resolve_scope
from app.services.periodes import periode_precedente, semaine_senelec, semaine_senelec_passee
from app.services.reseau_htb import est_cause_htb


def _hors_perimetre(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"status": "error", "data": None, "error": message},
    )


def _invalide(erreur: ValidationError) -> HTTPException:
    messages = "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in erreur.errors())
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"status": "error", "data": None, "error": messages or "Filtres invalides"},
    )


def libelle_periode(debut: date, fin: date) -> str:
    """« S47 · 14/11 → 20/11/2026 » pour une semaine SENELEC, « 01/11 → 25/11/2026 » sinon."""
    semaine = semaine_senelec(debut)
    plage = f"{debut:%d/%m} → {fin:%d/%m/%Y}"
    if semaine.debut == debut and semaine.fin == fin:
        return f"S{semaine.numero} · {plage}"
    return plage


def resoudre_filtres(
    user: Utilisateur,
    bruts: dict[str, Any],
    aujourd_hui: date | None = None,
) -> FiltresResolus:
    """Filtres complétés : période par défaut (semaine SENELEC passée), périmètre du rôle."""
    valeurs = {cle: v for cle, v in bruts.items() if v is not None}
    if "debut" not in valeurs or "fin" not in valeurs:
        defaut = semaine_senelec_passee(aujourd_hui or date.today())
        valeurs.setdefault("debut", defaut.debut)
        valeurs.setdefault("fin", defaut.fin)
    try:
        filtres = FiltresIncidents.model_validate(valeurs)
    except ValidationError as erreur:
        raise _invalide(erreur) from erreur

    # Lève 403 hors périmètre (autre région pour un BCC / BRC, région pour un SUPERVISEUR)
    scope = _resolve_scope(user, region_id=filtres.region_id)
    perimetre = PerimetreSuivi(niveau=scope.niveau, scope_id=scope.scope_id)  # type: ignore[arg-type]
    roles = {ur.role.nom for ur in user.user_roles}
    national = is_superadmin(user) or bool(roles & {"ADMIN_SCR", "ADMIN_SAQS"})
    # Région imposée seulement à un compte régional (pas à un national qui choisit une région)
    if scope.niveau == "region" and roles & {"BCC", "BRC"} and not national:
        filtres = filtres.model_copy(update={"region_id": scope.scope_id})
        perimetre.region_verrouillee = True
    elif scope.niveau == "service":
        if filtres.service_id is not None and filtres.service_id != scope.scope_id:
            raise _hors_perimetre("Hors périmètre : service non autorisé pour votre compte")
        filtres = filtres.model_copy(update={"service_id": scope.scope_id})
        perimetre.service_verrouille = True

    semaine = semaine_senelec(filtres.debut)
    est_semaine = semaine.debut == filtres.debut and semaine.fin == filtres.fin
    return FiltresResolus(
        filtres=filtres,
        semaine=SemaineSenelecSchema(**semaine.__dict__) if est_semaine else None,
        libelle_periode=libelle_periode(filtres.debut, filtres.fin),
        perimetre=perimetre,
    )


# ── Onglet Vue d'ensemble ─────────────────────────────────────────────────────────────────

CATEGORIES_NATURE: tuple[tuple[CategorieNature, str], ...] = (
    ("incident", "Incidents"),
    ("delestage", "Délestages"),
    ("travaux", "Travaux"),
    ("autre", "Autres coupures"),
)
# Regroupement des catégories du rapport hebdo DD (docs/fusion_suivi_incidents.md §8)
_DEPUIS_HEBDO: dict[str, CategorieNature] = {
    hebdo.PERMANENT: "incident",
    hebdo.SEMI_PERMANENT: "incident",
    hebdo.FUGITIF: "incident",
    hebdo.DELESTAGE_HTA: "delestage",
    hebdo.HTB_DELESTAGE: "delestage",
    hebdo.TRAVAUX_HTA: "travaux",
}
NIVEAUX_CLASSEMENT = ("service", "poste_source", "feeder")
LIMITE_MAX_CLASSEMENT = 50
NON_RENSEIGNE = "Non renseigné"


def categorie_nature(nature: str | None, cause: str | None) -> CategorieNature:
    """Incidents / Délestages / Travaux / Autres coupures, d'après la règle du rapport hebdo DD."""
    return _DEPUIS_HEBDO.get(hebdo.categorie_libelles(nature, cause), "autre")


def _heures(minutes: Any) -> float:
    return round(float(minutes or 0) / 60, 4)


def _mwh(valeur: Any) -> float:
    return round(float(valeur or 0), 4)


def _part(nombre: int, total: int) -> float:
    return nombre / total if total else 0.0


def _invalide_classement(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"status": "error", "data": None, "error": message},
    )


def _limite_classement(limite: int | str | None) -> int:
    """Limite du classement (défaut 10) ; texte non entier ou hors 1..50 → 422 enveloppé."""
    if limite is None or limite == "":
        return 10
    try:
        valeur = int(limite)
    except (TypeError, ValueError):
        valeur = 0
    if not 1 <= valeur <= LIMITE_MAX_CLASSEMENT:
        raise _invalide_classement(f"La limite doit être un entier compris entre 1 et {LIMITE_MAX_CLASSEMENT}")
    return valeur


def _cle_cache(endpoint: str, *parties: str) -> str:
    """``suivi:{endpoint}:{empreinte}`` : empreinte des filtres résolus (périmètre compris)."""
    empreinte = hashlib.sha256("|".join(parties).encode()).hexdigest()[:32]
    return f"suivi:{endpoint}:{empreinte}"


async def _kpi(db: AsyncSession, filtres: FiltresIncidents) -> KpiSuivi:
    agregats, postes = repo.requete_kpi(filtres)
    ligne = (await db.execute(agregats)).one()
    nombre_postes = (await db.execute(postes)).scalar_one()
    moyenne = ligne.duree_moyenne_minutes
    return KpiSuivi(
        nombre_interruptions=int(ligne.nombre or 0),
        duree_totale_heures=_heures(ligne.duree_minutes),
        duree_moyenne_minutes=None if moyenne is None else round(float(moyenne), 2),
        postes_touches=int(nombre_postes or 0),
        coupures_clients=int(ligne.coupures_clients or 0),
        end_mwh=_mwh(ligne.end_mwh),
    )


async def _natures_reseaux(
    db: AsyncSession, filtres: FiltresIncidents
) -> tuple[list[RepartitionNature], list[RepartitionReseau]]:
    """Une requête groupée par (nature, cause) ; catégorie et réseau déduits des libellés."""
    sommes: dict[str, list[float]] = {cle: [0, 0.0, 0.0] for cle, _ in CATEGORIES_NATURE}
    reseaux: dict[str, list[float]] = {"hta": [0, 0.0, 0.0], "htb": [0, 0.0, 0.0]}
    for ligne in (await db.execute(repo.requete_natures(filtres))).all():
        valeurs = (int(ligne.nombre or 0), float(ligne.duree_minutes or 0), float(ligne.end_mwh or 0))
        reseau = "htb" if est_cause_htb(ligne.cause) else "hta"
        for cible in (sommes[categorie_nature(ligne.nature, ligne.cause)], reseaux[reseau]):
            for i, v in enumerate(valeurs):
                cible[i] += v
    total = int(sum(v[0] for v in sommes.values()))
    natures = [
        RepartitionNature(
            categorie=cle,
            libelle=libelle,
            nombre=int(sommes[cle][0]),
            duree_heures=_heures(sommes[cle][1]),
            end_mwh=_mwh(sommes[cle][2]),
            part=_part(int(sommes[cle][0]), total),
        )
        for cle, libelle in CATEGORIES_NATURE
    ]
    hta, htb = reseaux["hta"], reseaux["htb"]
    lignes_reseau = [
        RepartitionReseau(reseau=cle, nombre=int(v[0]), duree_heures=_heures(v[1]), end_mwh=_mwh(v[2]))
        for cle, v in (("hta", hta), ("htb", htb), ("total", [a + b for a, b in zip(hta, htb)]))
    ]
    return natures, lignes_reseau


async def vue_ensemble(db: AsyncSession, redis: Redis, user: Utilisateur, bruts: dict[str, Any]) -> VueEnsemble:
    """KPI de la période et de la précédente, natures, réseaux HTA / HTB.

    RBAC en SQL : les filtres résolus portent la région (BCC / BRC) ou le service (SUPERVISEUR)
    imposés, appliqués par ``appliquer_filtres``.
    """
    resolus = resoudre_filtres(user, bruts)
    filtres = resolus.filtres
    cle = _cle_cache("vue-ensemble", filtres.model_dump_json())
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return VueEnsemble.model_validate({**en_cache, "filtres": resolus.model_dump(mode="json")})

    debut_p, fin_p = periode_precedente(filtres.debut, filtres.fin)
    precedents = filtres.model_copy(update={"debut": debut_p, "fin": fin_p})
    natures, reseaux = await _natures_reseaux(db, filtres)
    resultat = VueEnsemble(
        filtres=resolus,
        periode_precedente=PeriodeSuivi(debut=debut_p, fin=fin_p, libelle=libelle_periode(debut_p, fin_p)),
        kpi=await _kpi(db, filtres),
        kpi_precedent=await _kpi(db, precedents),
        natures=natures,
        reseaux=reseaux,
    )
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat


async def classement(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    bruts: dict[str, Any],
    niveau: str | None,
    limite: int | str | None = 10,
) -> ClassementSuivi:
    """Services, postes sources ou feeders les plus touchés ; « Non renseigné » toujours en dernier."""
    if niveau not in NIVEAUX_CLASSEMENT:
        raise _invalide_classement("Niveau de classement attendu : service, poste_source ou feeder")
    limite = _limite_classement(limite)
    filtres = resoudre_filtres(user, bruts).filtres
    cle = _cle_cache("classement", filtres.model_dump_json(), niveau, str(limite))
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return ClassementSuivi.model_validate(en_cache)

    rattachees: list[tuple[int, str | None, str, int, float, float]] = []
    non_renseigne: tuple[int, float, float] | None = None
    for ligne in (await db.execute(repo.requete_classement(filtres, niveau))).all():
        valeurs = (int(ligne.nombre or 0), float(ligne.duree_minutes or 0), float(ligne.end_mwh or 0))
        if ligne.id is None:
            non_renseigne = valeurs
        else:
            rattachees.append((ligne.id, ligne.code, ligne.libelle, *valeurs))
    rattachees.sort(key=lambda r: (-r[3], r[2]))
    total = sum(r[3] for r in rattachees) + (non_renseigne[0] if non_renseigne else 0)

    def _ligne(id_: int | None, code: str | None, libelle: str, nombre: int, minutes: float, end: float) -> LigneClassement:
        return LigneClassement(
            id=id_,
            code=code,
            libelle=libelle,
            nombre=nombre,
            duree_heures=_heures(minutes),
            end_mwh=_mwh(end),
            part=_part(nombre, total),
        )

    lignes = [_ligne(*r) for r in rattachees[:limite]]
    reste = rattachees[limite:]
    autres = None
    if reste:
        autres = _ligne(
            None,
            None,
            f"Autres ({len(reste)})",
            sum(r[3] for r in reste),
            sum(r[4] for r in reste),
            sum(r[5] for r in reste),
        )
    if non_renseigne is not None:
        lignes.append(_ligne(None, None, NON_RENSEIGNE, *non_renseigne))
    resultat = ClassementSuivi(niveau=niveau, total_interruptions=total, lignes=lignes, autres=autres)  # type: ignore[arg-type]
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat
