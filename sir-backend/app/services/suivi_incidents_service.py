"""Menu « Suivi incidents » : résolution des filtres communs aux onglets.

Périmètre : même règle que les indicateurs (``indicateurs_service._resolve_scope``) — rôles
nationaux libres, BCC / BRC limités à leur région (``scope_service_id`` = région), SUPERVISEUR
limité à son service. Les valeurs imposées par le rôle remplacent celles de la requête.
"""

from __future__ import annotations

import asyncio
import bisect
import hashlib
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import pilotage_repository
from app.repositories import suivi_incidents_repository as repo
from app.schemas.suivi_incidents import (
    CarteSuivi,
    CategorieNature,
    ClassementSuivi,
    EvolutionSuivi,
    FiltresIncidents,
    FiltresResolus,
    IndicateurSaifi,
    KpiSuivi,
    LigneClassement,
    LigneReseau,
    LocalisationPosteSource,
    LocalisationSuivi,
    MoisReference,
    NaturesPoint,
    PageNonLocalises,
    ParModeLocalisation,
    PeriodeSuivi,
    PerimetreSuivi,
    PointCarte,
    PosteNonLocalise,
    PointEvolution,
    RepartitionNature,
    RepartitionReseau,
    ReseauSuivi,
    SaifiMois,
    SaifiNature,
    SaifiReseau,
    SaifiSaidiSuivi,
    SaifiService,
    SemaineSenelecSchema,
    VueEnsemble,
)
from app.services import indicateurs_cache_service as cache
from app.services import rapport_hebdo_dd_service as hebdo
from app.services.indicateurs_service import _load_service_ids, _resolve_scope
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


# ── Onglet Évolution ──────────────────────────────────────────────────────────────────────

GRANULARITES = ("jour", "semaine", "mois")
JOURS_MAX_GRANULARITE_JOUR = 366
_MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def granularite_auto(debut: date, fin: date) -> str:
    """Jour jusqu'à 31 jours, semaine SENELEC jusqu'à 186 jours, mois au-delà (fin incluse)."""
    jours = (fin - debut).days + 1
    if jours <= 31:
        return "jour"
    if jours <= 186:
        return "semaine"
    return "mois"


def _mois_suivant(jour: date) -> date:
    return date(jour.year + (jour.month == 12), jour.month % 12 + 1, 1)


def intervalles(debut: date, fin: date, granularite: str) -> list[tuple[date, date, str]]:
    """Points de la série : contigus, couvrant [debut, fin], premier et dernier rognés aux bornes."""
    if granularite not in GRANULARITES:
        raise ValueError(f"Granularité inconnue : {granularite}")
    points: list[tuple[date, date, str]] = []
    courant = debut
    while courant <= fin:
        if granularite == "jour":
            fin_point, libelle = courant, f"{courant:%d/%m}"
        elif granularite == "semaine":
            semaine = semaine_senelec(courant)
            fin_point, libelle = semaine.fin, f"S{semaine.numero}"
        else:
            fin_point = _mois_suivant(courant) - timedelta(days=1)
            libelle = f"{_MOIS_COURTS[courant.month - 1]} {courant.year}"
        fin_point = min(fin_point, fin)
        points.append((courant, fin_point, libelle))
        courant = fin_point + timedelta(days=1)
    return points


def _en_date(valeur: Any) -> date:
    """Jour renvoyé par la base : ``date`` (SQL Server) ou texte « AAAA-MM-JJ » (SQLite)."""
    if isinstance(valeur, date):
        return valeur if type(valeur) is date else valeur.date()  # type: ignore[union-attr]
    return date.fromisoformat(str(valeur)[:10])




