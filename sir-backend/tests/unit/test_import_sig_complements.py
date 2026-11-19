"""Reprise PosteSource_SIG / FEEDERS_SIG : colonnes reconnues par leur nom, tout le reste gardé en JSON."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.migration.import_sig_complements import cle_nom, feeder_sig, poste_source_sig  # noqa: E402
from scripts.migration.loaders.sig import attributs_noeud, attributs_troncon  # noqa: E402


def test_feeder_sig_colonnes_reconnues() -> None:
    ligne = feeder_sig({"IDFEEDERS_SIG": 7, "NOMFEEDER": "OUAKAM", "IMATFEEDER": "D101", "SSTATION": "HANN", "DELEGATION": "DD", "AUTRE": "x"}, 1)
    assert (ligne["legacy_id"], ligne["nom"], ligne["code"], ligne["poste_source"], ligne["delegation"]) == ("7", "OUAKAM", "D101", "HANN", "DD")
    assert json.loads(ligne["attributs"])["AUTRE"] == "x"


def test_poste_source_sig_coordonnees() -> None:
    ligne = poste_source_sig({"IDPosteSource_SIG": 12, "NOMPOSTESOURCE": "CAP DES BICHES", "CORX": "240000,5", "CORY": 1630000}, 1)
    assert (ligne["nom"], ligne["coord_x"], ligne["coord_y"]) == ("CAP DES BICHES", 240000.5, 1630000.0)


def test_complements_noeud_troncon_et_cle() -> None:
    assert attributs_noeud({"DELEGATION": " DRS ", "PUISSANCE_": 160})["delegation"] == "DRS"
    assert attributs_troncon({"SS": "HANN", "TYPE_CONDU": "ALMELEC"})["poste_source"] == "HANN"
    assert cle_nom("Yeumbeul 30 kV") == "YEUMBEUL30KV"


def test_tables_reelles_du_sig_de_sir_v1() -> None:
    # Colonnes lues sur srv-hfsql le 19/11/2026
    ps = poste_source_sig({"fid": 0.0, "postesource": "S/S UNIVERSITE", "idpostesource_sig": 17.0}, 1)
    assert (ps["legacy_id"], ps["nom"]) == ("17", "S/S UNIVERSITE")
    fd = feeder_sig({"fid": 0, "nomfeeder": "ABASS NDAO", "imatfeeder": "LM.03.06", "postesource": "S/S UNIVERSITE",
                     "categories": "AERIEN", "idpropritetaire_ligne": 1, "date_mise_en_service": None, "nombre_km": 12.5}, 1)
    assert (fd["legacy_id"], fd["nom"], fd["code"], fd["poste_source"]) == ("0", "ABASS NDAO", "LM.03.06", "S/S UNIVERSITE")
    assert attributs_troncon({"SECTIONS": "0.0", "TYPE_CONDU": "0.0"})["section"] is None
    assert attributs_noeud({"PUISSANCE_": "630.0"})["puissance"] == "630"
