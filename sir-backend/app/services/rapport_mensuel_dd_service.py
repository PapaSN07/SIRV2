"""Rapport mensuel d'exploitation distribution — modèle « Analyse succincte statistiques
exploitation distribution » (Service Conduite des Réseaux, réf. PR3-INS-108-a) fusionné avec le
tableau des indicateurs DD (IndicateursDD2026.xlsx) — décision du 06/11/2026.

Partie HTA seulement : la partie BT (pannes, secteurs, temps de dépannage), la disponibilité des
OMT (téléconduite) et les indicateurs commerciaux viennent d'autres outils que SIR.

Contenu :
  1. Indicateurs du mois (END, nombre, SAIFI, SAIDI, défauts aux 100 km, durée de réparation)
     avec cible et cumul de l'année ;
  2. Réalisations par nature (Dakar / Régions), répartition de l'END, END par service / cible ;
  3. Récapitulatif par service ; évolution M-1 et N-1 par service ;
  4. Top 10 des départs (permanent, semi-permanent, fugitif) avec sièges et évolution ;
     sièges des permanents ; tronçons fragilisés ; top des tops ;
  5. Travaux programmés ; agressions par entreprise ; carte du poids de l'END.
"""

from __future__ import annotations

import calendar
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import pilotage_repository
from app.repositories import rapport_hebdo_repository as hebdo_repo
from app.repositories import rapport_mensuel_dd_repository as repo
from app.repositories.perimetre import perimetre_region
from app.repositories.rapport_mensuel_dd_repository import LigneMensuelle
from app.services import saifi_saidi_service
from app.services.rapport_hebdo_dd_service import (
    AUTRES_HTA,
    CATEGORIES_HTA,
    DAKAR,
    DELESTAGE_HTA,
    FUGITIF,
    HTB_AUTRES,
    HTB_DELESTAGE,
    MANOEUVRE_HTA,
    PERMANENT,
    REGIONS,
    SEMI_PERMANENT,
    TRAVAUX_HTA,
    Compte,
    _norme,
    categorie,
    zone,
)
from app.services.rapport_mensuel_service import CarteEnd, assembler_carte_end

logger = logging.getLogger(__name__)

MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
# Libellés du modèle PR3-INS-108-a
LIBELLES_NATURE = {
    PERMANENT: "Défauts permanents",
    SEMI_PERMANENT: "Défauts semi-permanents",
    FUGITIF: "Défauts fugitifs",
    DELESTAGE_HTA: "Délestage incidents HTA",
    TRAVAUX_HTA: "Coupures pour travaux HTA",
    MANOEUVRE_HTA: "Coupures pour manœuvres HTA",
    AUTRES_HTA: "Autres coupures HTA",
}
NATURES = tuple(cle for cle, _ in CATEGORIES_HTA)
INCIDENTS = (PERMANENT, SEMI_PERMANENT, FUGITIF)
ORDRE_DAKAR = ("SDDV", "SDPG", "SDRBD")
_TOP = 10
_SEUIL_TRONCON = 3  # défauts sur un même tronçon dans le mois


def mois_precedent(annee: int, mois: int) -> tuple[int, int]:
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def bornes(annee: int, mois: int) -> tuple[datetime, datetime]:
    a, m = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    return datetime(annee, mois, 1), datetime(a, m, 1)


def libelle_mois(annee: int, mois: int) -> str:
    return f"{MOIS[mois - 1]} {annee}"


def ordre_service(code: str) -> tuple[int, str]:
    """Dakar d'abord (SDDV, SDPG, SDRBD), puis les services des Régions, DRS en dernier."""
    if code in ORDRE_DAKAR:
        return ORDRE_DAKAR.index(code), code
    return (99 if code in ("DRS", "SDRS") else 10), code


# --------------------------------------------------------------------------------------
# Structures
# --------------------------------------------------------------------------------------


@dataclass
class ServiceMois:
    code: str
    zone: str
    par_nature: dict[str, Compte] = field(default_factory=lambda: defaultdict(Compte))

    @property
    def total(self) -> Compte:
        total = Compte()
        for cle in NATURES:
            c = self.par_nature.get(cle, Compte())
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total


