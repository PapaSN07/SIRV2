#!/usr/bin/env python3
"""Région d'exploitation des interruptions de distribution reprises : Dakar (BCC) / Régions (BRC).

SIR v1 porte la région sur l'interruption (colonne « regions » des tables Interruptions et
Interruptions_Histo) ; les services travaillent dans les deux régions. Ce script recopie cette
valeur dans ``interruptions.region_id`` (migration b8c9d0e1f2a3). Relançable : seules les
valeurs différentes sont écrites. Les interruptions saisies dans SIRV2 ont leur région à la
saisie (imposée par le compte BCC / BRC).

Simulation par défaut : répartition par année et par région, avant / après.

Usage (poste ETL avec le pilote ODBC HFSQL) :
    python scripts/migration/backfill_interruption_region.py
    python scripts/migration/backfill_interruption_region.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.transforms.regions import code_region_v1  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402

_TABLES = ("Interruptions", "Interruptions_Histo")
_LOT = 5000


def lire_regions_hfsql() -> tuple[dict[int, str], Counter]:
    """id SIRV2 → code région (DAKAR / REGIONS) et décompte des valeurs SIR v1 non reconnues."""
    correspondance = {
        str(k).split(".")[0]: int(v)
        for k, v in IdMapStore().load("interruptions").items()
    }
    resultat: dict[int, str] = {}
    inconnues: Counter = Counter()
    conn = connect_hfsql()
    try:
        for table in _TABLES:
            rows = fetch_all(conn, f"SELECT NInterruption, regions FROM {table}")
            rattachees = 0
            for row in rows:
                sid = correspondance.get(
                    str(row_get(row, "NInterruption")).split(".")[0]
                )
                if sid is None:
                    continue
                valeur = row_get(row, "regions")
                code = code_region_v1(valeur)
                if code is None:
                    inconnues[str(valeur)] += 1
                    continue
                resultat[sid] = code
                rattachees += 1
            print(
                f"  {table} : {len(rows)} ligne(s), {rattachees} région(s) rattachée(s) à SIRV2",
                flush=True,
            )
    finally:
        conn.close()
    return resultat, inconnues


def corrections(
    actuelles: list[tuple[int, int | None]], cible: dict[int, int]
) -> list[tuple[int, int]]:
    """(region_id, interruption_id) pour les interruptions dont la région diffère de SIR v1."""
    return [
        (cible[iid], iid)
        for iid, region in actuelles
        if iid in cible and region != cible[iid]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--execute", action="store_true", help="Écrire en base (sinon simulation)"
    )
    args = parser.parse_args()
    ensure_dirs()
    print("Lecture SIR v1 (regions)…", flush=True)
    codes, inconnues = lire_regions_hfsql()
    bilan: dict[str, Any] = {
        "simulation": not args.execute,
        "v1_rattachees": len(codes),
    }
    if inconnues:
        print(
            f"  valeurs « regions » non reconnues : {dict(inconnues.most_common(10))}"
        )
        bilan["valeurs_inconnues"] = dict(inconnues.most_common(20))

    with get_session() as session:
        regions = {
            str(c): int(i)
            for i, c in session.execute(text("SELECT id, code FROM dbo.regions")).all()
        }
        libelles = {v: k for k, v in regions.items()}
        manquantes = {"DAKAR", "REGIONS"} - set(regions)
        if manquantes:
            print(f"Régions absentes de SIRV2 : {manquantes} — arrêt.")
            return 1
        cible = {iid: regions[c] for iid, c in codes.items()}
        actuelles = [
            (int(i), int(r) if r is not None else None, int(a))
            for i, r, a in session.execute(
                text(
                    "SELECT id, region_id, YEAR(date_apparition) FROM dbo.interruptions "
                    "WHERE type_direction = 'distribution'"
                )
            ).all()
        ]
        a_corriger = corrections([(i, r) for i, r, _ in actuelles], cible)
        repartition: dict[int, Counter] = defaultdict(Counter)
        for iid, region, annee in actuelles:
            nouvelle = cible.get(iid, region)
            repartition[annee][
                libelles.get(nouvelle, "(sans région)") if nouvelle else "(sans région)"
            ] += 1
        print(
            f"\n{len(actuelles)} interruption(s) de distribution · {len(a_corriger)} région(s) à écrire"
        )
        print("  année | répartition après correction")
        for annee, compte in sorted(repartition.items()):
            print(f"  {annee} | {dict(compte)}")
        bilan.update(interruptions=len(actuelles), a_corriger=len(a_corriger))
        bilan["sans_region_apres"] = sum(
            c.get("(sans région)", 0) for c in repartition.values()
        )

        if args.execute and a_corriger:
            cur = session.connection().connection.cursor()
            cur.fast_executemany = True
            for i in range(0, len(a_corriger), _LOT):
                cur.executemany(
                    "UPDATE dbo.interruptions SET region_id = ? WHERE id = ?",
                    a_corriger[i : i + _LOT],
                )
            cur.close()
            session.commit()
            print(f"{len(a_corriger)} région(s) écrite(s).")
        else:
            session.rollback()

    rapport = get_settings().reports_dir / "backfill_interruption_region.json"
    rapport.write_text(
        json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n" + json.dumps(bilan, ensure_ascii=False))
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