async def evolution(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    bruts: dict[str, Any],
    granularite: str | None = "auto",
) -> EvolutionSuivi:
    """Série par jour, semaine SENELEC ou mois, tous les intervalles (vides compris), par nature."""
    choix = "auto" if granularite is None else granularite
    if choix != "auto" and choix not in GRANULARITES:
        raise _invalide_classement("Granularité attendue : auto, jour, semaine ou mois")
    filtres = resoudre_filtres(user, bruts).filtres
    appliquee = granularite_auto(filtres.debut, filtres.fin) if choix == "auto" else choix
    if appliquee == "jour" and (filtres.fin - filtres.debut).days + 1 > JOURS_MAX_GRANULARITE_JOUR:
        raise _invalide_classement("Pas de série par jour au-delà d'un an : choisissez la semaine ou le mois")
    cle = _cle_cache("evolution", filtres.model_dump_json(), appliquee)
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return EvolutionSuivi.model_validate(en_cache)

    bornes = intervalles(filtres.debut, filtres.fin, appliquee)
    debuts = [b[0] for b in bornes]
    sommes = [[0, 0.0, 0.0, {cle_n: 0 for cle_n, _ in CATEGORIES_NATURE}] for _ in bornes]
    for ligne in (await db.execute(repo.requete_evolution(filtres))).all():
        i = bisect.bisect_right(debuts, _en_date(ligne.jour)) - 1
        if i < 0:
            continue
        nombre = int(ligne.nombre or 0)
        point = sommes[i]
        point[0] += nombre
        point[1] += float(ligne.duree_minutes or 0)
        point[2] += float(ligne.end_mwh or 0)
        point[3][categorie_nature(ligne.nature, ligne.cause)] += nombre
    resultat = EvolutionSuivi(
        granularite=appliquee,  # type: ignore[arg-type]
        points=[
            PointEvolution(
                debut=d,
                fin=f,
                libelle=libelle,
                nombre=int(somme[0]),
                duree_heures=_heures(somme[1]),
                end_mwh=_mwh(somme[2]),
                natures=NaturesPoint(**somme[3]),
            )
            for (d, f, libelle), somme in zip(bornes, sommes)
        ],
    )
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat


# ── Onglet Réseau ─────────────────────────────────────────────────────────────────────────

NIVEAUX_RESEAU = ("poste_source", "feeder")
_LIBELLE_NIVEAU = {"poste_source": "Poste source", "feeder": "Feeder"}
_PLURIEL_NIVEAU = {"poste_source": "Postes sources", "feeder": "Feeders"}


def _niveau_reseau(niveau: str | None) -> str:
    if niveau not in NIVEAUX_RESEAU:
        raise _invalide_classement("Niveau attendu : poste_source ou feeder")
    return niveau


async def _reseau(db: AsyncSession, redis: Redis, filtres: FiltresIncidents, niveau: str) -> ReseauSuivi:
    cle = _cle_cache("reseau", filtres.model_dump_json(), niveau)
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return ReseauSuivi.model_validate(en_cache)

    postes = {
        ligne.id: int(ligne.postes or 0)
        for ligne in (await db.execute(repo.requete_reseau_postes(filtres, niveau))).all()
    }
    brutes = (await db.execute(repo.requete_reseau(filtres, niveau))).all()
    total = sum(int(ligne.nombre or 0) for ligne in brutes)
    lignes = [
        LigneReseau(
            id=ligne.id,
            code=ligne.code if ligne.id is not None else None,
            libelle=ligne.libelle if ligne.id is not None else NON_RENSEIGNE,
            poste_source=ligne.poste_source if ligne.id is not None else None,
            nombre=int(ligne.nombre or 0),
            duree_heures=_heures(ligne.duree_minutes),
            end_mwh=_mwh(ligne.end_mwh),
            coupures_clients=int(ligne.coupures_clients or 0),
            postes_touches=postes.get(ligne.id, 0),
            part=_part(int(ligne.nombre or 0), total),
        )
        for ligne in brutes
    ]
    lignes.sort(key=lambda l: (l.id is None, -l.nombre, l.libelle))
    resultat = ReseauSuivi(niveau=niveau, total_interruptions=total, lignes=lignes)  # type: ignore[arg-type]
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat


async def reseau(
    db: AsyncSession, redis: Redis, user: Utilisateur, bruts: dict[str, Any], niveau: str | None
) -> ReseauSuivi:
    """Tous les postes sources ou feeders touchés ; « Non renseigné » en dernier."""
    niveau = _niveau_reseau(niveau)
    filtres = resoudre_filtres(user, bruts).filtres
    return await _reseau(db, redis, filtres, niveau)




