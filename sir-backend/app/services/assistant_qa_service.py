"""Assistant — réponses aux questions d'exploitation posées en français courant.

Lecture par règles, sans service externe : la question est découpée en
- une **intention** (postes les plus touchés, départs les plus perturbés, END, SAIFI/SAIDI,
  interruptions en cours ou à valider, causes, natures, durée moyenne, défauts aux 100 km,
  dernières interruptions, nombre d'interruptions) ;
- une **période** (aujourd'hui, hier, cette semaine, semaine dernière, ce mois, mois dernier,
  « en octobre », « 2025 », « les 30 derniers jours »… ; à défaut : l'année en cours) ;
- les **départs** cités (même rapprochement que la lecture des SMS : sans accents, fautes légères)
  et les **services** cités (SDDV, SDPG…).
Les chiffres viennent de la base SIRV2, dans le périmètre du compte. Une question hors de ces
intentions reçoit la liste des questions comprises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import assistant_qa_repository as repo
from app.repositories import lecture_sms_repository as sms_repo
from app.repositories.assistant_qa_repository import Filtre
from app.services import saifi_saidi_service, sig_admin_service
from app.services.lecture_sms_service import _departs, mots, sans_accents

MOIS = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6, "JUILLET": 7,
    "AOUT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11, "DECEMBRE": 12,
}
MOIS_NOMS = {v: k.capitalize().replace("Fevrier", "Février").replace("Aout", "Août").replace("Decembre", "Décembre") for k, v in MOIS.items()}

# Mots des questions qui ne sont jamais des noms de départ
_MOTS_QUESTION = {
    "POSTE", "POSTES", "PLUS", "AFFECTE", "AFFECTES", "TOUCHE", "TOUCHES", "DANS", "FEEDER", "FEEDERS",
    "DEPART", "DEPARTS", "QUEL", "QUELS", "QUELLE", "QUELLES", "COMBIEN", "NOMBRE", "INTERRUPTION",
    "INTERRUPTIONS", "COUPURE", "COUPURES", "MOIS", "SEMAINE", "ANNEE", "JOUR", "DERNIER", "DERNIERE",
    "DERNIERS", "DERNIERES", "PERTURBE", "PERTURBES", "CAUSE", "CAUSES", "NATURE", "NATURES",
    "SERVICE", "SERVICES", "ENERGIE", "DISTRIBUEE", "DUREE", "MOYENNE", "DEFAUTS", "DEFAUT",
    "VALIDER", "COURS", "DONNE", "DONNER", "LISTE", "MONTRE", "AUJOURD", "HIER", "DEPUIS",
    "CETTE", "PASSE", "PASSEE", "TOTAL", "TOTALE", "GLOBAL", "RESEAU", "SAIFI", "SAIDI",
} | set(MOIS)

_SUPERLATIF = re.compile(r"\b(PLUS (AFFECT|TOUCH|COUP|PERTURB|IMPACT|SOLLICIT|FRAPP|SOUVENT|D INTERRUPTION|DE COUPURE)\w*|TOP|CLASSEMENT|LES PLUS|LE PLUS|PRINCIPAUX|PRINCIPALES)\b")


@dataclass
class Periode:
    debut: datetime
    fin: datetime
    libelle: str


@dataclass
class Question:
    texte: str
    normalise: str
    periode: Periode
    top: int = 10
    feeders: list = field(default_factory=list)
    services: list[tuple[int, str, str]] = field(default_factory=list)


def _jour(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _mois(annee: int, mois: int) -> tuple[datetime, datetime]:
    return datetime(annee, mois, 1), datetime(annee + (mois == 12), mois % 12 + 1, 1)


def lire_periode(texte: str, aujourd_hui: date) -> Periode:
    """Période citée dans la question ; à défaut, l'année en cours (jusqu'à aujourd'hui)."""
    t = " ".join(mots(texte))
    demain = _jour(aujourd_hui + timedelta(days=1))
    if "AUJOURD" in t:
        return Periode(_jour(aujourd_hui), demain, "aujourd'hui")
    if re.search(r"\bHIER\b", t):
        h = aujourd_hui - timedelta(days=1)
        return Periode(_jour(h), _jour(aujourd_hui), f"hier ({h:%d/%m/%Y})")
    m = re.search(r"\b(\d{1,3}) DERNIERS? JOURS\b", t)
    if m:
        n = int(m.group(1))
        return Periode(_jour(aujourd_hui - timedelta(days=n - 1)), demain, f"les {n} derniers jours")
    # Semaine d'exploitation DD : samedi → vendredi
    samedi = aujourd_hui - timedelta(days=(aujourd_hui.weekday() - 5) % 7)
    if re.search(r"SEMAINE (DERNIERE|PASSEE|PRECEDENTE)", t):
        debut = samedi - timedelta(days=7)
        return Periode(_jour(debut), _jour(samedi), f"la semaine du {debut:%d/%m} au {samedi - timedelta(days=1):%d/%m}")
    if re.search(r"(CETTE|LA) SEMAINE|SEMAINE EN COURS", t):
        return Periode(_jour(samedi), demain, f"la semaine en cours (depuis le samedi {samedi:%d/%m})")
    if re.search(r"MOIS (DERNIER|PASSE|PRECEDENT)", t):
        a, mo = (aujourd_hui.year, aujourd_hui.month - 1) if aujourd_hui.month > 1 else (aujourd_hui.year - 1, 12)
        d, f = _mois(a, mo)
        return Periode(d, f, f"{MOIS_NOMS[mo].lower()} {a}")
    if re.search(r"CE MOIS|MOIS EN COURS|MOIS CI", t):
        d, _ = _mois(aujourd_hui.year, aujourd_hui.month)
        return Periode(d, demain, f"{MOIS_NOMS[aujourd_hui.month].lower()} {aujourd_hui.year} (mois en cours)")
    annee_citee = re.search(r"\b(20\d{2})\b", t)
    for nom, numero in MOIS.items():
        if re.search(rf"\b{nom}\b", t):
            annee = int(annee_citee.group(1)) if annee_citee else aujourd_hui.year
            if not annee_citee and numero > aujourd_hui.month:
                annee -= 1
            d, f = _mois(annee, numero)
            return Periode(d, min(f, demain), f"{MOIS_NOMS[numero].lower()} {annee}")
    if re.search(r"ANNEE (DERNIERE|PASSEE|PRECEDENTE)", t):
        a = aujourd_hui.year - 1
        return Periode(datetime(a, 1, 1), datetime(a + 1, 1, 1), f"l'année {a}")
    if annee_citee:
        a = int(annee_citee.group(1))
        return Periode(datetime(a, 1, 1), min(datetime(a + 1, 1, 1), demain), f"l'année {a}")
    return Periode(datetime(aujourd_hui.year, 1, 1), demain, f"l'année {aujourd_hui.year} (au {aujourd_hui:%d/%m})")


