"""Carte des postes : homonymes SIG départagés par le feeder ; conversion UTM 28N exacte."""

from app.repositories.pilotage_repository import PointSig, _lon_lat, choisir_point


def test_homonyme_departage_par_feeder() -> None:
    candidats = [PointSig(10, -17.45, 14.70), PointSig(20, -16.20, 14.10)]
    assert choisir_point(candidats, 20) == (-16.20, 14.10)


def test_homonymes_eloignes_sans_feeder_non_places() -> None:
    candidats = [PointSig(10, -17.45, 14.70), PointSig(20, -16.20, 14.10)]
    assert choisir_point(candidats, 99) is None


def test_doublons_proches_places() -> None:
    candidats = [PointSig(None, -17.4500, 14.7000), PointSig(None, -17.4502, 14.7001)]
    assert choisir_point(candidats, None) == (-17.45, 14.70)


def test_utm28n_conforme_a_pyproj() -> None:
    # Référence pyproj EPSG:32628 → EPSG:4326 : (-17.442363416605, 14.703901116809)
    lon, lat = _lon_lat(237000, 1627000)
    assert abs(lon - -17.442363416605) < 1e-7 and abs(lat - 14.703901116809) < 1e-7
    # Coordonnées déjà en degrés (x = longitude) laissées telles quelles
    assert _lon_lat(-16.95, 14.82) == (-16.95, 14.82)
