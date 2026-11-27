#!/usr/bin/env python3
"""Départs (feeders) cités par le SIG ArcGIS ou la liste des exploitants et absents de SIRV2 (lecture seule).

Pour chaque départ non reconnu : poste source, nombre de postes et de tronçons (km) dans le SIG, nombre de
postes dans la liste des exploitants, service, présence dans la base IndicateursTransportDistribution
(table Feeders) et les feeders SIRV2 aux noms les plus proches. Le classeur Excel produit sert à décider,
départ par départ : « créer » ou « = feeder SIRV2 existant ».

Usage (poste SENELEC) :
    python scripts/migration/lister_departs_manquants.py --kmz "D:\\Senelec\\SIRV2\\DAKAR HTA.mxd.kmz"
        --liste-exploitants "D:\\Senelec\\SIRV2\\LISTE POSTES DAKAR JUILLET 2026.xlsx"
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402

try:
    from scripts.migration.corriger_feeders_postes import cle_feeder, lire_liste_exploitants, resoudre_feeder
    from scripts.migration.import_sig_arcgis import COUCHES_TRONCONS, lire_kmz, noeud_arcgis, troncon_arcgis
except ModuleNotFoundError:  # copie posée à côté des deux autres scripts
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from corriger_feeders_postes import cle_feeder, lire_liste_exploitants, resoudre_feeder  # type: ignore[no-redef]
    from import_sig_arcgis import COUCHES_TRONCONS, lire_kmz, noeud_arcgis, troncon_arcgis  # type: ignore[no-redef]


def suggestions(nom: str, poste_source: str, feeders: list[tuple[int, str, str, str]], n: int = 3) -> list[str]:
    """Feeders SIRV2 aux noms les plus proches : d'abord ceux du même poste source."""
    cle = cle_feeder(nom)
    du_ps = [f for f in feeders if cle_feeder(f[3]) == cle_feeder(poste_source)]
    resultat: list[str] = []
    for groupe in (du_ps, feeders):
        noms = {cle_feeder(f[1]): f for f in groupe}
        for k in difflib.get_close_matches(cle, list(noms), n=n, cutoff=0.6):
            f = noms[k]
            libelle = f"{f[1]} ({f[3] or 'sans poste source'}, id {f[0]})"
            if libelle not in resultat:
                resultat.append(libelle)
        if len(resultat) >= n:
            break
    return resultat[:n]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kmz", type=Path)
    parser.add_argument("--liste-exploitants", type=Path)
    args = parser.parse_args()

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from sqlalchemy import text

    from scripts.migration.config import get_settings
    from scripts.migration.db_session import get_session
    from scripts.migration.itd_sqlserver import connect_itd

    with get_session() as session:
        feeders = [
            (int(i), lib or "", code or "", ps or "")
            for i, lib, code, ps in session.execute(text(
                "SELECT f.id, f.libelle, f.code, ps.libelle FROM dbo.feeders f"
                " LEFT JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id WHERE f.is_active = 1")).all()
        ]
    par_cle: dict[str, set[int]] = defaultdict(set)
    feeders_du_ps: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for i, lib, code, ps in feeders:
        for nom in (lib, code):
            if cle_feeder(nom):
                par_cle[cle_feeder(nom)].add(i)
                feeders_du_ps[cle_feeder(ps)][cle_feeder(nom)].add(i)

    itd_feeders: dict[str, str] = {}
    try:
        cn = connect_itd()
        cur = cn.cursor()
        cur.execute("SELECT Feeder, PosteSOurce, Service FROM dbo.Feeders")
        for feeder, ps, service in cur.fetchall():
            if feeder:
                itd_feeders[cle_feeder(feeder)] = f"{feeder} ({ps or '—'}, {service or '—'})"
        cn.close()
    except Exception as e:  # noqa: BLE001
        print(f"Base IndicateursTransportDistribution injoignable ({e}) : colonne ITD vide.")

    # Départs non reconnus : (poste source, nom) → compteurs
    manquants: dict[tuple[str, str], dict[str, object]] = {}

    def noter(ps: str, depart: str, cle_compteur: str, valeur: float = 1.0, service: str = "") -> None:
        if not depart or resoudre_feeder(depart, ps, feeders_du_ps, par_cle) is not None:
            return
        ligne = manquants.setdefault((cle_feeder(ps), cle_feeder(depart)), {
            "ps": ps, "depart": depart, "postes_sig": 0, "troncons_sig": 0, "km_sig": 0.0,
            "postes_liste": 0, "services": set(),
        })
        ligne[cle_compteur] = float(ligne[cle_compteur]) + valeur  # type: ignore[arg-type]
        if service:
            ligne["services"].add(service)  # type: ignore[union-attr]

    if args.kmz:
        couches = lire_kmz(args.kmz)
        for a, _ in couches.get("PosteHTABT", []):
            n = noeud_arcgis(a)
            if n and n["nom_feeder"]:
                noter(str(n["poste_source"] or ""), str(n["nom_feeder"]), "postes_sig", service=str(n["delegation"] or ""))
        for couche, type_ligne in COUCHES_TRONCONS.items():
            for a, g in couches.get(couche, []):
                t = troncon_arcgis(a, g, type_ligne)
                if t and t["nom_feeder"]:
                    noter(str(t["poste_source"] or ""), str(t["nom_feeder"]), "troncons_sig")
                    noter(str(t["poste_source"] or ""), str(t["nom_feeder"]), "km_sig", float(t["longueur_m"] or 0) / 1000)
    if args.liste_exploitants:
        for service, ps, feeder, _poste in lire_liste_exploitants(args.liste_exploitants):
            noter(ps, feeder, "postes_liste", service=service)

    lignes = sorted(manquants.values(), key=lambda x: (-float(x["postes_sig"]) - float(x["postes_liste"]), str(x["ps"])))  # type: ignore[arg-type]
    print(f"{len(lignes)} départs absents de SIRV2 (SIG et / ou liste des exploitants).")

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Départs manquants"
    entetes = [
        "Poste source", "Départ (nom relevé)", "Source", "Postes SIG", "Tronçons SIG", "km SIG",
        "Postes liste exploitants", "Service / unité", "Base ITD (Feeders)", "Feeders SIRV2 proches",
        "DÉCISION (créer / existant)", "FEEDER SIRV2 SI EXISTANT",
    ]
    feuille.append(entetes)
    for x in lignes:
        source = " + ".join(s for s, k in (("SIG", "postes_sig"), ("Liste exploitants", "postes_liste")) if float(x[k]))  # type: ignore[arg-type]
        if not source:
            source = "SIG (tronçons)"
        feuille.append([
            x["ps"], x["depart"], source, int(float(x["postes_sig"])), int(float(x["troncons_sig"])),  # type: ignore[arg-type]
            round(float(x["km_sig"]), 1), int(float(x["postes_liste"])),  # type: ignore[arg-type]
            ", ".join(sorted(x["services"])), itd_feeders.get(cle_feeder(str(x["depart"])), ""),  # type: ignore[arg-type]
            " ; ".join(suggestions(str(x["depart"]), str(x["ps"]), feeders)), "", "",
        ])
    for c in feuille[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="262051")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for c in (feuille["K1"], feuille["L1"]):
        c.fill = PatternFill("solid", fgColor="E6007E")
    for col, largeur in zip("ABCDEFGHIJKL", (18, 30, 22, 10, 11, 9, 13, 26, 34, 60, 20, 26)):
        feuille.column_dimensions[col].width = largeur
    feuille.freeze_panes = "C2"
    feuille.auto_filter.ref = feuille.dimensions

    sortie = get_settings().reports_dir / f"departs_manquants_{datetime.now():%Y%m%d_%H%M}.xlsx"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(sortie)
    print(f"Classeur : {sortie}")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