@dataclass
class Evolution:
    code: str
    zone: str
    nombre_prec: int
    nombre: int
    end_prec_mwh: float
    end_mwh: float

    @property
    def ecart(self) -> int:
        return self.nombre - self.nombre_prec

    @property
    def evolution_pct(self) -> float | None:
        return None if not self.end_prec_mwh else 100 * (self.end_mwh - self.end_prec_mwh) / self.end_prec_mwh


@dataclass
class TopDepart:
    feeder: str
    services: str
    nombre: int
    nombre_prec: int
    sieges: dict[str, int] = field(default_factory=dict)

    @property
    def evolution(self) -> int:
        return self.nombre - self.nombre_prec


@dataclass
class TronconFragile:
    service: str
    feeder: str
    troncon: str
    nombre: int
    siege: str


@dataclass
class Agression:
    entreprise: str
    services: str
    nombre: int
    end_mwh: float


@dataclass
class Indicateur:
    libelle: str
    unite: str
    realise: float | None
    cible: float | None = None
    cumul: float | None = None
    cible_cumul: float | None = None
    plus_est_mieux: bool = False
    note: str = ""

    @property
    def atteint(self) -> bool | None:
        if self.realise is None or self.cible is None:
            return None
        return self.realise >= self.cible if self.plus_est_mieux else self.realise <= self.cible


@dataclass
class DefautsService:
    code: str
    permanents: int
    longueur_km: float

    @property
    def valeur(self) -> float | None:
        return 100 * self.permanents / self.longueur_km if self.longueur_km else None


@dataclass
class RapportMensuelData:
    annee: int
    mois: int
    zones: list[str]
    bilan: dict[str, dict[str, Compte]]  # zone → nature → compte
    services: list[ServiceMois]
    evolution_m1: list[Evolution]
    evolution_n1: list[Evolution]
    tops: dict[str, dict[str, list[TopDepart]]]  # zone → nature → départs
    top_des_tops: dict[str, list[TopDepart]]
    sieges_permanents: dict[str, dict[str, dict[str, int]]]  # zone → service → siège → nombre
    troncons: dict[str, list[TronconFragile]]
    agressions: dict[str, list[Agression]]
    programmes: dict[str, Compte]  # service → travaux programmés
    indicateurs: list[Indicateur]
    defauts: list[DefautsService]
    end_par_mois_mwh: list[float]  # END HTA de janvier au mois du rapport (cumul de l'année)
    cible_annuelle_mwh: float | None
    cibles_service_mwh: dict[str, float]
    carte: CarteEnd | None
    synthese: list[str]

    @property
    def periode(self) -> str:
        return libelle_mois(self.annee, self.mois)

    @property
    def periode_prec(self) -> str:
        return libelle_mois(*mois_precedent(self.annee, self.mois))

    def total_zone(self, z: str) -> Compte:
        total = Compte()
        for cle in NATURES:
            c = self.bilan.get(z, {}).get(cle, Compte())
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total

    def total_nature(self, cle: str) -> Compte:
        total = Compte()
        for z in self.zones:
            c = self.bilan.get(z, {}).get(cle, Compte())
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total

    @property
    def total(self) -> Compte:
        total = Compte()
        for z in self.zones:
            c = self.total_zone(z)
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total

    @property
    def cible_mois_mwh(self) -> float | None:
        if not self.cible_annuelle_mwh:
            return None
        jours_annee = 366 if calendar.isleap(self.annee) else 365
        return self.cible_annuelle_mwh * calendar.monthrange(self.annee, self.mois)[1] / jours_annee


# --------------------------------------------------------------------------------------
# Calculs (sans base : testables)
# --------------------------------------------------------------------------------------


def _hta(lignes: list[LigneMensuelle]) -> list[LigneMensuelle]:
    return [li for li in lignes if categorie(li) not in (HTB_DELESTAGE, HTB_AUTRES)]


def _code(li: LigneMensuelle) -> str:
    return li.service_code or "—"


