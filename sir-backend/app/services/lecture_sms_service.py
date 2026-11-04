"""Service — lecture d'un SMS en texte libre pour pré-remplir la saisie d'une interruption.

Au moment où un SMS part de SIRV2, son texte est lu : type d'événement (déclenchement / coupure
ou remise), départ, heures, cause. L'écran de saisie s'ouvre pré-rempli ; l'agent vérifie et
enregistre (aucune interruption n'est créée sans confirmation).

La lecture est faite par des règles (pas de service externe) : mots-clés de l'exploitation,
heures « 10h15 » / « 10:15 », dates « 04/11 », départs et causes rapprochés des référentiels
SIRV2 (sans accents ni ponctuation, fautes de frappe légères tolérées).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import lecture_sms_repository as repo
from app.repositories.lecture_sms_repository import CauseRef, DepartRef
from app.schemas.lecture_sms import DepartReconnu, InterruptionEnCours, LectureSmsResponse

# Mots qui annoncent une remise (testés avant l'apparition : « remis sous tension »)
_REMISE = re.compile(
    r"\b(REMIS|REMISE|REMIZ|RETABLI\w*|RETAB\w*|REALIM\w*|REPRIS\w*|RESTITU\w*|RECONNECT\w*|"
    r"REFERM\w*|SOUS TENSION|RENVOI DE TENSION|FIN (D INCIDENT|DE COUPURE|TRAVAUX|DES TRAVAUX))\b"
)
_APPARITION = re.compile(
    r"\b(DECLENCH\w*|DECL|DECLT|DCL|DCLT|COUPURE\w*|COUPE|COUPEE|INCIDENT\w*|PANNE\w*|"
    r"HORS TENSION|DEFAUT\w*|OUVERTURE|OUVERT|MANQUE DE TENSION|DELEST\w*|MANOEUVRE\w*|"
    r"MANOEUV\w*|TRAVAUX|CONSIGNATION|CONSIGNE|ISOLE\w*|ISOLEMENT)\b"
)
_PROGRAMME = re.compile(r"\b(PROGRAMM\w*|TRAVAUX|MANOEUVRE\w*|MANOEUV\w*|CONSIGN\w*|ENTRETIEN|ELAGAGE)\b")
# Mots placés devant un nom de départ / poste source (ne font jamais partie du nom)
_AVANT_DEPART = {"DEP", "DEPART", "DEPARTS", "DPT", "FEEDER", "FDR", "DU", "SUR", "AU"}
_AVANT_POSTE = {"PS", "POSTE", "SOURCE", "P", "PST"}
# « 10h15 », « 10 H 15 », « 10:15 », « 10h » ; pas « 10 HANN » (H suivi d'un nom)
_HEURE = re.compile(r"(?<![\d/])([01]?\d|2[0-3])\s*(?:HEURES?|H|:)\s*([0-5]\d)?\s*(?:MN|MIN)?(?![A-Z\d/])")
_DATE = re.compile(r"(?<![\d:])([0-3]?\d)[/-]([01]?\d)(?:[/-](\d{2,4}))?(?![\d:])")
_SEUIL_APPROCHE = 0.86
_FUTUR_TOLERE = timedelta(minutes=30)


def sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().upper()


def cle(texte: str) -> str:
    """Nom comparable : majuscules, sans accents, espaces ni ponctuation."""
    return re.sub(r"[^A-Z0-9]", "", sans_accents(texte))


def mots(texte: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", sans_accents(texte))


@dataclass
class Lecture:
    evenement: str = "inconnu"
    date_apparition: datetime | None = None
    date_remise: datetime | None = None
    departs: list[DepartRef] = field(default_factory=list)
    depart_score: float = 0.0
    cause: CauseRef | None = None
    is_programme: bool = False
    champs: list[str] = field(default_factory=list)

    @property
    def confiance(self) -> float:
        if self.evenement == "inconnu":
            return 0.0
        score = 0.3
        if len(self.departs) == 1:
            score += 0.4 * self.depart_score
        elif self.departs:
            score += 0.15
        if self.date_apparition or self.date_remise:
            score += 0.2
        if self.cause:
            score += 0.1
        return round(min(score, 1.0), 2)


def _evenement(texte: str) -> tuple[str, int | None, int | None]:
    """(type, position du mot d'apparition, position du mot de remise)."""
    t = " ".join(mots(texte))
    remise = _REMISE.search(t)
    apparition = _APPARITION.search(t)
    # « mis hors tension » / « sous tension » : un seul des deux peut être vrai au même endroit
    if remise and apparition and remise.group(0) == "SOUS TENSION" and "HORS TENSION" in t:
        remise = None
    if apparition:
        return "apparition", apparition.start(), remise.start() if remise else None
    if remise:
        return "remise", None, remise.start()
    return "inconnu", None, None


def _jour(texte: str, maintenant: datetime) -> date | None:
    m = _DATE.search(sans_accents(texte))
    if not m:
        return None
    jour, mois = int(m.group(1)), int(m.group(2))
    annee = int(m.group(3)) if m.group(3) else maintenant.year
    if annee < 100:
        annee += 2000
    try:
        d = date(annee, mois, jour)
    except ValueError:
        return None
    if not m.group(3) and d > maintenant.date() + timedelta(days=1):
        d = d.replace(year=annee - 1)  # « 31/12 » lu le 2 janvier
    return d


def _heures(texte: str) -> list[tuple[int, int, int]]:
    """(heure, minute, position) dans l'ordre du texte."""
    t = sans_accents(texte)
    return [(int(m.group(1)), int(m.group(2) or 0), m.start()) for m in _HEURE.finditer(t)]


def _horodatage(jour: date | None, heure: int, minute: int, maintenant: datetime) -> datetime:
    base = jour or maintenant.date()
    valeur = datetime(base.year, base.month, base.day, heure, minute)
    if jour is None and valeur > maintenant + _FUTUR_TOLERE:
        valeur -= timedelta(days=1)  # « 23h50 » envoyé après minuit
    return valeur


def _proche(a: str, b: str) -> float:
    if abs(len(a) - len(b)) > 2 or a[:1] != b[:1]:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _fenetres(liste: list[str], taille_max: int = 5) -> list[tuple[int, int, str]]:
    """(début, fin, clé) de chaque suite de 1 à taille_max mots."""
    return [
        (i, j, "".join(liste[i:j]))
        for i in range(len(liste))
        for j in range(i + 1, min(i + taille_max, len(liste)) + 1)
    ]


def _departs(texte: str, departs: list[DepartRef]) -> tuple[list[DepartRef], float]:
    """Départs nommés dans le texte : nom exact (ou code) d'abord, puis nom proche (faute de frappe).

    Un nom court (moins de 4 caractères) n'est retenu que juste après « départ » / « DEP ».
    À noms égaux, le poste source cité dans le texte départage.
    """
    liste = mots(texte)
    par_cle: dict[str, list[DepartRef]] = {}
    for d in departs:
        for k in {cle(d.libelle), cle(d.code)}:
            if k:
                par_cle.setdefault(k, []).append(d)
    postes_cites = {k for _, _, k in _fenetres([m for m in liste if m not in _AVANT_POSTE], 4) if len(k) >= 3}

    meilleurs: list[tuple[float, int, list[DepartRef]]] = []
    for i, j, k in _fenetres(liste):
        if liste[i] in _AVANT_DEPART or liste[j - 1] in _AVANT_DEPART:
            continue
        apres_depart = i > 0 and liste[i - 1] in {"DEP", "DEPART", "DPT", "FEEDER", "FDR"}
        if len(k) < 4 and not apres_depart:
            continue
        trouves = par_cle.get(k)
        score = 1.0
        if trouves is None and len(k) >= 5 and j - i <= 3:
            proches = [(c, _proche(k, c)) for c in par_cle]
            proches = [(c, s) for c, s in proches if s >= _SEUIL_APPROCHE]
            if proches:
                c, score = max(proches, key=lambda cs: cs[1])
                trouves = par_cle[c]
        if trouves:
            bonus = 0.05 if apres_depart else 0.0
            meilleurs.append((score + bonus, len(k), trouves))
    if not meilleurs:
        return [], 0.0
    score, _, trouves = max(meilleurs, key=lambda m: (m[0], m[1]))
    if len(trouves) > 1:
        cites = [d for d in trouves if cle(d.poste_source_libelle) in postes_cites]
        trouves = cites or trouves
    uniques = list({d.id: d for d in trouves}.values())
    return uniques, min(score, 1.0)


def _cause(texte: str, causes: list[CauseRef]) -> CauseRef | None:
    """Cause dont le libellé complet figure dans le texte (le plus long l'emporte)."""
    t = " " + " ".join(mots(texte)) + " "
    candidates = [c for c in causes if len(cle(c.libelle)) >= 4 and f" {' '.join(mots(c.libelle))} " in t]
    return max(candidates, key=lambda c: len(c.libelle), default=None)


def analyser(
    texte: str,
    departs: list[DepartRef],
    causes: list[CauseRef],
    maintenant: datetime,
) -> Lecture:
    """Lecture pure (sans base) : testable sur des SMS d'exemple."""
    lecture = Lecture()
    evenement, pos_apparition, pos_remise = _evenement(texte)
    lecture.evenement = evenement
    if evenement == "inconnu":
        return lecture

    jour = _jour(texte, maintenant)
    heures = _heures(texte)
    if evenement == "apparition":
        if heures:
            h, m, _ = heures[0]
            lecture.date_apparition = _horodatage(jour, h, m, maintenant)
            lecture.champs.append("date_apparition")
        # « Déclenchement … 10h15, remis à 10h40 » : deuxième heure = remise
        if pos_remise is not None and pos_apparition is not None and pos_remise > pos_apparition and len(heures) > 1:
            h, m, _ = heures[1]
            remise = _horodatage(jour, h, m, maintenant)
            if lecture.date_apparition and remise < lecture.date_apparition:
                remise += timedelta(days=1)
            lecture.date_remise = remise
            lecture.champs.append("date_remise")
        lecture.is_programme = bool(_PROGRAMME.search(" ".join(mots(texte))))
    elif heures:
        h, m, _ = heures[-1]
        lecture.date_remise = _horodatage(jour, h, m, maintenant)
        lecture.champs.append("date_remise")

    lecture.departs, lecture.depart_score = _departs(texte, departs)
    if lecture.departs:
        lecture.champs.append("depart")
    lecture.cause = _cause(texte, causes)
    if lecture.cause:
        lecture.champs.append("cause")
    return lecture


def _region_du_compte(user: Utilisateur) -> int | None:
    """Région imposée par le compte (BCC → Dakar, BRC → Régions), None pour un compte national."""
    from app.services.interruption_distribution_service import _read_scope

    try:
        scope = _read_scope(user)
    except HTTPException:
        return None
    return scope.region_id if scope is not None else None


def _depart_reconnu(d: DepartRef) -> DepartReconnu:
    return DepartReconnu(
        id=d.id,
        libelle=d.libelle,
        poste_source_id=d.poste_source_id,
        poste_source_libelle=d.poste_source_libelle,
        region_id=d.region_id,
    )


async def lire(db: AsyncSession, user: Utilisateur, texte: str) -> LectureSmsResponse:
    departs = await repo.lister_departs(db)
    causes = await repo.lister_causes_distribution(db)
    lecture = analyser(texte, departs, causes, datetime.now())

    region = _region_du_compte(user)
    possibles = lecture.departs
    hors_perimetre = False
    if region is not None and possibles:
        dans_region = [d for d in possibles if d.region_id in (region, None)]
        hors_perimetre = not dans_region
        possibles = dans_region or possibles
    depart = possibles[0] if len(possibles) == 1 else None

    en_cours = None
    if depart is not None and lecture.evenement != "inconnu":
        ref = await repo.interruption_en_cours_du_depart(db, depart.id)
        if ref is not None:
            en_cours = InterruptionEnCours(
                id=ref.id, numero_interruption=ref.numero_interruption, date_apparition=ref.date_apparition
            )

    return LectureSmsResponse(
        texte=texte,
        evenement=lecture.evenement,  # type: ignore[arg-type]
        date_apparition=lecture.date_apparition,
        date_remise=lecture.date_remise,
        depart=_depart_reconnu(depart) if depart else None,
        departs_possibles=[_depart_reconnu(d) for d in possibles[:8]] if depart is None else [],
        cause_id=lecture.cause.id if lecture.cause else None,
        cause_libelle=lecture.cause.libelle if lecture.cause else None,
        is_programme=lecture.is_programme,
        interruption_en_cours=en_cours,
        hors_perimetre=hors_perimetre,
        champs_reconnus=lecture.champs,
        confiance=lecture.confiance,
    )
