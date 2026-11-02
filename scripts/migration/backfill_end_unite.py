#!/usr/bin/env python3
"""Corrige l'unité de l'END des interruptions migrées : SIR v1 stocke ENDD en kWh, SIRV2 en MWh.

Constat (diag_interruptions_end.py, juin → octobre 2026) : ENDD / (puissance MW × durée h) vaut
exactement 1 000 sur 20 127 interruptions : ENDD = puissance kW × durée h, donc des kWh. La reprise
le recopiait tel quel dans ``interruptions_distribution.end_mwh`` et
``interruptions_transport.energie_non_fournie_mwh`` : toutes les END migrées étaient 1 000 fois
trop grandes dans les écrans et les rapports (qui multiplient par 1 000 pour afficher des kWh).

Recalcul à partir de SIR v1 (NInterruption, ENDD), donc sans risque de double division si le
script est relancé : END SIRV2 = ENDD / 1000. Les interruptions saisies dans SIRV2 (sans équivalent
SIR v1) ne sont pas touchées.

Simulation par défaut : totaux par année avant / après et exemples.

Usage (poste ETL avec le pilote ODBC HFSQL) :
    python scripts/migration/backfill_end_unite.py
    python scripts/migration/backfill_end_unite.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
from scripts.migration.transforms.rows import row_get  # noqa: E402

_TABLES = (
    "Interruptions",
    "Interruptions_Histo",
    "InterruptionsTransport",
    "Interruptions_OMVG",
)
_LOT = 5000
_TOLERANCE = 0.0005  # MWh

_CIBLES = {
    "distribution": ("dbo.interruptions_distribution", "end_mwh"),
    "transport": ("dbo.interruptions_transport", "energie_non_fournie_mwh"),
}


def _nombre(valeur: Any) -> float | None:
    if valeur is None or str(valeur).strip() == "":
        return None
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def lire_end_hfsql() -> dict[int, float]:
    """id SIRV2 → END en MWh (ENDD SIR v1 / 1000)."""
    correspondance = {
        str(k).split(".")[0]: int(v)
        for k, v in IdMapStore().load("interruptions").items()
    }
    resultat: dict[int, float] = {}
    conn = connect_hfsql()
    try:
        for table in _TABLES:
            try:
                rows = fetch_all(conn, f"SELECT NInterruption, ENDD FROM {table}")
            except Exception as exc:  # noqa: BLE001 — table absente sur cette base
                print(f"  {table} : ignorée ({str(exc)[:80]})")
                continue
            rattachees = 0
            for row in rows:
                sid = correspondance.get(
                    str(row_get(row, "NInterruption")).split(".")[0]
                )
                kwh = _nombre(row_get(row, "ENDD", "endd"))
                if sid is None or kwh is None:
                    continue
                resultat[sid] = kwh / 1000
                rattachees += 1
            print(
                f"  {table} : {len(rows)} ligne(s), {rattachees} END rattachée(s) à SIRV2",
                flush=True,
            )
    finally:
        conn.close()
    return resultat


def corrections(
    actuelles: list[tuple[int, int, float | None]], cible: dict[int, float]
) -> list[tuple[float, int]]:
    """(nouvelle END MWh, interruption_id) pour les END qui diffèrent de ENDD / 1000."""
    return [
        (cible[iid], iid)
        for iid, _, valeur in actuelles
        if iid in cible
        and (valeur is None or abs(float(valeur) - cible[iid]) > _TOLERANCE)
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
    print("Lecture SIR v1 (ENDD)…", flush=True)
    cible = lire_end_hfsql()
    bilan: dict[str, Any] = {
        "simulation": not args.execute,
        "end_v1_rattachees": len(cible),
    }

    with get_session() as session:
        for direction, (table, colonne) in _CIBLES.items():
            actuelles = [
                (int(i), int(a), v)
                for i, a, v in session.execute(
                    text(
                        f"SELECT t.interruption_id, YEAR(i.date_apparition), t.{colonne} FROM {table} t "
                        "JOIN dbo.interruptions i ON i.id = t.interruption_id"
                    )
                ).all()
            ]
            a_corriger = corrections(actuelles, cible)
            par_annee: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
            for iid, annee, valeur in actuelles:
                par_annee[annee][0] += float(valeur or 0)
                par_annee[annee][1] += cible.get(iid, float(valeur or 0))
            print(
                f"\n{direction} : {len(actuelles)} END · {len(a_corriger)} à corriger"
            )
            print("  année |   avant (« MWh »)  |   après (MWh)")
            for annee, (avant, apres) in sorted(par_annee.items()):
                print(f"  {annee} | {avant:>18,.1f} | {apres:>14,.3f}")
            bilan[direction] = {"end": len(actuelles), "a_corriger": len(a_corriger)}
            if args.execute and a_corriger:
                cur = session.connection().connection.cursor()
                cur.fast_executemany = True
                for i in range(0, len(a_corriger), _LOT):
                    cur.executemany(
                        f"UPDATE {table} SET {colonne} = ? WHERE interruption_id = ?",
                        a_corriger[i : i + _LOT],
                    )
                cur.close()
                session.commit()
                print(f"  {len(a_corriger)} END corrigée(s).")
        if not args.execute:
            session.rollback()

    rapport = get_settings().reports_dir / "backfill_end_unite.json"
    rapport.write_text(
        json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n" + json.dumps(bilan, ensure_ascii=False))
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
