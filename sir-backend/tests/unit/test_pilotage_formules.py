"""Formules du pilotage : défauts aux 100 km, objectifs et tendance."""

from app.repositories.pilotage_repository import _lon_lat
from app.services.pilotage_service import (
    decouper_objectif,
    defauts_pour_100_km,
    jours_de_annee,
    taux_realisation,
    tendance_lineaire,
)


def test_defauts_pour_100_km() -> None:
    assert defauts_pour_100_km(15, 150) == 10.0
    assert defauts_pour_100_km(0, 80) == 0
    assert defauts_pour_100_km(4, 0) is None


def test_objectif_journalier_et_cumul() -> None:
    journalier, cumul = decouper_objectif(365, jours_ecoules=100, jours_annee=365)
    assert journalier == 1
    assert round(cumul, 2) == 100
    assert taux_realisation(80, 100) == 80
    assert taux_realisation(10, 0) is None
    assert jours_de_annee(2024) == 366
    assert jours_de_annee(2026) == 365


def test_coordonnee_utm_senegal() -> None:
    longitude, latitude = _lon_lat(238394.6712, 1633987.3821)
    assert longitude is not None and latitude is not None
    assert -17.6 < longitude < -17.2
    assert 14.6 < latitude < 14.9


def test_tendance_lineaire_detecte_une_hausse() -> None:
    slope, _intercept, sens = tendance_lineaire([1, 2, 3, 4, 5, 6])
    assert slope > 0
    assert sens == "hausse"
    _slope, _intercept, stable = tendance_lineaire([4, 4, 4, 4])
    assert stable == "stable"