def _top(t: str, defaut: int = 10) -> int:
    m = re.search(r"\b(?:TOP|LES)\s*(\d{1,2})\b|\b(\d{1,2})\s+(?:POSTES|DEPARTS|FEEDERS|CAUSES|PREMIERS|PREMIERES)\b", t)
    if not m:
        return 1 if re.search(r"\bLE (POSTE|DEPART|FEEDER) LE PLUS\b|\bLA CAUSE LA PLUS\b", t) else defaut
    return max(1, min(int(m.group(1) or m.group(2)), 30))


def intention(t: str) -> str | None:
    """Intention de la question (texte normalisé), ou None si elle relève du scoring de risque."""
    if re.search(r"\b(RISQUE|TRAVAUX|PRIORIS|PREVENTI|MAINTENANCE|SCORE)\w*", t):
        return None
    if re.search(r"\bSAIFI|\bSAIDI", t):
        return "saifi_saidi"
    if re.search(r"\bDEFAUTS?\b", t) and "100" in t:
        return "defauts_100km"
    if re.search(r"\bEN COURS\b|NON REMIS|PAS (ENCORE )?REMIS|SANS (DATE DE )?REMISE", t):
        return "en_cours"
    if re.search(r"\b(A VALIDER|NON VALIDE|EN ATTENTE DE VALIDATION|VALIDATION)", t):
        return "a_valider"
    if re.search(r"\bCAUSES?\b", t):
        return "causes"
    if re.search(r"\bNATURES?\b|\bPERMANENT|\bFUGITI", t):
        return "natures"
    if re.search(r"\bPOSTES?\b", t) and _SUPERLATIF.search(t):
        return "postes"
    if re.search(r"\b(FEEDERS?|DEPARTS?)\b", t) and _SUPERLATIF.search(t):
        return "feeders"
    if re.search(r"\bEND\b|ENERGIE NON", t):
        return "end"
    if re.search(r"\bDUREE", t):
        return "duree"
    if re.search(r"\bDERNIER(E|ES|S)?\b", t) and re.search(r"INTERRUPTION|COUPURE|INCIDENT", t):
        return "recentes"
    if re.search(r"\bCOMBIEN\b|\bNOMBRE\b", t):
        return "nombre"
    return "resume"