def bilan_par_zone(lignes: list[LigneMensuelle]) -> dict[str, dict[str, Compte]]:
    bilan: dict[str, dict[str, Compte]] = defaultdict(lambda: defaultdict(Compte))
    for li in _hta(lignes):
        bilan[zone(li)][categorie(li)].ajouter(li)
    return bilan


def par_service(lignes: list[LigneMensuelle]) -> dict[str, ServiceMois]:
    services: dict[str, ServiceMois] = {}
    for li in _hta(lignes):
        code = _code(li)
        s = services.setdefault(code, ServiceMois(code=code, zone=zone(li)))
        s.par_nature[categorie(li)].ajouter(li)
    return services


def zone_du_service(lignes: list[LigneMensuelle]) -> dict[str, str]:
    """Zone majoritaire de chaque service (un service peut travailler dans les deux)."""
    compte: dict[str, Counter] = defaultdict(Counter)
    for li in lignes:
        compte[_code(li)][zone(li)] += 1
    return {code: c.most_common(1)[0][0] for code, c in compte.items()}


def evolutions(actuel: list[LigneMensuelle], reference: list[LigneMensuelle]) -> list[Evolution]:
    a, r = par_service(actuel), par_service(reference)
    zones = zone_du_service(actuel + reference)
    codes = sorted(set(a) | set(r), key=ordre_service)
    lignes = []
    for code in codes:
        ta = a[code].total if code in a else Compte()
        tr = r[code].total if code in r else Compte()
        lignes.append(Evolution(code, zones.get(code, REGIONS), tr.nombre, ta.nombre, tr.end_mwh, ta.end_mwh))
    return lignes


def _services_du_depart(lignes: list[LigneMensuelle]) -> str:
    return "/".join(sorted({_code(li) for li in lignes}, key=ordre_service))


def tops_departs(
    actuel: list[LigneMensuelle],
    precedent: list[LigneMensuelle],
    natures: tuple[str, ...],
    z: str,
    limite: int = _TOP,
) -> list[TopDepart]:
    """Départs de la zone les plus touchés par ces natures, sièges et nombre du mois précédent."""
    def groupes(lignes: list[LigneMensuelle]) -> dict[str, list[LigneMensuelle]]:
        g: dict[str, list[LigneMensuelle]] = defaultdict(list)
        for li in lignes:
            if li.feeder and zone(li) == z and categorie(li) in natures:
                g[li.feeder].append(li)
        return g

    g, gp = groupes(actuel), groupes(precedent)
    classes = sorted(g.items(), key=lambda kv: (-len(kv[1]), -sum(li.end_mwh for li in kv[1]), kv[0]))[:limite]
    return [
        TopDepart(
            feeder=feeder,
            services=_services_du_depart(lis),
            nombre=len(lis),
            nombre_prec=len(gp.get(feeder, [])),
            sieges=dict(Counter(li.siege or "Non renseigné" for li in lis).most_common()),
        )
        for feeder, lis in classes
    ]


def sieges_permanents(lignes: list[LigneMensuelle]) -> dict[str, dict[str, dict[str, int]]]:
    resultat: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for li in lignes:
        if categorie(li) == PERMANENT:
            resultat[zone(li)][_code(li)][li.siege or "Non renseigné"] += 1
    return {
        z: {code: dict(c.most_common()) for code, c in sorted(par.items(), key=lambda kv: ordre_service(kv[0]))}
        for z, par in resultat.items()
    }


def troncons_fragilises(lignes: list[LigneMensuelle], seuil: int = _SEUIL_TRONCON) -> dict[str, list[TronconFragile]]:
    groupes: dict[tuple[str, str, str], list[LigneMensuelle]] = defaultdict(list)
    for li in lignes:
        if li.troncon and categorie(li) in INCIDENTS:
            groupes[(zone(li), li.feeder or "—", li.troncon)].append(li)
    resultat: dict[str, list[TronconFragile]] = defaultdict(list)
    for (z, feeder, troncon), lis in sorted(groupes.items(), key=lambda kv: -len(kv[1])):
        if len(lis) < seuil:
            continue
        siege = Counter(li.siege for li in lis if li.siege).most_common(1)
        resultat[z].append(
            TronconFragile(_services_du_depart(lis), feeder, troncon, len(lis), siege[0][0] if siege else "—")
        )
    return resultat


