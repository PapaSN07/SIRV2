"""Onglet Évolution du « Suivi incidents » : fonctions pures du service (spécification §9).

Fonctions attendues dans ``app/services/suivi_incidents_service.py`` :

- ``granularite_auto(debut: date, fin: date) -> str`` : ``"jour"`` si la période (fin incluse) fait
  31 jours ou moins, ``"semaine"`` si elle fait 186 jours ou moins, ``"mois"`` sinon ;
- ``intervalles(debut: date, fin: date, granularite: str) -> list[tuple[date, date, str]]`` :
  ``(debut, fin, libelle)`` de chaque point, dans l'ordre, couvrant toute la période sans trou ni
  chevauchement ; granularité ``jour`` | ``semaine`` | ``mois`` (autre valeur → ``ValueError``).

  * jour : ``debut == fin``, libellé « 14/11 » ;
  * semaine : semaine SENELEC (samedi → vendredi, numéro ISO du vendredi), libellé « S47 » (sans
    zéro : « S1 ») ; premier et dernier intervalles rognés aux bornes ;
  * mois : mois civil, libellé « nov. 2026 » (janv., févr., mars, avr., mai, juin, juil., août,
    sept., oct., nov., déc.), rogné de même.

Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest


def _service():
    from app.services import suivi_incidents_service

    return suivi_incidents_service


def _intervalles(debut: date, fin: date, granularite: str) -> list[tuple[date, date, str]]:
    resultat = [tuple(i) for i in _service().intervalles(debut, fin, granularite)]
    for intervalle in resultat:
        assert len(intervalle) == 3, intervalle
    return resultat  # type: ignore[return-value]


def _contigus(points: list[tuple[date, date, str]], debut: date, fin: date) -> None:
    """Toute la période, sans trou ni chevauchement, dans l'ordre."""
    assert points, "aucun intervalle"
    assert points[0][0] == debut
    assert points[-1][1] == fin
    for (d, f, _), (d_suivant, _, _) in zip(points, points[1:]):
        assert d <= f
        assert d_suivant == f + timedelta(days=1)
    assert points[-1][0] <= points[-1][1]


# --------------------------------------------------------------------------------------------
# Granularité automatique : seuils 31 / 186 jours (fin incluse)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debut", "fin", "attendue"),
    [
        (date(2026, 11, 14), date(2026, 11, 14), "jour"),  # 1 jour
        (date(2026, 11, 14), date(2026, 11, 20), "jour"),  # semaine SENELEC
        (date(2026, 10, 1), date(2026, 10, 31), "jour"),  # 31 jours
        (date(2026, 10, 1), date(2026, 11, 1), "semaine"),  # 32 jours
        (date(2026, 1, 1), date(2026, 7, 5), "semaine"),  # 186 jours
        (date(2026, 1, 1), date(2026, 7, 6), "mois"),  # 187 jours
        (date(2026, 1, 1), date(2026, 12, 31), "mois"),  # année
        (date(2024, 1, 1), date(2026, 12, 31), "mois"),  # trois ans
    ],
)
def test_granularite_auto_seuils(debut: date, fin: date, attendue: str) -> None:
    assert (fin - debut).days + 1 in (1, 7, 31, 32, 186, 187, 365, 1096)  # contrôle des données
    assert _service().granularite_auto(debut, fin) == attendue


# --------------------------------------------------------------------------------------------
# Jour
# --------------------------------------------------------------------------------------------


def test_jours_semaine_senelec() -> None:
    points = _intervalles(date(2026, 11, 14), date(2026, 11, 20), "jour")
    assert [p[2] for p in points] == ["14/11", "15/11", "16/11", "17/11", "18/11", "19/11", "20/11"]
    for d, f, _ in points:
        assert d == f
    _contigus(points, date(2026, 11, 14), date(2026, 11, 20))


def test_jour_unique() -> None:
    assert _intervalles(date(2026, 11, 14), date(2026, 11, 14), "jour") == [
        (date(2026, 11, 14), date(2026, 11, 14), "14/11")
    ]


def test_jours_changement_d_annee() -> None:
    points = _intervalles(date(2026, 12, 30), date(2027, 1, 2), "jour")
    assert [p[2] for p in points] == ["30/12", "31/12", "01/01", "02/01"]
    assert points[2][0] == date(2027, 1, 1)


def test_jours_annee_bissextile_366_points() -> None:
    points = _intervalles(date(2028, 1, 1), date(2028, 12, 31), "jour")
    assert len(points) == 366
    assert (date(2028, 2, 29), date(2028, 2, 29), "29/02") in points


# --------------------------------------------------------------------------------------------
# Semaine SENELEC (samedi → vendredi), rognée aux bornes
# --------------------------------------------------------------------------------------------


def test_semaine_exacte_un_point() -> None:
    assert _intervalles(date(2026, 11, 14), date(2026, 11, 20), "semaine") == [
        (date(2026, 11, 14), date(2026, 11, 20), "S47")
    ]