def _fr(n: float, decimales: int = 0) -> str:
    texte = f"{n:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte


def _perimetre(q: Question) -> str:
    morceaux = []
    if q.feeders:
        morceaux.append("départ " + " / ".join(d.libelle for d in q.feeders))
    if q.services:
        morceaux.append("service " + " / ".join(s[1] for s in q.services))
    return (" — " + ", ".join(morceaux)) if morceaux else ""


AIDE = (
    "Je réponds aux questions sur les interruptions de distribution, par exemple :\n"
    "- « Le poste le plus affecté du feeder Yeumbeul 30 kV ce mois ? »\n"
    "- « Top 5 des départs les plus perturbés en octobre »\n"
    "- « END du mois dernier pour le service SDDV »\n"
    "- « SAIFI et SAIDI de 2026 »\n"
    "- « Combien d'interruptions en cours ? » / « Combien à valider ? »\n"
    "- « Principales causes cette semaine », « Répartition par nature »\n"
    "- « Durée moyenne des coupures le mois dernier »\n"
    "- « Défauts aux 100 km cette année »\n"
    "- « Dernières interruptions du départ Hann »\n"
    "- « Quels travaux prioriser ? » (scores de risque)\n"
    "Sans période citée, je prends l'année en cours."
)


async def comprendre(db: AsyncSession, texte: str, aujourd_hui: date | None = None) -> Question:
    jour = aujourd_hui or date.today()
    t = " ".join(mots(texte))
    departs = await sms_repo.lister_departs(db)
    filtre_mots = " ".join(m for m in mots(texte) if m not in _MOTS_QUESTION)
    trouves, score = _departs(filtre_mots, departs) if filtre_mots else ([], 0.0)
    services = [s for s in await repo.lister_services(db) if s[1] and re.search(rf"\b{re.escape(sans_accents(s[1]))}\b", t)]
    return Question(
        texte=texte,
        normalise=t,
        periode=lire_periode(texte, jour),
        top=_top(t),
        feeders=trouves if score >= 0.86 else [],
        services=services,
    )


def _filtre(q: Question, service_ids: list[int] | None) -> Filtre:
    ids = service_ids
    if q.services:
        cites = [s[0] for s in q.services]
        ids = [i for i in cites if service_ids is None or i in service_ids] or [-1]
    return Filtre(
        debut=q.periode.debut,
        fin=q.periode.fin,
        service_ids=ids,
        feeder_ids=[d.id for d in q.feeders] or None,
    )


