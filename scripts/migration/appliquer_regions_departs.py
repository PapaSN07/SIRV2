#!/usr/bin/env python3
"""Fixe la région propre des départs (feeders.region_id) d'après le SIG : départs de SDRBD.

Source : reports/probe_departs_delegation.csv (probe_departs_delegation.py) : km de réseau par
délégation SIG pour chaque départ ; DRD1-3 → Dakar, DRN / DRS / DRCE* / DRCO* → Régions. La région
retenue est celle de la majorité des km, appliquée seulement aux départs des services demandés
(SDRBD par défaut) et seulement si elle diffère de la région de leur service ; les autres départs
gardent la région de leur service (colonne vide).

Corrections manuelles : --dakar / --regions suivis d'identifiants SIRV2 de départs (prioritaires).
Simulation par défaut. Relançable (remet à vide les départs qui ne relèvent plus d'une exception).

Usage :
    python scripts/migration/appliquer_regions_departs.py
    python scripts/migration/appliquer_regions_departs.py --seuil 60 --execute
    python scripts/migration/appliquer_regions_departs.py --regions 812 815 --dakar 820 --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402


def decisions(
    lignes: list[dict[str, str]],
    services: set[str],
    seuil: int,
    forces: dict[int, str],
) -> dict[int, str]:
    """feeder_id → « Dakar » / « Régions » pour les départs en exception (CSV + corrections manuelles).

    Un départ passe en Régions si au moins ``seuil`` % de ses km SIG sont en délégations des
    Régions (et inversement pour Dakar) ; les cas intermédiaires restent sur la région du service.
    """
    resultat: dict[int, str] = {}
    for ligne in lignes:
        if ligne.get("service", "").upper() not in services or not ligne.get(
            "feeder_id_sirv2"
        ):
            continue
        try:
            part_regions = int(ligne.get("part_regions_pct") or "")
        except ValueError:
            continue
        fid = int(ligne["feeder_id_sirv2"])
        if part_regions >= seuil:
            resultat[fid] = "Régions"
        elif 100 - part_regions >= seuil:
            resultat[fid] = "Dakar"
    resultat.update(forces)
    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--fichier", default=None, help="CSV de probe_departs_delegation.py"
    )
    parser.add_argument("--services", nargs="*", default=["SDRBD"])
    parser.add_argument(
        "--seuil", type=int, default=60, help="Part minimale des km (%%) pour trancher"
    )
    parser.add_argument(
        "--regions", nargs="*", type=int, default=[], help="Départs forcés en Régions"
    )
    parser.add_argument(
        "--dakar", nargs="*", type=int, default=[], help="Départs forcés à Dakar"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Écrire en base (sinon simulation)"
    )
    args = parser.parse_args()
    ensure_dirs()
    chemin = (
        Path(args.fichier)
        if args.fichier
        else get_settings().reports_dir / "probe_departs_delegation.csv"
    )
    if not chemin.is_file():
        print(f"{chemin} introuvable : lancer d'abord probe_departs_delegation.py")
        return 1
    with chemin.open(encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    forces = {i: "Régions" for i in args.regions} | {i: "Dakar" for i in args.dakar}
    choix = decisions(lignes, {s.upper() for s in args.services}, args.seuil, forces)

    with get_session() as session:
        regions = {
            str(lib): int(i)
            for i, lib in session.execute(
                text(
                    "SELECT id, libelle FROM dbo.regions WHERE code IN ('DAKAR', 'REGIONS')"
                )
            ).all()
        }
        departs = {
            int(i): (str(lib), str(svc or "—"), r_svc, r_dep)
            for i, lib, svc, r_svc, r_dep in session.execute(
                text(
                    "SELECT f.id, f.libelle, s.code, s.region_id, f.region_id FROM dbo.feeders f "
                    "LEFT JOIN dbo.services s ON s.id = f.service_id"
                )
            ).all()
        }
        ecritures: list[dict[str, Any]] = []
        print(
            "  départ                         | service | région service | région départ → nouvelle"
        )
        for fid, (lib, svc, r_svc, r_dep) in sorted(
            departs.items(), key=lambda kv: kv[1][0]
        ):
            voulue = choix.get(fid)
            cible = regions.get(voulue) if voulue else None
            if cible is not None and cible == r_svc and fid not in forces:
                cible = None  # même région que le service : pas d'exception
            if cible != r_dep:
                ecritures.append({"r": cible, "i": fid})
                libelle = {v: k for k, v in regions.items()}
                print(
                    f"  {lib[:30]:<30} | {svc:<7} | {libelle.get(r_svc, '—'):<13} | "
                    f"{libelle.get(r_dep, '—')} → {libelle.get(cible, '— (région du service)')}"
                )
        print(
            f"\n{len(ecritures)} départ(s) à modifier · {sum(1 for e in ecritures if e['r'])} en exception"
        )
        if args.execute and ecritures:
            session.execute(
                text("UPDATE dbo.feeders SET region_id = :r WHERE id = :i"), ecritures
            )
            session.commit()
            print(
                "Écrit. Relancer backfill_interruption_region.py pour les interruptions."
            )
        else:
            session.rollback()
    rapport = get_settings().reports_dir / "appliquer_regions_departs.json"
    rapport.write_text(
        json.dumps(
            {"simulation": not args.execute, "modifies": len(ecritures)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
