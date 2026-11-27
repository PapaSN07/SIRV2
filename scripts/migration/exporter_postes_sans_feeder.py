#!/usr/bin/env python3
"""Classeur des postes SIR sans feeder fiable, à faire compléter par les exploitants (lecture seule).

Postes = lignes « sans_source » du dernier rapport de corriger_feeders_postes.py (aucune source : ni base ITD,
ni texte SIR v1, ni interruptions, ni recensement, ni liste des exploitants). Pour chacun : service, clients,
puissance, interruptions SIRV2 (nombre, dernière date, feeder le plus cité), feeder indiqué par le SIG.
Colonnes à remplir : POSTE SOURCE et FEEDER (liste déroulante des feeders SIRV2), ou « Inactif ».

Usage (poste SENELEC) :
    python scripts/migration/exporter_postes_sans_feeder.py --rapport "scripts\\migration\\reports\\feeders_postes_20261127_0952.csv"
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402


def lire_sans_source(rapport: Path) -> list[dict[str, str]]:
    """Lignes du rapport sans aucune source de feeder."""
    with rapport.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f, delimiter=";") if r.get("niveau") == "sans_source"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rapport", type=Path, required=True, help="rapport CSV de corriger_feeders_postes.py")
    args = parser.parse_args()

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from sqlalchemy import bindparam, text

    from scripts.migration.config import get_settings
    from scripts.migration.db_session import get_session

    lignes = lire_sans_source(args.rapport)
    ids = [int(r["poste_id"]) for r in lignes]
    print(f"{len(ids)} postes sans source de feeder.")

    with get_session() as session:
        details = {int(r.id): r for r in session.execute(text(
            "SELECT p.id, p.puissance_kva, p.nombre_clients, s.libelle AS service"
            " FROM dbo.postes p LEFT JOIN dbo.services s ON s.id = p.service_id"
            " WHERE p.id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": ids}).all()} if ids else {}
        interruptions = {int(r.poste_id): r for r in session.execute(text(
            "SELECT pi.poste_id, COUNT(*) AS nombre, MAX(i.date_apparition) AS derniere"
            " FROM dbo.poste_interruptions pi JOIN dbo.interruptions i ON i.id = pi.interruption_id"
            " WHERE pi.poste_id IN :ids GROUP BY pi.poste_id").bindparams(bindparam("ids", expanding=True)),
            {"ids": ids}).all()} if ids else {}
        feeders_cites: dict[int, str] = {}
        if ids:
            comptes: dict[int, dict[str, int]] = {}
            for r in session.execute(text(
                "SELECT pi.poste_id, f.libelle, COUNT(*) AS nombre"
                " FROM dbo.poste_interruptions pi JOIN dbo.interruptions i ON i.id = pi.interruption_id"
                " JOIN dbo.feeders f ON f.id = i.feeder_id"
                " WHERE pi.poste_id IN :ids GROUP BY pi.poste_id, f.libelle").bindparams(
                    bindparam("ids", expanding=True)), {"ids": ids}).all():
                comptes.setdefault(int(r.poste_id), {})[r.libelle] = int(r.nombre)
            feeders_cites = {p: max(c, key=lambda k: c[k]) for p, c in comptes.items()}
        feeders = session.execute(text(
            "SELECT f.libelle, ps.libelle AS poste_source FROM dbo.feeders f"
            " JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id WHERE f.is_active = 1"
            " ORDER BY ps.libelle, f.libelle")).all()

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Postes sans feeder"
    entetes = ["ID poste SIRV2", "Code", "Poste", "Service", "Clients", "Puissance (kVA)", "Interruptions SIRV2",
               "Dernière interruption", "Feeder des interruptions", "Feeder indiqué par le SIG",
               "Feeder actuel (par défaut)", "POSTE SOURCE", "FEEDER", "INACTIF (oui)", "Commentaire"]
    feuille.append(entetes)
    lignes.sort(key=lambda r: (-(interruptions[int(r["poste_id"])].nombre if int(r["poste_id"]) in interruptions else 0),
                               r["poste"]))
    for r in lignes:
        pid = int(r["poste_id"])
        d, it = details.get(pid), interruptions.get(pid)
        feuille.append([
            pid, r["code"], r["poste"], d.service if d else None,
            int(d.nombre_clients) if d and d.nombre_clients is not None else None,
            float(d.puissance_kva) if d and d.puissance_kva is not None else None,
            int(it.nombre) if it else 0, it.derniere.strftime("%d/%m/%Y") if it and it.derniere else None,
            feeders_cites.get(pid), r.get("feeder_sig") or None, r.get("ancien_feeder") or "aucun",
            None, None, None, None,
        ])

    liste = classeur.create_sheet("Feeders SIRV2")
    liste.append(["Poste source", "Feeder"])
    for f in feeders:
        liste.append([f.poste_source, f.libelle])
    liste.column_dimensions["A"].width = 30
    liste.column_dimensions["B"].width = 40
    fin = len(feeders) + 1
    choix_feeder = DataValidation(type="list", formula1=f"='Feeders SIRV2'!$B$2:$B${fin}", allow_blank=True)
    choix_ps = DataValidation(type="list", formula1=f"='Feeders SIRV2'!$A$2:$A${fin}", allow_blank=True)
    choix_inactif = DataValidation(type="list", formula1='"oui"', allow_blank=True)
    for v, col in ((choix_ps, "L"), (choix_feeder, "M"), (choix_inactif, "N")):
        v.showErrorMessage = False  # valeur libre acceptée (nom relevé sur le terrain)
        feuille.add_data_validation(v)
        v.add(f"{col}2:{col}{len(lignes) + 1}")

    for c in feuille[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="262051")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for col in "LMNO":
        feuille[f"{col}1"].fill = PatternFill("solid", fgColor="E6007E")
    for col, largeur in zip("ABCDEFGHIJKLMNO", (10, 20, 32, 12, 9, 10, 12, 13, 26, 22, 20, 24, 30, 10, 30)):
        feuille.column_dimensions[col].width = largeur
    feuille.freeze_panes = "D2"
    feuille.auto_filter.ref = feuille.dimensions

    sortie = get_settings().reports_dir / f"postes_sans_feeder_{datetime.now():%Y%m%d_%H%M}.xlsx"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(sortie)
    print(f"Classeur : {sortie}")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
