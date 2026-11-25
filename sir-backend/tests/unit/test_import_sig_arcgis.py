"""Import du SIG ArcGIS (KMZ « DAKAR HTA ») : lecture des bulles, longueurs, postes et tronçons."""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.migration.import_sig_arcgis import (  # noqa: E402
    attributs_description,
    lire_kmz,
    longueur_troncon_m,
    noeud_arcgis,
    troncon_arcgis,
)

BULLE = (
    "<html><body><table><tr><td>Nom Du Poste</td><td>BATA</td></tr>"
    "<tr bgcolor='#D4E4F3'><td>FeederID</td><td>RUFISQUE NORD</td></tr>"
    "<tr><td>PosteSource</td><td>CAP DES BICHES</td></tr>"
    "<tr><td>X_Centroide</td><td>257339,437693</td></tr><tr><td>Y_Centroide</td><td>1626840,05</td></tr>"
    "<tr><td>Indicateur d'&#233;tat</td><td>En Service</td></tr>"
    "<tr><td>Commentaires</td><td>&lt;Nul&gt;</td></tr>"
    "<tr><td>GlobalID</td><td>{5d138b36-bacc}</td></tr></table></body></html>"
)


def test_bulle_arcgis_lue_et_nul_vide() -> None:
    a = attributs_description(BULLE)
    assert a["Nom Du Poste"] == "BATA" and a["Indicateur d'état"] == "En Service"
    assert a["Commentaires"] is None


def test_poste_arcgis() -> None:
    n = noeud_arcgis(attributs_description(BULLE))
    assert n is not None
    assert (n["global_id"], n["nom_feeder"], n["poste_source"], n["region"]) == ("5D138B36-BACC", "RUFISQUE NORD", "CAP DES BICHES", "DAKAR")
    assert n["coord_x"] == 257339.437693 and n["est_actif"] is True


def test_longueur_geometrie_sinon_champ_km_ou_m() -> None:
    ligne = [[(-17.3, 14.7), (-17.3, 14.701)]]  # ~111 m
    assert 100 < longueur_troncon_m({}, ligne, "aerien") < 120  # type: ignore[operator]
    illisible = [[(-17.0, 2797815776645.0), (-17.0, 2796607506375.0)]]
    assert longueur_troncon_m({"Longueur mesurée, [m]": "0,766919"}, illisible, "souterrain") == 766.919
    assert longueur_troncon_m({"Longueur mesurée, [m]": "3455,5"}, illisible, "souterrain") == 3455.5
    assert longueur_troncon_m({}, illisible, "souterrain") is None


def test_troncon_et_lecture_kmz(tmp_path: Path) -> None:
    kml = (
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Folder><name>ConducteurAerienHTA</name>'
        "<Placemark><description><![CDATA[<table><tr><td>Nom Du Depart</td><td>SIES</td></tr>"
        "<tr><td>Amont</td><td>REMONTEE SOUT</td></tr><tr><td>Aval</td><td>H61 SBM</td></tr>"
        "<tr><td>Tension Nominale</td><td>30</td></tr><tr><td>GlobalID</td><td>{0d1d}</td></tr></table>]]></description>"
        "<MultiGeometry><LineString><coordinates>-17.3,14.7,0 -17.3,14.701,0</coordinates></LineString></MultiGeometry>"
        "</Placemark></Folder></Document></kml>"
    )
    chemin = tmp_path / "dakar.kmz"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("doc.kml", kml)
    couches = lire_kmz(chemin)
    a, g = couches["ConducteurAerienHTA"][0]
    t = troncon_arcgis(a, g, "aerien")
    assert t is not None
    assert (t["nom_feeder"], t["nom_noeud_amont"], t["nom_noeud_aval"], t["tension_kv"]) == ("SIES", "REMONTEE SOUT", "H61 SBM", 30.0)
    assert t["type_conducteur"].startswith("Aérien") and 100 < t["longueur_m"] < 120  # type: ignore[union-attr,operator]
