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
