"""Rapport hebdomadaire d'exploitation du réseau de distribution (modèle « Rapport Hebdo DD »).

Semaine du samedi au vendredi (modèle S39-2021), envoyée le samedi à 8 h. Partie HTA
uniquement : la partie BT (dépannages) n'est pas dans SIR et a été retirée.

Classement des interruptions distribution (date d'apparition dans la semaine, tous statuts) :

- coupures dues au réseau HTB / à la production (cause contenant « HTB », « PRODUCTION »,
  « BLACK START ») : hors tableaux HTA, citées dans les faits marquants ;
- manœuvre (cause « Manœuvre ») → Manœuvre réseau HTA ;
- nature Permanent / Semi permanent / Fugitif / Délestage → la catégorie du même nom ;
- nature Coupure : cause « Travaux » → Travaux réseau HTA, sinon Autres coupures HTA ;
- autre nature (Effacement, non renseignée) → Autres coupures HTA.

Les facteurs exogènes (choc accidentel, agression, malveillance) restent dans leur catégorie
et sont totalisés à part (« dont … »). Incidents réseaux = permanents + semi-permanents +
fugitifs ; leur END comprend aussi les délestages incidents HTA (comme le modèle).
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import rapport_hebdo_repository as repo
from app.repositories.rapport_hebdo_repository import LigneHebdo
from app.services import saifi_saidi_service

PERMANENT = "permanent"
SEMI_PERMANENT = "semi_permanent"
FUGITIF = "fugitif"
DELESTAGE_HTA = "delestage_hta"
TRAVAUX_HTA = "travaux_hta"
MANOEUVRE_HTA = "manoeuvre_hta"
AUTRES_HTA = "autres_hta"
HTB_DELESTAGE = "htb_delestage"
HTB_AUTRES = "htb_autres"

CATEGORIES_HTA: tuple[tuple[str, str], ...] = (
    (PERMANENT, "Permanent"),
    (SEMI_PERMANENT, "Semi permanent"),
    (FUGITIF, "Fugitif"),
    (DELESTAGE_HTA, "Délestage incident HTA"),
    (TRAVAUX_HTA, "Travaux réseau HTA"),
    (MANOEUVRE_HTA, "Manœuvre réseau HTA"),
    (AUTRES_HTA, "Autres coupures HTA (circonstancielle, …)"),
)
CATEGORIES_HTB: tuple[tuple[str, str], ...] = (
    (HTB_DELESTAGE, "Délestage incidents et manque de production"),
    (HTB_AUTRES, "Autres interruptions dues au HTB (travaux, incidents)"),
)
INCIDENTS = (PERMANENT, SEMI_PERMANENT, FUGITIF)
INCIDENTS_END = (PERMANENT, SEMI_PERMANENT, FUGITIF, DELESTAGE_HTA)
JOURS = ("Samedi", "Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi")
DAKAR, REGIONS = "Dakar", "Régions"

_CAUSES_EXOGENES = ("CHOC ACCIDENTEL", "AGRESSION", "MALVEILLANCE", "FACTEURS EXOGENES", "FACTEUR EXOGENE")
_SEUIL_INCIDENT_HTB = 20
_MAX_FAITS_PAR_ZONE = 12  # interruptions HTA dans la journée pour parler d'un incident HTB


def _norme(texte: str | None) -> str:
    if not texte:
        return ""
    sans_accent = unicodedata.normalize("NFKD", texte.replace("œ", "oe").replace("Œ", "OE"))
    return "".join(c for c in sans_accent if not unicodedata.combining(c)).upper().strip()


def categorie(ligne: LigneHebdo) -> str:
    cause = _norme(ligne.cause)
    nature = _norme(ligne.nature)
    if "HTB" in cause or "PRODUCTION" in cause or "BLACK START" in cause:
        return HTB_DELESTAGE if ("PRODUCTION" in cause or "DELESTAGE" in nature) else HTB_AUTRES
    if "MANOEUVRE" in cause:
        return MANOEUVRE_HTA
    if nature.startswith("SEMI"):
        return SEMI_PERMANENT
    if nature.startswith("PERMANENT"):
        return PERMANENT
    if nature.startswith("FUGITIF"):
        return FUGITIF
    if nature.startswith("DELESTAGE"):
        return DELESTAGE_HTA
    if "TRAVAUX" in cause:
        return TRAVAUX_HTA
    return AUTRES_HTA


def est_exogene(ligne: LigneHebdo) -> bool:
    cause = _norme(ligne.cause)
    return any(c in cause for c in _CAUSES_EXOGENES)


def zone(ligne: LigneHebdo) -> str:
    return DAKAR if "DAKAR" in _norme(ligne.region_libelle) else REGIONS


def semaine_samedi_vendredi(reference: date) -> tuple[date, date]:
    """Dernière semaine complète samedi → vendredi avant `reference` (le samedi : la veille)."""
    recul = (reference.weekday() - 4) % 7 or 7
    vendredi = reference - timedelta(days=recul)
    return vendredi - timedelta(days=6), vendredi


def numero_semaine(vendredi: date) -> int:
    return vendredi.isocalendar()[1]


@dataclass
class Compte:
    nombre: int = 0
    end_mwh: float = 0.0

    def ajouter(self, ligne: LigneHebdo) -> None:
        self.nombre += 1
        self.end_mwh += ligne.end_mwh


@dataclass
class StatsSemaine:
    debut: date
    fin: date
    numero: int
    par_categorie: dict[str, Compte] = field(default_factory=lambda: defaultdict(Compte))
    par_service: dict[tuple[str, str], Compte] = field(default_factory=lambda: defaultdict(Compte))
    end_service: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    par_jour: dict[tuple[int, str, str], Compte] = field(default_factory=lambda: defaultdict(Compte))
    par_jour_service: dict[tuple[int, str, str], Compte] = field(default_factory=lambda: defaultdict(Compte))
    exogenes: Compte = field(default_factory=Compte)
    exogenes_jour: dict[tuple[int, str], Compte] = field(default_factory=lambda: defaultdict(Compte))
    saifi: float = 0.0
    saidi_h: float = 0.0
    clients_impactes: int = 0
    clients_reference: int = 0

    @property
    def total_hta(self) -> Compte:
        total = Compte()
        for cle, _ in CATEGORIES_HTA:
            c = self.par_categorie.get(cle, Compte())
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total

    def somme(self, categories: tuple[str, ...]) -> Compte:
        total = Compte()
        for cle in categories:
            c = self.par_categorie.get(cle, Compte())
            total.nombre += c.nombre
            total.end_mwh += c.end_mwh
        return total


@dataclass
class FaitsMarquants:
    majeurs: list[str] = field(default_factory=list)
    dakar: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)


@dataclass
class RapportHebdoData:
    semaine: StatsSemaine
    precedente: StatsSemaine
    services: list[str]
    cumul_end_mwh: float
    cumul_end_exogenes_mwh: float
    cumul_nombre_exogenes: int
    cumul_saifi: float
    cumul_saidi_h: float
    cumul_clients_impactes: int
    cumul_clients_reference: int
    objectif_end_annuel_mwh: float | None
    faits: FaitsMarquants
    introduction: str
    paragraphes_semaines: list[str]
    dominance: str

    @property
    def cible_hebdo_mwh(self) -> float | None:
        return self.objectif_end_annuel_mwh / 52 if self.objectif_end_annuel_mwh else None

    @property
    def cible_cumul_mwh(self) -> float | None:
        if not self.objectif_end_annuel_mwh:
            return None
        fin = self.semaine.fin
        jours = (date(fin.year, 12, 31) - date(fin.year, 1, 1)).days + 1
        return self.objectif_end_annuel_mwh * fin.timetuple().tm_yday / jours


# --------------------------------------------------------------------------------------
# Mise en forme commune (Word, PDF, Excel)
# --------------------------------------------------------------------------------------

def fmt_nombre(valeur: float, decimales: int = 0) -> str:
    texte = f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte


def fmt_mwh(valeur: float) -> str:
    return fmt_nombre(valeur, 3)


def fmt_duree_h(heures: float) -> str:
    secondes = int(round(heures * 3600))
    return f"{secondes // 3600}:{secondes % 3600 // 60:02d}:{secondes % 60:02d}"


def fmt_date_longue(jour: date) -> str:
    mois = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre")
    return f"{jour.day:02d} {mois[jour.month - 1]} {jour.year}"


def ecart_pct(actuel: float, precedent: float) -> float | None:
    if not precedent:
        return None
    return (actuel - precedent) * 100.0 / precedent


def titre_semaine(data: RapportHebdoData) -> str:
    s = data.semaine
    return f"S{s.numero:02d}-{s.fin.year} du {fmt_date_longue(s.debut)} au {fmt_date_longue(s.fin)}"


# --------------------------------------------------------------------------------------
# Calculs
# --------------------------------------------------------------------------------------

def _stats(lignes: list[LigneHebdo], debut: date, fin: date) -> StatsSemaine:
    stats = StatsSemaine(debut=debut, fin=fin, numero=numero_semaine(fin))
    for ligne in lignes:
        cat = categorie(ligne)
        stats.par_categorie[cat].ajouter(ligne)
        jour = (ligne.date_apparition.date() - debut).days
        z = zone(ligne)
        if 0 <= jour < 7:
            stats.par_jour[(jour, cat, z)].ajouter(ligne)
        if cat in (HTB_DELESTAGE, HTB_AUTRES):
            continue
        code = ligne.service_code or "—"
        stats.par_service[(cat, code)].ajouter(ligne)
        if 0 <= jour < 7:
            stats.par_jour_service[(jour, cat, code)].ajouter(ligne)
        stats.end_service[code] += ligne.end_mwh
        if est_exogene(ligne):
            stats.exogenes.ajouter(ligne)
            if 0 <= jour < 7:
                stats.exogenes_jour[(jour, z)].ajouter(ligne)
    return stats


def _bornes(debut: date, fin: date) -> tuple[datetime, datetime]:
    return datetime(debut.year, debut.month, debut.day), datetime(fin.year, fin.month, fin.day) + timedelta(days=1)


async def _semaine(db: AsyncSession, debut: date, fin: date, service_ids: list[int]) -> tuple[StatsSemaine, list[LigneHebdo]]:
    d, f = _bornes(debut, fin)
    lignes = await repo.lister_interruptions(db, d, f)
    stats = _stats(lignes, debut, fin)
    calcul = await saifi_saidi_service.calculer_perimetre(db, service_ids, d, f)
    stats.saifi, stats.saidi_h = calcul.saifi, calcul.saidi
    stats.clients_reference = calcul.total_clients_reference
    stats.clients_impactes = round(calcul.saifi * calcul.total_clients_reference)
    return stats, lignes


def _ordre_services(stats: StatsSemaine, services: list[tuple[int, str, str | None]]) -> list[str]:
    presents = {code for (_, code) in stats.par_service}
    region = {code: lib for _, code, lib in services}
    codes = sorted(presents, key=lambda c: (0 if "DAKAR" in _norme(region.get(c)) else 1, c))
    return codes


def _heure(valeur: datetime | None) -> str:
    return valeur.strftime("%Hh%M") if valeur else "?"


def _faits(lignes: list[LigneHebdo], stats: StatsSemaine) -> FaitsMarquants:
    faits = FaitsMarquants()
    exogenes = [ligne for ligne in lignes if est_exogene(ligne) and categorie(ligne) not in (HTB_DELESTAGE, HTB_AUTRES)]
    if exogenes:
        dakar = sum(1 for ligne in exogenes if zone(ligne) == DAKAR)
        faits.majeurs.append(
            f"{len(exogenes)} interruption(s) due(s) aux facteurs exogènes (choc accidentel, agression…) : "
            f"{dakar} à Dakar, {len(exogenes) - dakar} en régions"
        )
    par_jour: dict[date, list[LigneHebdo]] = defaultdict(list)
    for ligne in lignes:
        if categorie(ligne) in (HTB_DELESTAGE, HTB_AUTRES):
            par_jour[ligne.date_apparition.date()].append(ligne)
    for jour, groupe in sorted(par_jour.items()):
        if len(groupe) >= _SEUIL_INCIDENT_HTB:
            debut = min(g.date_apparition for g in groupe)
            remises = [g.date_remise for g in groupe if g.date_remise]
            fin = max(remises) if remises else None
            faits.majeurs.append(
                f"Incident réseau HTB / production du {jour:%d/%m/%Y} : {len(groupe)} interruptions côté HTA "
                f"(Dakar et régions) de {_heure(debut)} à {_heure(fin)}"
            )
    hta = [ligne for ligne in lignes if categorie(ligne) not in (HTB_DELESTAGE, HTB_AUTRES) and ligne.end_mwh > 0]
    for ligne in sorted(hta, key=lambda x: x.end_mwh, reverse=True)[:3]:
        faits.majeurs.append(
            f"Plus forte END : {ligne.feeder or 'feeder non renseigné'} ({ligne.service_code or '—'}) le "
            f"{ligne.date_apparition:%d/%m à %Hh%M}, {ligne.nature or 'nature non renseignée'}, "
            f"cause {ligne.cause or 'non renseignée'} — {fmt_mwh(ligne.end_mwh)} MWh"
        )
    for ligne in exogenes:
        lieu = f" — {ligne.localisation}" if ligne.localisation else ""
        texte = (
            f"{(ligne.cause or 'Facteur exogène').capitalize()} sur {ligne.feeder or 'feeder non renseigné'} "
            f"({ligne.service_code or '—'}) le {ligne.date_apparition:%d/%m à %Hh%M}{lieu}"
        )
        (faits.dakar if zone(ligne) == DAKAR else faits.regions).append(texte)
    for liste in (faits.dakar, faits.regions):
        if len(liste) > _MAX_FAITS_PAR_ZONE:
            reste = len(liste) - _MAX_FAITS_PAR_ZONE
            del liste[_MAX_FAITS_PAR_ZONE:]
            liste.append(f"… et {reste} autre(s) interruption(s) due(s) aux facteurs exogènes")
    return faits


def _paragraphe_semaine(stats: StatsSemaine, cible_hebdo: float | None) -> str:
    total = stats.total_hta
    inc = stats.somme(INCIDENTS)
    end_inc = stats.somme(INCIDENTS_END).end_mwh
    perm = stats.par_categorie.get(PERMANENT, Compte()).nombre
    semi = stats.par_categorie.get(SEMI_PERMANENT, Compte()).nombre
    fug = stats.par_categorie.get(FUGITIF, Compte()).nombre
    travaux = stats.par_categorie.get(TRAVAUX_HTA, Compte()).end_mwh
    autres = stats.somme((MANOEUVRE_HTA, AUTRES_HTA)).end_mwh
    texte = (
        f"Au cours de la semaine S{stats.numero:02d}, {total.nombre} interruptions de service ont été "
        f"enregistrées sur le réseau de distribution (Dakar et régions), dont {inc.nombre} incidents réseaux "
        f"({perm} permanents, {semi} semi-permanents et {fug} fugitifs), avec une END totale de "
        f"{fmt_mwh(total.end_mwh)} MWh (toutes causes confondues), dont {fmt_mwh(end_inc)} MWh liés aux "
        f"incidents réseaux (dont {fmt_mwh(stats.exogenes.end_mwh)} MWh dus aux facteurs exogènes), "
        f"{fmt_mwh(travaux)} MWh dus aux travaux HTA et {fmt_mwh(autres)} MWh dus aux autres coupures HTA "
        f"(manœuvres, coupures circonstancielles)."
    )
    if cible_hebdo:
        sens = "supérieure" if total.end_mwh > cible_hebdo else "inférieure"
        texte += f" Cette réalisation est {sens} à la valeur cible hebdomadaire de {fmt_nombre(cible_hebdo)} MWh."
    return texte


def _introduction(s: StatsSemaine, p: StatsSemaine, faits: FaitsMarquants) -> str:
    ts, tp = s.total_hta, p.total_hta
    if ts.nombre <= tp.nombre and ts.end_mwh <= tp.end_mwh:
        tendance = "une amélioration de la qualité de service"
        detail = "avec une baisse du nombre d'interruptions et de l'END"
    elif ts.nombre >= tp.nombre and ts.end_mwh >= tp.end_mwh:
        tendance = "une dégradation de la qualité de service"
        detail = "avec une hausse du nombre d'interruptions et de l'END"
    else:
        tendance = "une évolution contrastée de la qualité de service"
        sens_n = "baisse" if ts.nombre < tp.nombre else "hausse"
        sens_e = "baisse" if ts.end_mwh < tp.end_mwh else "hausse"
        detail = f"avec une {sens_n} du nombre d'interruptions et une {sens_e} de l'END"
    texte = (
        f"Il a été noté {tendance} sur les réseaux HTA par rapport à la semaine S{p.numero:02d} {detail} "
        f"({ts.nombre} interruptions contre {tp.nombre} ; {fmt_mwh(ts.end_mwh)} MWh contre {fmt_mwh(tp.end_mwh)} MWh)."
    )
    htb = [f for f in faits.majeurs if f.startswith("Incident réseau HTB")]
    if htb:
        texte += " Point saillant de la semaine : " + htb[0][0].lower() + htb[0][1:] + "."
    return texte


def _dominance(stats: StatsSemaine) -> str:
    total = sum(stats.end_service.values())
    if total <= 0:
        return ""
    parts: list[str] = []
    cumul = 0.0
    for code, end in sorted(stats.end_service.items(), key=lambda kv: kv[1], reverse=True):
        part = end * 100 / total
        parts.append(f"{code} ({part:.0f} %)")
        cumul += part
        if cumul >= 80:
            break
    return (
        "Les interruptions sont dominées cette semaine en termes d'END par : "
        + ", ".join(parts)
        + f", qui font un cumul de {cumul:.0f} %."
    )


async def collecter(db: AsyncSession, debut: date, fin: date) -> RapportHebdoData:
    """Toutes les données du rapport de la semaine [debut, fin] (samedi → vendredi)."""
    services = await repo.services_distribution(db)
    service_ids = [sid for sid, _, _ in services]
    stats, lignes = await _semaine(db, debut, fin, service_ids)
    precedente, _ = await _semaine(db, debut - timedelta(days=7), fin - timedelta(days=7), service_ids)

    debut_annee, fin_excl = datetime(fin.year, 1, 1), _bornes(debut, fin)[1]
    annee = await repo.lister_interruptions(db, debut_annee, fin_excl, detail=False)
    hta_annee = [ligne for ligne in annee if categorie(ligne) not in (HTB_DELESTAGE, HTB_AUTRES)]
    exo_annee = [ligne for ligne in hta_annee if est_exogene(ligne)]
    cumul = await saifi_saidi_service.calculer_perimetre(db, service_ids, debut_annee, fin_excl)
    objectif = await repo.objectif_end_annuel(db, fin.year)
    cible_hebdo = objectif / 52 if objectif else None

    faits = _faits(lignes, stats)
    return RapportHebdoData(
        semaine=stats,
        precedente=precedente,
        services=_ordre_services(stats, services),
        cumul_end_mwh=sum(ligne.end_mwh for ligne in hta_annee),
        cumul_end_exogenes_mwh=sum(ligne.end_mwh for ligne in exo_annee),
        cumul_nombre_exogenes=len(exo_annee),
        cumul_saifi=cumul.saifi,
        cumul_saidi_h=cumul.saidi,
        cumul_clients_impactes=round(cumul.saifi * cumul.total_clients_reference),
        cumul_clients_reference=cumul.total_clients_reference,
        objectif_end_annuel_mwh=objectif,
        faits=faits,
        introduction=_introduction(stats, precedente, faits),
        paragraphes_semaines=[_paragraphe_semaine(stats, cible_hebdo), _paragraphe_semaine(precedente, cible_hebdo)],
        dominance=_dominance(stats),
    )
