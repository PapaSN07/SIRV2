"""Départs manquants : correspondances validées et création des feeders (scripts de migration)."""

import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.migration import corriger_feeders_postes as cfp  # noqa: E402
from scripts.migration.creer_departs_manquants import code_unique, lire_decisions, trouver_poste_source  # noqa: E402

ENTETES = ["Poste source", "Départ (nom relevé)", "Source", "Postes SIG", "Tronçons SIG", "km SIG",
           "Postes liste exploitants", "Service / unité", "Base ITD (Feeders)", "Feeders SIRV2 proches",
           "DÉCISION (créer / existant)", "FEEDER SIRV2 SI EXISTANT"]


def _classeur(tmp_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(ENTETES)
    ws.append(["BEL AIR", "POINT E", "SIG", 3, 0, 0, 0, "", "", "", "existant", "POINT E (BEL AIR, id 259)"])
    ws.append(["DIASS", "BENTEIGNE", "SIG", 2, 0, 0, 0, "", "", "", "créer", ""])
    ws.append(["HANN", "HLM PO", "SIG", 1, 0, 0, 0, "", "", "", "à préciser", ""])
    chemin = tmp_path / "departs.xlsx"
    wb.save(chemin)
    return chemin


def test_correspondances_prioritaires(tmp_path: Path) -> None:
    cfp.CORRESPONDANCES.clear()
    assert cfp.charger_correspondances(_classeur(tmp_path)) == 1
    assert cfp.resoudre_feeder("Point-E", "AUTRE", {}, {}) == 259
    cfp.CORRESPONDANCES.clear()
    assert cfp.resoudre_feeder("Point-E", "AUTRE", {}, {}) is None


def test_lire_decisions(tmp_path: Path) -> None:
    decisions = {d["depart"]: d["decision"] for d in lire_decisions(_classeur(tmp_path))}
    assert decisions == {"POINT E": "existant", "BENTEIGNE": "creer", "HLM PO": "à preciser"}


def test_code_unique() -> None:
    existants = {"SONATEL"}
    assert code_unique("Sonatel", existants) == "SONATEL 2"
    code = code_unique("LIVRAISON STADE DU SENEGAL ZONE NORD", existants)
    assert len(code) <= 20 and code == "LIVRAISON STADE DU S"


def test_trouver_poste_source() -> None:
    ps = {1: "DIASS", 2: "CAP DES BICHES", 3: "POSTE DIAMNIADIO", 4: "DIAMNIADIO 2"}
    assert trouver_poste_source("Diass", ps) == 1
    assert trouver_poste_source("CAP DES BICHE", ps) == 2
    assert trouver_poste_source("INCONNU", ps) is None