def est_agression(li: LigneMensuelle) -> bool:
    cause = _norme(li.cause)
    return "AGRESS" in cause or "MALVEILL" in cause or "CHOC ACCIDENTEL" in cause


def agressions(lignes: list[LigneMensuelle]) -> dict[str, list[Agression]]:
    groupes: dict[tuple[str, str], list[LigneMensuelle]] = defaultdict(list)
    for li in lignes:
        if est_agression(li):
            groupes[(zone(li), (li.entreprise or "Tiers").strip())].append(li)
    resultat: dict[str, list[Agression]] = defaultdict(list)
    for (z, entreprise), lis in sorted(groupes.items(), key=lambda kv: (-len(kv[1]), kv[0][1])):
        resultat[z].append(
            Agression(entreprise, _services_du_depart(lis), len(lis), sum(li.end_mwh for li in lis))
        )
    return resultat


def travaux_programmes(lignes: list[LigneMensuelle]) -> dict[str, Compte]:
    resultat: dict[str, Compte] = defaultdict(Compte)
    for li in lignes:
        if categorie(li) == TRAVAUX_HTA:
            resultat[_code(li)].ajouter(li)
    return dict(sorted(resultat.items(), key=lambda kv: ordre_service(kv[0])))


def duree_moyenne_reparation_h(lignes: list[LigneMensuelle]) -> float | None:
    """Durée moyenne des défauts permanents remis sous tension (reprise de la clientèle)."""
    durees = [li.duree_minutes for li in lignes if categorie(li) == PERMANENT and li.duree_minutes]
    return sum(durees) / len(durees) / 60 if durees else None


def _pct(actuel: float, precedent: float) -> str:
    if not precedent:
        return "sans référence"
    v = 100 * (actuel - precedent) / precedent
    return f"{'+' if v >= 0 else ''}{v:.1f} %".replace(".", ",")


def _nb(v: float, d: int = 0) -> str:
    return f"{v:,.{d}f}".replace(",", "\u00a0").replace(".", ",")


def rediger_synthese(data: RapportMensuelData, total_prec: Compte) -> list[str]:
    """Quelques phrases d'introduction, écrites à partir des chiffres (relues par le SCR)."""
    t = data.total
    phrases = [
        f"En {data.periode}, le réseau HTA a enregistré **{_nb(t.nombre)} interruptions** pour "
        f"**{_nb(t.end_mwh * 1000)} kWh** d'énergie non distribuée, contre {_nb(total_prec.nombre)} "
        f"interruptions et {_nb(total_prec.end_mwh * 1000)} kWh en {data.periode_prec} "
        f"(END {_pct(t.end_mwh, total_prec.end_mwh)})."
    ]
    if data.cible_mois_mwh:
        ecart = t.end_mwh - data.cible_mois_mwh
        phrases.append(
            f"La cible du mois ({_nb(data.cible_mois_mwh * 1000)} kWh) est "
            + (f"**dépassée de {_nb(ecart * 1000)} kWh**." if ecart > 0 else f"**respectée** ({_nb(-ecart * 1000)} kWh de marge).")
        )
    natures = sorted(NATURES, key=lambda c: -data.total_nature(c).end_mwh)
    if t.end_mwh:
        premiere = natures[0]
        part = 100 * data.total_nature(premiere).end_mwh / t.end_mwh
        phrases.append(
            f"{LIBELLES_NATURE[premiere]} : première source d'END ({_nb(part, 0)} % du total)."
        )
    services = sorted(data.services, key=lambda s: -s.total.end_mwh)
    if services and t.end_mwh:
        s = services[0]
        phrases.append(
            f"{s.code} porte la plus forte END du mois ({_nb(s.total.end_mwh * 1000)} kWh, "
            f"{_nb(100 * s.total.end_mwh / t.end_mwh, 0)} %)."
        )
    for z in data.zones:
        top = data.top_des_tops.get(z, [])
        if top:
            phrases.append(
                f"Départ le plus perturbé ({z}) : **{top[0].feeder}** ({top[0].services}), "
                f"{top[0].nombre} incidents contre {top[0].nombre_prec} le mois précédent."
            )
    return phrases