def construire_xlsx_reseau(donnees: ReseauSuivi, titre: str) -> bytes:
    """Classeur d'une feuille : titre, en-tête, lignes dans l'ordre du tableau Réseau."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = _PLURIEL_NIVEAU[donnees.niveau]
    feuille.append([titre])
    feuille["A1"].font = Font(bold=True, size=12)
    feuille.append([])
    entete = [_LIBELLE_NIVEAU[donnees.niveau], "Code"]
    if donnees.niveau == "feeder":
        entete.append("Poste source")
    entete += ["Interruptions", "Durée (h)", "END (MWh)", "Coupures-clients", "Postes touchés", "Part (%)"]
    feuille.append(entete)
    remplissage = PatternFill("solid", fgColor="262051")
    for cellule in feuille[3]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = remplissage
    for ligne in donnees.lignes:
        valeurs: list[object] = [ligne.libelle, ligne.code]
        if donnees.niveau == "feeder":
            valeurs.append(ligne.poste_source)
        valeurs += [
            ligne.nombre,
            round(ligne.duree_heures, 2),
            round(ligne.end_mwh, 3),
            ligne.coupures_clients,
            ligne.postes_touches,
            round(ligne.part * 100, 1),
        ]
        feuille.append(valeurs)
        # Libellés venus de la base : toujours du texte, jamais une formule (« =… »)
        for cellule in feuille[feuille.max_row]:
            if isinstance(cellule.value, str):
                cellule.data_type = "s"
    for i, largeur in enumerate([34, 14] + ([30] if donnees.niveau == "feeder" else []) + [14, 12, 12, 16, 14, 10], start=1):
        feuille.column_dimensions[get_column_letter(i)].width = largeur
    feuille.freeze_panes = "A4"
    sortie = BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


async def exporter_reseau(
    db: AsyncSession, redis: Redis, user: Utilisateur, bruts: dict[str, Any], niveau: str | None
) -> tuple[bytes, str]:
    """Fichier Excel du tableau Réseau (mêmes droits et même périmètre que ``reseau``)."""
    niveau = _niveau_reseau(niveau)
    resolus = resoudre_filtres(user, bruts)
    filtres = resolus.filtres
    donnees = await _reseau(db, redis, filtres, niveau)
    titre = f"Suivi incidents — {_PLURIEL_NIVEAU[niveau]} touchés — {resolus.libelle_periode}"
    contenu = await asyncio.to_thread(construire_xlsx_reseau, donnees, titre)
    return contenu, f"suivi_{niveau}_{filtres.debut.isoformat()}_{filtres.fin.isoformat()}.xlsx"


# ── Onglet SAIFI / SAIDI ──────────────────────────────────────────────────────────────────

# Filtres qui restreignent le numérateur sans changer le périmètre (dénominateur)
_FILTRES_CONTRIBUTION = ("poste_source_id", "feeder_id", "nature_id", "cause_id", "reseau", "exogene")


def _indicateur(clients: float, client_heures: float, nombre: int, base: int) -> dict[str, Any]:
    return {
        "saifi": clients / base if base > 0 else 0.0,
        "saidi": client_heures / base if base > 0 else 0.0,
        "interruptions": int(nombre),
        "clients_coupes": int(clients),
        "client_heures": float(client_heures),
        "clients_reference": int(base),
    }


def _sommes(lignes: list[Any]) -> tuple[float, float, int]:
    return (
        sum(float(l.clients or 0) for l in lignes),
        sum(float(l.client_heures or 0) for l in lignes),
        sum(int(l.nombre or 0) for l in lignes),
    )


async def _base_clients(
    db: AsyncSession, service_ids: list[int], debut: datetime, fin: datetime, aujourd_hui: date
) -> tuple[int, tuple[int, int] | None]:
    """Base clients du périmètre (formule SENELEC) et mois de la base réellement utilisée."""
    mois = await pilotage_repository.mois_derniere_apparition(db, service_ids, debut, fin)
    if mois is None:
        borne = min(fin - timedelta(seconds=1), datetime(aujourd_hui.year, aujourd_hui.month, aujourd_hui.day))
        mois = (borne.year, borne.month)
    utilise = await pilotage_repository.dernier_mois_base(db, service_ids, *mois) if service_ids else None
    if utilise is None:
        return 0, None
    base = await pilotage_repository.clients_reference_exacte(db, service_ids, *utilise)
    return base, utilise


def _mois_de_la_periode(debut: date, fin: date) -> list[tuple[int, int]]:
    mois, courant = [], date(debut.year, debut.month, 1)
    while courant <= fin:
        mois.append((courant.year, courant.month))
        courant = _mois_suivant(courant)
    return mois


async def saifi_saidi(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    bruts: dict[str, Any],
    aujourd_hui: date | None = None,
) -> SaifiSaidiSuivi:
    """SAIFI / SAIDI du périmètre, ou contribution des interruptions filtrées (base clients du périmètre)."""
    resolus = resoudre_filtres(user, bruts)
    filtres = resolus.filtres
    scope = _resolve_scope(user, region_id=filtres.region_id)
    cle = _cle_cache("saifi-saidi", filtres.model_dump_json(), scope.niveau, str(scope.scope_id))
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return SaifiSaidiSuivi.model_validate(en_cache)

    service_ids = await _load_service_ids(db, scope)  # pose aussi la région du calcul
    contribution = any(getattr(filtres, champ) is not None for champ in _FILTRES_CONTRIBUTION) or (
        filtres.service_id is not None and not resolus.perimetre.service_verrouille
    )
    debut = datetime(filtres.debut.year, filtres.debut.month, filtres.debut.day)
    fin = datetime(filtres.fin.year, filtres.fin.month, filtres.fin.day) + timedelta(days=1)
    base, mois_base = await _base_clients(db, service_ids, debut, fin, aujourd_hui or date.today())

    async def lignes(regroupement: str | None) -> list[Any]:
        if not service_ids:
            return []
        return list((await db.execute(repo.requete_saifi(filtres, service_ids, regroupement))).all())

    # Synthèse
    clients, client_heures, nombre = _sommes(await lignes(None))
    synthese = IndicateurSaifi(**_indicateur(clients, client_heures, nombre, base))

    # Réseaux et natures : une requête (nature, cause)
    par_nature = await lignes("nature")
    reseaux_sommes: dict[str, list[Any]] = {"hta": [], "htb": []}
    natures_sommes: dict[str, list[Any]] = {cle_n: [] for cle_n, _ in CATEGORIES_NATURE}
    for ligne in par_nature:
        reseaux_sommes["htb" if est_cause_htb(ligne.cause) else "hta"].append(ligne)
        natures_sommes[categorie_nature(ligne.nature, ligne.cause)].append(ligne)
    reseaux = [
        SaifiReseau(reseau=r, **_indicateur(*_sommes(reseaux_sommes[r]), base))  # type: ignore[arg-type]
        for r in ("hta", "htb")
    ]
    reseaux.append(SaifiReseau(reseau="total", **_indicateur(*_sommes(par_nature), base)))

    def part(saifi: float) -> float:
        return saifi / synthese.saifi if synthese.saifi > 0 else 0.0

    natures = []
    for cle_n, libelle in CATEGORIES_NATURE:
        valeurs = _indicateur(*_sommes(natures_sommes[cle_n]), base)
        natures.append(SaifiNature(categorie=cle_n, libelle=libelle, part_saifi=part(valeurs["saifi"]), **valeurs))

    # Série mensuelle : numérateur du mois (rogné à la période) ÷ base du mois civil
    mois = _mois_de_la_periode(filtres.debut, filtres.fin)
    par_mois: dict[tuple[int, int], list[float]] = {m: [0.0, 0.0, 0] for m in mois}
    for ligne in await lignes("jour"):
        jour = _en_date(ligne.jour)
        cible = par_mois.get((jour.year, jour.month))
        if cible is not None:
            cible[0] += float(ligne.clients or 0)
            cible[1] += float(ligne.client_heures or 0)
            cible[2] += int(ligne.nombre or 0)
    bases = (
        await pilotage_repository.clients_reference_par_mois(db, service_ids, (mois[0][0] - 1, mois[0][1]), mois[-1])
        if service_ids
        else {}
    )
    mensuel, cumul_clients, cumul_heures = [], 0.0, 0.0
    for annee, numero in mois:
        connus = [k for k, v in bases.items() if k <= (annee, numero) and v > 0]
        base_mois = bases[max(connus)] if connus else 0
        c, h, n = par_mois[(annee, numero)]
        cumul_clients += c
        cumul_heures += h
        mensuel.append(
            SaifiMois(
                annee=annee,
                mois=numero,
                libelle=f"{_MOIS_COURTS[numero - 1]} {annee}",
                saifi=c / base_mois if base_mois else 0.0,
                saidi=h / base_mois if base_mois else 0.0,
                saifi_cumule=cumul_clients / base_mois if base_mois else 0.0,
                saidi_cumule=cumul_heures / base_mois if base_mois else 0.0,
                interruptions=int(n),
            )
        )

    # Contribution par service (les interruptions sans service sont hors formule)
    services = []
    for ligne in await lignes("service"):
        valeurs = _indicateur(float(ligne.clients or 0), float(ligne.client_heures or 0), int(ligne.nombre or 0), base)
        services.append(
            SaifiService(id=ligne.id, code=ligne.code, libelle=ligne.libelle or NON_RENSEIGNE, part_saifi=part(valeurs["saifi"]), **valeurs)
        )
    services.sort(key=lambda x: (x.id is None, -x.saifi, x.libelle))

    resultat = SaifiSaidiSuivi(
        contribution=contribution,
        synthese=synthese,
        mois_reference=MoisReference(annee=mois_base[0], mois=mois_base[1]) if mois_base else None,
        reseaux=reseaux,
        natures=natures,
        mensuel=mensuel,
        services=services,
    )
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat


# ── Onglets Carte et Localisation ─────────────────────────────────────────────────────────

# Lue à chaque appel (les tests la remplacent) : au-delà, la carte devient illisible et lourde
LIMITE_POINTS_CARTE = 3000
_ORDRE_NATURES = {cle_n: i for i, (cle_n, _) in enumerate(CATEGORIES_NATURE)}


async def _postes_localises(db: AsyncSession, filtres: FiltresIncidents) -> list[dict[str, Any]]:
    """Postes touchés avec leur nature dominante et leur position (rapprochement SIG, sinon nom)."""
    postes = [dict(ligne._mapping) for ligne in (await db.execute(repo.requete_postes_touches(filtres))).all()]
    if not postes:
        return []

    # Nature dominante : la catégorie la plus fréquente ; égalité → incident, délestage, travaux, autre
    comptes: dict[int, dict[str, int]] = {}
    for ligne in (await db.execute(repo.requete_postes_natures(filtres))).all():
        par_categorie = comptes.setdefault(ligne.poste_id, {})
        categorie = categorie_nature(ligne.nature, ligne.cause)
        par_categorie[categorie] = par_categorie.get(categorie, 0) + int(ligne.nombre or 0)

    # 1. Nœud SIG rapproché (première ligne exploitable par poste)
    rapproches: dict[int, tuple[float, float]] = {}
    for requete in repo.requete_rapprochement_sig([p["poste_id"] for p in postes]):
        for ligne in (await db.execute(requete)).all():
            if ligne.poste_id in rapproches:
                continue
            longitude, latitude = pilotage_repository._lon_lat(ligne.coord_x, ligne.coord_y)
            if longitude is not None and latitude is not None:
                rapproches[ligne.poste_id] = (longitude, latitude)

    # 2. Nom (puis code) du poste dans le SIG, homonymes départagés par le feeder du poste
    restants = [p for p in postes if p["poste_id"] not in rapproches]
    coords = (
        await pilotage_repository.coords_par_nom(db, [p["libelle"] for p in restants] + [p["code"] for p in restants])
        if restants
        else {}
    )
    for poste in postes:
        par_categorie = comptes.get(poste["poste_id"], {})
        poste["nature_dominante"] = (
            min(par_categorie, key=lambda c: (-par_categorie[c], _ORDRE_NATURES[c])) if par_categorie else "autre"
        )
        if poste["poste_id"] in rapproches:
            poste["longitude"], poste["latitude"] = rapproches[poste["poste_id"]]
            poste["localisation"] = "rapprochement"
            continue
        candidats = coords.get((poste["libelle"] or "").casefold()) or coords.get((poste["code"] or "").casefold()) or []
        point = pilotage_repository.choisir_point(candidats, poste["feeder_id"])
        poste["longitude"], poste["latitude"] = point if point else (None, None)
        poste["localisation"] = "nom" if point else None
    return postes


async def _postes_localises_en_cache(db: AsyncSession, redis: Redis, filtres: FiltresIncidents) -> list[dict[str, Any]]:
    """``_postes_localises`` calculé une fois par jeu de filtres résolus (1 h), partagé par la carte et
    toutes les pages de Localisation : sur une année nationale, ce calcul est le plus coûteux du menu."""
    cle = _cle_cache("postes-localises", filtres.model_dump_json())
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return list(en_cache)
    postes = await _postes_localises(db, filtres)
    await cache.set_cached(redis, cle, postes)
    return postes


async def carte(db: AsyncSession, redis: Redis, user: Utilisateur, bruts: dict[str, Any]) -> CarteSuivi:
    """Postes touchés localisés, les plus touchés d'abord, au plus ``LIMITE_POINTS_CARTE``."""
    filtres = resoudre_filtres(user, bruts).filtres
    limite = LIMITE_POINTS_CARTE
    cle = _cle_cache("carte", filtres.model_dump_json(), str(limite))
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return CarteSuivi.model_validate(en_cache)

    postes = await _postes_localises_en_cache(db, redis, filtres)
    localises = sorted((p for p in postes if p["localisation"]), key=lambda p: (-int(p["nombre"] or 0), p["libelle"]))
    points = [
        PointCarte(
            poste_id=p["poste_id"],
            code=p["code"],
            libelle=p["libelle"],
            feeder_id=p["feeder_id"],
            feeder=p["feeder"],
            nombre=int(p["nombre"] or 0),
            duree_heures=_heures(p["duree_minutes"]),
            clients=int(p["clients"] or 0),
            nature_dominante=p["nature_dominante"],
            longitude=p["longitude"],
            latitude=p["latitude"],
            localisation=p["localisation"],
        )
        for p in localises[:limite]
    ]
    resultat = CarteSuivi(
        postes_touches=len(postes),
        postes_localises=len(localises),
        tronque=len(localises) > limite,
        points=points,
    )
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat


def _entier_borne(valeur: int | str | None, defaut: int, minimum: int, maximum: int, nom: str) -> int:
    """Paramètre de pagination : entier dans [minimum, maximum], sinon 422 enveloppé."""
    if valeur is None or valeur == "":
        return defaut
    try:
        entier = int(str(valeur))
    except ValueError:
        entier = minimum - 1
    if not minimum <= entier <= maximum:
        raise _invalide_classement(f"Le paramètre {nom} doit être un entier entre {minimum} et {maximum}")
    return entier


async def localisation(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    bruts: dict[str, Any],
    page: int | str | None = 1,
    size: int | str | None = 20,
) -> LocalisationSuivi:
    """Taux de postes touchés localisés, détail par poste source, postes non localisés paginés."""
    page_n = _entier_borne(page, 1, 1, 1_000_000, "page")
    taille = _entier_borne(size, 20, 1, 100, "size")
    filtres = resoudre_filtres(user, bruts).filtres
    cle = _cle_cache("localisation", filtres.model_dump_json(), str(page_n), str(taille))
    en_cache = await cache.get_cached(redis, cle)
    if en_cache is not None:
        return LocalisationSuivi.model_validate(en_cache)

    postes = await _postes_localises_en_cache(db, redis, filtres)
    localises = [p for p in postes if p["localisation"]]

    par_ps: dict[int | None, dict[str, Any]] = {}
    for p in postes:
        ligne = par_ps.setdefault(
            p["poste_source_id"],
            {"libelle": p["poste_source"] if p["poste_source_id"] is not None else NON_RENSEIGNE, "touches": 0, "non": 0},
        )
        ligne["touches"] += 1
        ligne["non"] += 0 if p["localisation"] else 1
    postes_sources = sorted(
        (
            LocalisationPosteSource(
                id=ps_id,
                libelle=v["libelle"],
                postes_touches=v["touches"],
                non_localises=v["non"],
                taux=(v["touches"] - v["non"]) / v["touches"] if v["touches"] else 0.0,
            )
            for ps_id, v in par_ps.items()
        ),
        key=lambda x: (x.id is None, -x.non_localises, x.libelle),
    )

    non_localises = sorted((p for p in postes if not p["localisation"]), key=lambda p: (-int(p["nombre"] or 0), p["libelle"]))
    debut = (page_n - 1) * taille
    resultat = LocalisationSuivi(
        postes_touches=len(postes),
        postes_localises=len(localises),
        taux=len(localises) / len(postes) if postes else 0.0,
        par_mode=ParModeLocalisation(
            rapprochement=sum(1 for p in localises if p["localisation"] == "rapprochement"),
            nom=sum(1 for p in localises if p["localisation"] == "nom"),
        ),
        postes_sources=postes_sources,
        non_localises=PageNonLocalises(
            total=len(non_localises),
            page=page_n,
            size=taille,
            items=[
                PosteNonLocalise(
                    poste_id=p["poste_id"],
                    code=p["code"],
                    libelle=p["libelle"],
                    feeder=p["feeder"],
                    poste_source=p["poste_source"],
                    interruptions=int(p["nombre"] or 0),
                )
                for p in non_localises[debut : debut + taille]
            ],
        ),
    )
    await cache.set_cached(redis, cle, resultat.model_dump(mode="json"))
    return resultat