async def repondre(
    db: AsyncSession,
    user: Utilisateur,
    texte: str,
    service_ids: list[int] | None,
    aujourd_hui: date | None = None,
) -> str | None:
    """Réponse chiffrée ; None quand la question relève des scores de risque (travaux, priorités)."""
    q = await comprendre(db, texte, aujourd_hui)
    quoi = intention(q.normalise)
    if quoi is None:
        return None
    f = _filtre(q, service_ids)
    p = q.periode.libelle + _perimetre(q)

    if quoi == "postes":
        rows = await repo.postes_plus_impactes(db, f, q.top)
        if not rows:
            return f"Aucun poste impacté enregistré sur {p}."
        if q.top == 1:
            r = rows[0]
            return (
                f"Poste le plus affecté sur {p} : **{r.poste}**"
                f"{f' (départ {r.feeder})' if r.feeder and not q.feeders else ''} — "
                f"{r.nombre} interruption(s), {_fr(r.clients or 0)} coupures-clients, {_fr(r.heures or 0, 1)} h de coupure."
            )
        lignes = [f"Postes les plus affectés sur {p} :"]
        lignes += [
            f"{i}. {r.poste}{f' ({r.feeder})' if r.feeder and not q.feeders else ''} — {r.nombre} interruption(s), "
            f"{_fr(r.clients or 0)} coupures-clients, {_fr(r.heures or 0, 1)} h"
            for i, r in enumerate(rows, 1)
        ]
        return "\n".join(lignes)

    if quoi == "feeders":
        rows = await repo.feeders_plus_perturbes(db, f, q.top)
        if not rows:
            return f"Aucune interruption sur {p}."
        lignes = [f"Départs les plus perturbés sur {p} (hors force majeure) :"]
        lignes += [
            f"{i}. {r.feeder}{f' ({r.poste_source})' if r.poste_source else ''} — {r.nombre} interruption(s), "
            f"END {_fr((r.end_mwh or 0) * 1000)} kWh, {_fr((r.minutes or 0) / 60, 1)} h cumulées"
            for i, r in enumerate(rows, 1)
        ]
        return "\n".join(lignes)

    if quoi == "end":
        mwh, nb = await repo.end_mwh(db, f)
        return (
            f"END sur {p} : **{_fr(mwh, 1)} MWh** ({_fr(mwh * 1000)} kWh), sur {nb} interruption(s) remises "
            "dans la période, clôturées ou validées, hors force majeure."
        )

    if quoi == "saifi_saidi":
        if q.feeders:
            return "SAIFI et SAIDI se calculent sur un périmètre (national, région, service), pas sur un départ seul."
        ids = f.service_ids if f.service_ids is not None else [s[0] for s in await repo.lister_services(db)]
        calcul = await saifi_saidi_service.calculer_perimetre(db, ids, f.debut, f.fin)
        return (
            f"Sur {p} : **SAIFI {_fr(calcul.saifi or 0, 3)}** interruptions par client, "
            f"**SAIDI {_fr(calcul.saidi or 0, 3)} h** par client (formule SENELEC, interruptions apparues dans la période)."
        )

    if quoi == "en_cours":
        nb = await repo.compter(db, f, statut="en_cours", sans_periode=True)
        rows = await repo.interruptions_recentes(db, f, 5, en_cours=True)
        lignes = [f"**{nb} interruption(s) en cours**{_perimetre(q)} (statut « en cours », toutes dates)."]
        if rows:
            lignes.append("Les plus récentes :")
            lignes += [f"- n° {r.numero_interruption} — {r.feeder or '?'} depuis le {r.date_apparition:%d/%m/%Y %H:%M}" for r in rows]
        return "\n".join(lignes)

    if quoi == "a_valider":
        nb = await repo.compter(db, f, statut="cloture", sans_periode=True)
        nb_periode = await repo.compter(db, f, statut="cloture")
        return f"**{nb} interruption(s) clôturée(s) à valider**{_perimetre(q)}, dont {nb_periode} apparue(s) sur {q.periode.libelle}."

    if quoi == "causes":
        rows = await repo.causes(db, f, q.top if q.top != 10 else 5)
        total = await repo.compter(db, f)
        if not rows:
            return f"Aucune interruption sur {p}."
        lignes = [f"Principales causes sur {p} ({total} interruptions) :"]
        lignes += [f"{i}. {r.libelle} — {r.nombre} ({_fr(100 * r.nombre / max(total, 1), 1)} %)" for i, r in enumerate(rows, 1)]
        return "\n".join(lignes)

    if quoi == "natures":
        rows = await repo.par_nature(db, f)
        total = sum(r.nombre for r in rows)
        if not rows:
            return f"Aucune interruption sur {p}."
        lignes = [f"Interruptions par nature sur {p} ({total}) :"]
        lignes += [f"- {r.libelle} : {r.nombre} ({_fr(100 * r.nombre / max(total, 1), 1)} %)" for r in rows]
        return "\n".join(lignes)

    if quoi == "duree":
        moyenne, nb = await repo.duree_moyenne_minutes(db, f)
        if moyenne is None:
            return f"Aucune durée enregistrée sur {p}."
        return f"Durée moyenne des interruptions sur {p} : **{_fr(moyenne)} min** ({_fr(moyenne / 60, 2)} h), sur {nb} interruption(s)."

    if quoi == "defauts_100km":
        d = await sig_admin_service.defauts_100km(
            db, user, annee=q.periode.debut.year, mois=q.periode.debut.month if (q.periode.fin - q.periode.debut).days <= 31 else None
        )
        g = d.global_
        lignes = [
            f"Défauts aux 100 km sur {q.periode.libelle} (réseau SIG, hors force majeure) : "
            f"**{_fr(g.defauts_100km or 0, 1)}** ({g.defauts} défauts / {_fr(g.longueur_km)} km), "
            f"dont permanents {_fr(g.permanents_100km or 0, 1)}."
        ]
        lignes += [f"- {s.libelle} : {_fr(s.defauts_100km or 0, 1)}" for s in d.par_service[:6]]
        lignes.append("Détail par feeder et par nature : Administration → SIG → Défauts aux 100 km.")
        return "\n".join(lignes)

    if quoi == "recentes":
        rows = await repo.interruptions_recentes(db, f, min(q.top, 10) if q.top != 10 else 5)
        if not rows:
            return f"Aucune interruption sur {p}."
        lignes = [f"Dernières interruptions{_perimetre(q)} :"]
        for r in rows:
            fin = f"remise {r.date_remise:%d/%m %H:%M}" if r.date_remise else "en cours"
            lignes.append(f"- n° {r.numero_interruption} — {r.feeder or '?'} — {r.date_apparition:%d/%m/%Y %H:%M}, {fin}{f' — {r.cause}' if r.cause else ''}")
        return "\n".join(lignes)

    if quoi == "nombre" or (quoi == "resume" and (q.feeders or q.services)):
        nb = await repo.compter(db, f)
        mwh, _ = await repo.end_mwh(db, f)
        lignes = [f"Sur {p} : **{nb} interruption(s)**, END {_fr(mwh, 1)} MWh."]
        if q.feeders or quoi == "resume":
            postes = await repo.postes_plus_impactes(db, f, 3)
            if postes:
                lignes.append("Postes les plus touchés : " + ", ".join(f"{r.poste} ({r.nombre})" for r in postes) + ".")
            causes = await repo.causes(db, f, 3)
            if causes:
                lignes.append("Principales causes : " + ", ".join(f"{r.libelle} ({r.nombre})" for r in causes) + ".")
        return "\n".join(lignes)

    return AIDE