def assembler(
    annee: int,
    mois: int,
    lignes: list[LigneMensuelle],
    precedent: list[LigneMensuelle],
    annee_prec: list[LigneMensuelle],
    *,
    zones: list[str],
    end_par_mois_mwh: list[float],
    cible_annuelle_mwh: float | None,
    indicateurs: list[Indicateur],
    defauts: list[DefautsService],
    carte: CarteEnd | None = None,
    cibles_service_mwh: dict[str, float] | None = None,
) -> RapportMensuelData:
    """Toutes les sections à partir des interruptions du mois, du mois précédent et de N-1."""
    services = sorted(par_service(lignes).values(), key=lambda s: ordre_service(s.code))
    data = RapportMensuelData(
        annee=annee,
        mois=mois,
        zones=zones,
        bilan=bilan_par_zone(lignes),
        services=services,
        evolution_m1=evolutions(lignes, precedent),
        evolution_n1=evolutions(lignes, annee_prec),
        tops={z: {cle: tops_departs(lignes, precedent, (cle,), z) for cle in INCIDENTS} for z in zones},
        top_des_tops={z: tops_departs(lignes, precedent, INCIDENTS, z) for z in zones},
        sieges_permanents=sieges_permanents(lignes),
        troncons=troncons_fragilises(lignes),
        agressions=agressions(lignes),
        programmes=travaux_programmes(lignes),
        indicateurs=indicateurs,
        defauts=defauts,
        end_par_mois_mwh=end_par_mois_mwh,
        cible_annuelle_mwh=cible_annuelle_mwh,
        cibles_service_mwh=cibles_service_mwh or {},
        carte=carte,
        synthese=[],
    )
    total_prec = Compte()
    for li in _hta(precedent):
        total_prec.ajouter(li)
    data.synthese = rediger_synthese(data, total_prec)
    return data


# --------------------------------------------------------------------------------------
# Collecte
# --------------------------------------------------------------------------------------


def _filtrer(lignes: list[LigneMensuelle], zones: list[str]) -> list[LigneMensuelle]:
    return [li for li in lignes if zone(li) in zones]


async def _region_et_zones(db: AsyncSession, region_id: int | None) -> list[str]:
    if region_id is None:
        return [DAKAR, REGIONS]
    libelle = await repo.libelle_region(db, region_id)
    return [DAKAR if "DAKAR" in _norme(libelle) else REGIONS]


