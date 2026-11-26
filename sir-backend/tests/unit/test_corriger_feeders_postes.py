"""Feeders des postes : feeders par défaut de SIR v1 (AIR SENEGAL 30 KV, SAUVEGARDE) jamais repris."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.migration.corriger_feeders_postes import decider, feeder_majoritaire  # noqa: E402
from scripts.migration.transforms.fk_resolver import FkResolver  # noqa: E402


class _Maps:
    def __init__(self) -> None:
        self.texte = {"AIR SENEGAL 30 KV": 52, "SAUVEGARDE": 41, "SAII": 7}
        self.legacy = {30: 41, 159: 52, 12: 7}

    def lookup_text(self, entite: str, cle: str) -> int | None:
        return self.texte.get(cle.strip().upper()) if cle else None

    def get(self, entite: str, cle: object) -> int | None:
        return self.legacy.get(cle)  # type: ignore[arg-type]


def test_feeder_du_poste_texte_d_abord_jamais_par_defaut() -> None:
    fk = FkResolver(_Maps())  # type: ignore[arg-type]
    # idfeeder 30 (SAUVEGARDE) mais texte SAII : le texte gagne
    assert fk.resolve_feeder_id_poste({"idfeeder": 30.0, "feeder": "SAII"}) == 7
    # texte par défaut, idfeeder 0 : aucun feeder (à corriger)
    assert fk.resolve_feeder_id_poste({"idfeeder": 0, "feeder": "AIR SENEGAL 30 KV"}) is None
    assert fk.resolve_feeder_id_poste({"idfeeder": 30, "feeder": ""}) is None
    assert fk.resolve_feeder_id_poste({"idfeeder": 12, "feeder": ""}) == 7


def test_decision_par_concordance_des_sources() -> None:
    # historique SIR v1 (texte, itd, interruptions) = une seule famille : leur accord seul reste « probable »
    assert decider({"texte": 7, "interruptions": 7, "sig": None}) == (7, "probable")
    assert decider({"texte": 7, "interruptions": 7, "sig": 7}) == (7, "sure")
    assert decider({"texte": None, "interruptions": None, "sig": 9}) == (9, "probable")
    assert decider({"texte": 7, "interruptions": 7, "sig": 9}) == (None, "a_arbitrer")
    assert decider({"texte": None, "interruptions": None, "sig": None}) == (None, "sans_source")


def test_feeder_majoritaire_des_coupures() -> None:
    assert feeder_majoritaire(Counter({7: 3, 52: 10, 9: 1}), exclus={52}) == 7  # 3/4 hors défaut
    assert feeder_majoritaire(Counter({7: 1, 9: 1}), exclus=set()) is None  # pas de majorité
    assert feeder_majoritaire(Counter({52: 4}), exclus={52}) is None


def test_decision_majoritaire() -> None:
    # terrain + SIG l'emportent sur l'historique (départ reconfiguré) ; terrain contre SIG : à arbitrer
    assert decider({"exploitants": 7, "recensement": 7, "sig": 7, "itd": 9, "texte": 9, "interruptions": 9}) == (7, "sure")
    assert decider({"exploitants": 7, "itd": 9, "texte": 9}) == (7, "terrain")
    assert decider({"exploitants": 7, "sig": 9, "texte": 9, "interruptions": 7}) == (None, "a_arbitrer")


def test_liste_exploitants_par_entete(tmp_path: Path) -> None:
    from openpyxl import Workbook

    from scripts.migration.corriger_feeders_postes import lire_liste_exploitants

    classeur = Workbook()
    feuille = classeur.active
    feuille.append(["SERVICES", "POSTES SOURCES", "FEEDERS", "POSTES"])
    feuille.append(["SDDV", "HANN", "SOPRIM", "PA 14"])
    feuille.append(["SDDV", "HANN", None, "SANS FEEDER"])
    chemin = tmp_path / "liste.xlsx"
    classeur.save(chemin)
    assert lire_liste_exploitants(chemin) == [("SDDV", "HANN", "SOPRIM", "PA 14")]


def test_resoudre_feeder_exact_puis_proche_dans_le_poste_source() -> None:
    from scripts.migration.corriger_feeders_postes import resoudre_feeder

    du_ps = {"BELAIR": {"ALBERTSARRAUT": {3}, "MEDINA6KV": {4}}, "AEROPORT": {"AIRSENEGAL30KV": {52}}}
    par_cle = {"ALBERTSARRAUT": {3}, "AIRSENEGAL30KV": {52}, "SOPRIM": {9}}
    assert resoudre_feeder("SOPRIM", "HANN", du_ps, par_cle) == 9
    assert resoudre_feeder("ALBERT SARRAULT", "BEL AIR", du_ps, par_cle) == 3
    assert resoudre_feeder("AIR SENEGAL", "AEROPORT", du_ps, par_cle) == 52
    assert resoudre_feeder("MEDINA", "BEL AIR", du_ps, par_cle) == 4
    assert resoudre_feeder("LFTR", "AEROPORT", du_ps, par_cle) is None