def test_semaines_rognees_aux_bornes() -> None:
    """Mardi 10/11 → mercredi 18/11 : S46 rognée (10/11 → 13/11), S47 rognée (14/11 → 18/11)."""
    assert _intervalles(date(2026, 11, 10), date(2026, 11, 18), "semaine") == [
        (date(2026, 11, 10), date(2026, 11, 13), "S46"),
        (date(2026, 11, 14), date(2026, 11, 18), "S47"),
    ]


def test_semaines_octobre_novembre() -> None:
    """Jeudi 01/10 → vendredi 20/11 : S40 rognée (01/10 → 02/10) puis S41 … S47 complètes."""
    points = _intervalles(date(2026, 10, 1), date(2026, 11, 20), "semaine")
    assert [p[2] for p in points] == ["S40", "S41", "S42", "S43", "S44", "S45", "S46", "S47"]
    assert points[0][:2] == (date(2026, 10, 1), date(2026, 10, 2))
    assert points[1][:2] == (date(2026, 10, 3), date(2026, 10, 9))
    assert points[5][:2] == (date(2026, 10, 31), date(2026, 11, 6))
    for d, f, _ in points[1:]:
        assert d.weekday() == 5 and f.weekday() == 4  # samedi → vendredi
    _contigus(points, date(2026, 10, 1), date(2026, 11, 20))


def test_semaine_d_un_seul_jour() -> None:
    """Un vendredi seul : semaine rognée à ce jour."""
    assert _intervalles(date(2026, 11, 20), date(2026, 11, 20), "semaine") == [
        (date(2026, 11, 20), date(2026, 11, 20), "S47")
    ]


def test_semaines_changement_d_annee_s53_puis_s1() -> None:
    """S53 2026 = samedi 26/12/2026 → vendredi 01/01/2027 ; S1 2027 = 02/01 → 08/01/2027."""
    assert _intervalles(date(2026, 12, 26), date(2027, 1, 8), "semaine") == [
        (date(2026, 12, 26), date(2027, 1, 1), "S53"),
        (date(2027, 1, 2), date(2027, 1, 8), "S1"),
    ]


def test_semaine_s1_commencant_l_annee_precedente() -> None:
    """S1 2026 = samedi 27/12/2025 → vendredi 02/01/2026 (rognée au 01/01/2026)."""
    points = _intervalles(date(2026, 1, 1), date(2026, 1, 9), "semaine")
    assert points == [
        (date(2026, 1, 1), date(2026, 1, 2), "S1"),
        (date(2026, 1, 3), date(2026, 1, 9), "S2"),
    ]


# --------------------------------------------------------------------------------------------
# Mois civil, rogné aux bornes, libellés français abrégés
# --------------------------------------------------------------------------------------------


def test_mois_complet_un_point() -> None:
    assert _intervalles(date(2026, 11, 1), date(2026, 11, 30), "mois") == [
        (date(2026, 11, 1), date(2026, 11, 30), "nov. 2026")
    ]


def test_mois_rognes_aux_bornes() -> None:
    assert _intervalles(date(2026, 8, 15), date(2026, 11, 20), "mois") == [
        (date(2026, 8, 15), date(2026, 8, 31), "août 2026"),
        (date(2026, 9, 1), date(2026, 9, 30), "sept. 2026"),
        (date(2026, 10, 1), date(2026, 10, 31), "oct. 2026"),
        (date(2026, 11, 1), date(2026, 11, 20), "nov. 2026"),
    ]


def test_mois_changement_d_annee() -> None:
    assert _intervalles(date(2026, 12, 1), date(2027, 2, 10), "mois") == [
        (date(2026, 12, 1), date(2026, 12, 31), "déc. 2026"),
        (date(2027, 1, 1), date(2027, 1, 31), "janv. 2027"),
        (date(2027, 2, 1), date(2027, 2, 10), "févr. 2027"),
    ]


def test_libelles_des_douze_mois() -> None:
    points = _intervalles(date(2026, 1, 1), date(2026, 12, 31), "mois")
    assert [p[2] for p in points] == [
        "janv. 2026", "févr. 2026", "mars 2026", "avr. 2026", "mai 2026", "juin 2026",
        "juil. 2026", "août 2026", "sept. 2026", "oct. 2026", "nov. 2026", "déc. 2026",
    ]
    assert points[1][:2] == (date(2026, 2, 1), date(2026, 2, 28))
    _contigus(points, date(2026, 1, 1), date(2026, 12, 31))


def test_fevrier_bissextile() -> None:
    assert _intervalles(date(2028, 2, 1), date(2028, 2, 29), "mois") == [
        (date(2028, 2, 1), date(2028, 2, 29), "févr. 2028")
    ]


# --------------------------------------------------------------------------------------------
# Granularité inconnue
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("granularite", ["annee", "trimestre", "auto"])
def test_intervalles_granularite_inconnue(granularite: str) -> None:
    """``intervalles`` reçoit la granularité appliquée (jamais ``auto``)."""
    with pytest.raises(ValueError):
        _service().intervalles(date(2026, 11, 14), date(2026, 11, 20), granularite)