async def collecter(
    db: AsyncSession,
    annee: int,
    mois: int,
    *,
    region_id: int | None = None,
    avec_cumul: bool = True,
) -> RapportMensuelData:
    """Données du rapport du mois ; `region_id` : Dakar ou Régions seulement (BCC / BRC).

    `avec_cumul=False` (aperçu à l'écran) : sans la lecture de toute l'année (END cumulée,
    SAIFI / SAIDI de l'année), plus rapide.
    """
    zones = await _region_et_zones(db, region_id)
    debut, fin = bornes(annee, mois)
    lignes = _filtrer(await repo.lister(db, debut, fin), zones)
    precedent = _filtrer(await repo.lister(db, *bornes(*mois_precedent(annee, mois))), zones)
    annee_prec = _filtrer(await repo.lister(db, *bornes(annee - 1, mois)), zones)

    services = await hebdo_repo.services_distribution(db)
    service_ids = [sid for sid, _, _ in services]
    code_vers_id = {code: sid for sid, code, _ in services}
    cible_end = await repo.objectif_annuel(db, annee, "END")
    cible_saifi = await repo.objectif_annuel(db, annee, "SAIFI")
    cible_saidi = await repo.objectif_annuel(db, annee, "SAIDI")

    end_par_mois: list[float] = []
    cumul_saifi = cumul_saidi = None
    with perimetre_region(region_id):
        mensuel = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut, fin)
        if avec_cumul:
            annuel = await saifi_saidi_service.calculer_perimetre(db, service_ids, datetime(annee, 1, 1), fin)
            cumul_saifi, cumul_saidi = annuel.saifi, annuel.saidi
    if avec_cumul:
        lignes_annee = _filtrer(await repo.lister(db, datetime(annee, 1, 1), fin), zones)
        par_mois: dict[int, float] = defaultdict(float)
        for li in _hta(lignes_annee):
            par_mois[li.date_apparition.month] += li.end_mwh
        end_par_mois = [round(par_mois.get(m, 0.0), 4) for m in range(1, mois + 1)]

    hta = _hta(lignes)
    total_end = sum(li.end_mwh for li in hta)
    jours_annee = 366 if calendar.isleap(annee) else 365
    jours_ecoules = (fin.date() - date(annee, 1, 1)).days
    cible_mois = cible_end * calendar.monthrange(annee, mois)[1] / jours_annee if cible_end else None
    cible_cumul = cible_end * jours_ecoules / jours_annee if cible_end else None
    duree = duree_moyenne_reparation_h(lignes)

    # Défauts permanents aux 100 km de réseau HTA, service par service
    permanents = Counter(_code(li) for li in lignes if categorie(li) == PERMANENT)
    defauts: list[DefautsService] = []
    for code in sorted({_code(li) for li in hta}, key=ordre_service):
        sid = code_vers_id.get(code)
        km = await pilotage_repository.longueur_reseau_km(db, [sid]) if sid else 0.0
        defauts.append(DefautsService(code, permanents.get(code, 0), km))
    total_km = sum(d.longueur_km for d in defauts)
    total_perm = sum(d.permanents for d in defauts)

    indicateurs = [
        Indicateur(
            "Énergie non distribuée HTA", "kWh", total_end * 1000,
            cible=cible_mois * 1000 if cible_mois else None,
            cumul=sum(end_par_mois) * 1000 if end_par_mois else None,
            cible_cumul=cible_cumul * 1000 if cible_cumul else None,
            note="Travaux, manœuvres et incidents sur le réseau HTA",
        ),
        Indicateur("Nombre d'interruptions HTA", "", float(len(hta))),
        Indicateur("SAIFI", "", mensuel.saifi, cible=cible_saifi / 12 if cible_saifi else None,
                   cumul=cumul_saifi, cible_cumul=cible_saifi * jours_ecoules / jours_annee if cible_saifi else None),
        Indicateur("SAIDI", "h", mensuel.saidi, cible=cible_saidi / 12 if cible_saidi else None,
                   cumul=cumul_saidi, cible_cumul=cible_saidi * jours_ecoules / jours_annee if cible_saidi else None),
        Indicateur("Défauts permanents aux 100 km", "", 100 * total_perm / total_km if total_km else None,
                   note=f"{total_perm} défauts permanents · {_nb(total_km)} km de réseau HTA"),
        Indicateur("Durée moyenne de réparation des permanents", "h", duree,
                   note="Reprise de la clientèle"),
    ]

    carte = None
    try:
        par_code: dict[str, Compte] = defaultdict(Compte)
        for li in hta:
            par_code[_code(li)].ajouter(li)
        items = [
            _ItemCarte(code_vers_id[c], v.end_mwh, v.nombre)
            for c, v in par_code.items() if c in code_vers_id and v.end_mwh > 0
        ]
        libelles = await pilotage_repository.libelles_services(db, [i.service_id for i in items])
        points = await pilotage_repository.points_sig_par_service(db)
        carte = assembler_carte_end(items, sum(i.end_mwh for i in items), libelles, points)
    except Exception:  # noqa: BLE001 — la carte est un complément
        logger.exception("Carte du poids de l'END non construite")

    return assembler(
        annee, mois, lignes, precedent, annee_prec,
        zones=zones,
        end_par_mois_mwh=end_par_mois,
        cible_annuelle_mwh=cible_end,
        indicateurs=indicateurs,
        defauts=defauts,
        carte=carte,
    )


@dataclass(frozen=True)
class _ItemCarte:
    service_id: int
    end_mwh: float
    nombre_interruptions: int
