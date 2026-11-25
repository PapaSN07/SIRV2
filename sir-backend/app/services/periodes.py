"""Périodes d'exploitation SENELEC.

Semaine SENELEC : du samedi au vendredi, numérotée par la semaine ISO de son vendredi
(S43 2026 = samedi 17/10 → vendredi 23/10). Même règle que le rapport hebdo DD, la synthèse
SAIFI/SAIDI de l'accueil (``indicateurs_service.periodes_synthese``) et le frontend
(``shared/utils/semaine-senelec.ts``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

_VENDREDI = 4  # date.weekday() : lundi = 0


@dataclass(frozen=True)
class SemaineSenelec:
    numero: int
    annee: int
    debut: date  # samedi
    fin: date  # vendredi, inclus


def semaine_senelec(jour: date) -> SemaineSenelec:
    """Semaine SENELEC qui contient ``jour``."""
    vendredi = jour + timedelta(days=(_VENDREDI - jour.weekday()) % 7)
    iso = vendredi.isocalendar()
    return SemaineSenelec(numero=iso.week, annee=iso.year, debut=vendredi - timedelta(days=6), fin=vendredi)


def semaine_senelec_passee(aujourd_hui: date) -> SemaineSenelec:
    """Dernière semaine terminée : son vendredi est strictement avant ``aujourd_hui``."""
    return semaine_senelec(semaine_senelec(aujourd_hui).debut - timedelta(days=1))


def _fin_de_mois(jour: date) -> date:
    suivant = date(jour.year + (jour.month == 12), jour.month % 12 + 1, 1)
    return suivant - timedelta(days=1)


def periode_precedente(debut: date, fin: date) -> tuple[date, date]:
    """Période de comparaison : semaine SENELEC, mois ou année précédents, sinon même durée juste avant."""
    semaine = semaine_senelec(debut)
    if semaine.debut == debut and semaine.fin == fin:
        return debut - timedelta(days=7), fin - timedelta(days=7)
    if (debut.month, debut.day) == (1, 1) and (fin.year, fin.month, fin.day) == (debut.year, 12, 31):
        return date(debut.year - 1, 1, 1), date(debut.year - 1, 12, 31)
    if debut.day == 1 and fin == _fin_de_mois(debut):
        fin_precedente = debut - timedelta(days=1)
        return fin_precedente.replace(day=1), fin_precedente
    jours = (fin - debut).days + 1
    return debut - timedelta(days=jours), debut - timedelta(days=1)
