"""Période de comparaison de la Vue d'ensemble « Suivi incidents » (spécification étape 3, §8).

``app.services.periodes.periode_precedente(debut, fin) -> tuple[date, date]`` :

- semaine SENELEC (samedi → vendredi) → semaine SENELEC précédente ;
- mois civil complet → mois précédent complet ;
- année civile → année précédente ;
- sinon → même nombre de jours, juste avant ``debut``.

Écrits avant le code (circuit « tests avant le code »).
"""

from datetime import date

import pytest


def _precedente(debut: date, fin: date) -> tuple[date, date]:
    from app.services.periodes import periode_precedente

    return periode_precedente(debut, fin)


# --------------------------------------------------------------------------------------------
# Semaine SENELEC
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debut", "fin", "attendu"),
    [
        # S47 2026 → S46 2026
        (date(2026, 11, 14), date(2026, 11, 20), (date(2026, 11, 7), date(2026, 11, 13))),
        # S43 2026 → S42 2026
        (date(2026, 10, 17), date(2026, 10, 23), (date(2026, 10, 10), date(2026, 10, 16))),
        # semaine à cheval sur deux années : samedi 02/01/2027 → vendredi 08/01/2027
        (date(2027, 1, 2), date(2027, 1, 8), (date(2026, 12, 26), date(2027, 1, 1))),
    ],
)
def test_semaine_senelec_semaine_precedente(debut: date, fin: date, attendu: tuple[date, date]) -> None:
    """Samedi → vendredi : la semaine SENELEC qui précède."""
    assert _precedente(debut, fin) == attendu


def test_retourne_un_tuple_de_dates() -> None:
    """Contrat : tuple (debut, fin) de ``date``, fin incluse."""
    resultat = _precedente(date(2026, 11, 14), date(2026, 11, 20))
    assert isinstance(resultat, tuple) and len(resultat) == 2
    assert all(type(d) is date for d in resultat)


# --------------------------------------------------------------------------------------------
# Mois civil complet
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debut", "fin", "attendu"),
    [
        # novembre (30 j) → octobre (31 j)
        (date(2026, 11, 1), date(2026, 11, 30), (date(2026, 10, 1), date(2026, 10, 31))),
        # décembre (31 j) → novembre (30 j)
        (date(2026, 12, 1), date(2026, 12, 31), (date(2026, 11, 1), date(2026, 11, 30))),
        # mars → février d'une année bissextile (29 j)
        (date(2028, 3, 1), date(2028, 3, 31), (date(2028, 2, 1), date(2028, 2, 29))),
        # mars → février d'une année non bissextile (28 j)
        (date(2026, 3, 1), date(2026, 3, 31), (date(2026, 2, 1), date(2026, 2, 28))),
        # février bissextile → janvier
        (date(2028, 2, 1), date(2028, 2, 29), (date(2028, 1, 1), date(2028, 1, 31))),
        # janvier → décembre de l'année précédente
        (date(2027, 1, 1), date(2027, 1, 31), (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_mois_complet_mois_precedent(debut: date, fin: date, attendu: tuple[date, date]) -> None:
    """Du 1er au dernier jour du mois : le mois précédent complet (pas « 30 jours avant »)."""
    assert _precedente(debut, fin) == attendu


# --------------------------------------------------------------------------------------------
# Année civile
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debut", "fin", "attendu"),
    [
        (date(2026, 1, 1), date(2026, 12, 31), (date(2025, 1, 1), date(2025, 12, 31))),
        # 2029 (365 j) → 2028 bissextile (366 j) : année civile, pas « 365 jours avant »
        (date(2029, 1, 1), date(2029, 12, 31), (date(2028, 1, 1), date(2028, 12, 31))),
        # 2028 bissextile (366 j) → 2027
        (date(2028, 1, 1), date(2028, 12, 31), (date(2027, 1, 1), date(2027, 12, 31))),
    ],
)
def test_annee_civile_annee_precedente(debut: date, fin: date, attendu: tuple[date, date]) -> None:
    """Du 1er janvier au 31 décembre : l'année civile précédente."""
    assert _precedente(debut, fin) == attendu


# --------------------------------------------------------------------------------------------
# Période libre : même nombre de jours juste avant
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debut", "fin", "attendu"),
    [
        # 10 jours (10/11 → 19/11) → les 10 jours juste avant (31/10 → 09/11)
        (date(2026, 11, 10), date(2026, 11, 19), (date(2026, 10, 31), date(2026, 11, 9))),
        # mois en cours partiel (25 jours) → 25 jours juste avant, pas le mois précédent
        (date(2026, 11, 1), date(2026, 11, 25), (date(2026, 10, 7), date(2026, 10, 31))),
        # 7 jours du dimanche au samedi : pas une semaine SENELEC, même résultat que 7 jours avant
        (date(2026, 11, 15), date(2026, 11, 21), (date(2026, 11, 8), date(2026, 11, 14))),
        # deux semaines SENELEC (14 jours) : période libre
        (date(2026, 11, 7), date(2026, 11, 20), (date(2026, 10, 24), date(2026, 11, 6))),
        # deux mois complets : « mois civil complet » ne vise qu'un mois → 61 jours avant
        (date(2026, 10, 1), date(2026, 11, 30), (date(2026, 8, 1), date(2026, 9, 30))),
        # du 15 au 14 du mois suivant : pas un mois civil
        (date(2026, 10, 15), date(2026, 11, 14), (date(2026, 9, 14), date(2026, 10, 14))),
    ],
)
def test_periode_libre_meme_duree_juste_avant(debut: date, fin: date, attendu: tuple[date, date]) -> None:
    """Ni semaine SENELEC, ni mois civil, ni année civile : même nombre de jours juste avant."""
    resultat = _precedente(debut, fin)
    assert resultat == attendu
    assert (resultat[1] - resultat[0]) == (fin - debut)


@pytest.mark.parametrize(
    ("jour", "veille"),
    [
        (date(2026, 11, 25), date(2026, 11, 24)),
        (date(2026, 11, 1), date(2026, 10, 31)),  # un seul jour, pas un mois
        (date(2027, 1, 1), date(2026, 12, 31)),  # un seul jour, pas une année
        (date(2028, 3, 1), date(2028, 2, 29)),
    ],
)
def test_un_seul_jour_la_veille(jour: date, veille: date) -> None:
    """Une journée → la veille."""
    assert _precedente(jour, jour) == (veille, veille)
