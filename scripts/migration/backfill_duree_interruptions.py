#!/usr/bin/env python3
"""Corrige la durée des interruptions migrées à partir de HFSQL ``dureeHeure``.

La migration lisait ``DureeInterruption`` comme des minutes : c'est une durée WinDev d'une
autre unité, d'où des durées de plusieurs milliers d'heures et un SAIDI faux. La durée de
référence est ``dureeHeure`` (heures), celle que Power BI utilise pour SAIDI.

Lecture HFSQL (NInterruption, dureeHeure) des tables Interruptions, Interruptions_Histo,
InterruptionsTransport et Interruptions_OMVG ; rattachement par la table de correspondance
« interruptions » ; mise à jour de ``interruptions.duree_minutes`` quand elle diffère.
Les interruptions saisies dans SIRV2 (sans équivalent HFSQL) ne sont pas touchées.

Simulation par défaut. Tester sur une copie de la base avant --execute.

Usage (poste ETL avec le pilote ODBC HFSQL) :
    python scripts/migration/backfill_duree_interruptions.py               # simulation
    python scripts/migration/backfill_duree_interruptions.py --depuis 2024 # à partir de 2024
    python scripts/migration/backfill_duree_interruptions.py --execute
"""

from __future__ import annotations

import argparse
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
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.transforms.dates import duree_minutes_interruption  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402

_TABLES = ("Interruptions", "Interruptions_Histo", "InterruptionsTransport", "Interruptions_OMVG")
_LOT = 1000


def lire_durees_hfsql() -> dict[int, float]:
    """id SIRV2 → dureeHeure HFSQL."""
    correspondance = {str(k).split(".")[0]: int(v) for k, v in IdMapStore().load("interruptions").items()}
    durees: dict[int, float] = {}
    conn = connect_hfsql()
    try:
        for table in _TABLES:
            try:
                rows = fetch_all(conn, f"SELECT NInterruption, dureeHeure FROM {table}")
            except Exception as exc:  # table absente sur cette base
                print(f"  {table} : ignorée ({str(exc)[:80]})")
                continue
            rattachees = 0
            for row in rows:
                sid = correspondance.get(str(row_get(row, "NInterruption")).split(".")[0])
                if sid is None:
                    continue
                try:
                    durees[sid] = float(str(row_get(row, "dureeHeure") or 0).replace(",", "."))
                except ValueError:
                    continue
                rattachees += 1
            print(f"  {table} : {len(rows)} ligne(s), {rattachees} rattachée(s) à SIRV2")
    finally:
        conn.close()
    return durees


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    parser.add_argument("--depuis", type=int, default=2000, help="Première année (date d'apparition)")
    args = parser.parse_args()
    ensure_dirs()

    print("Lecture HFSQL (dureeHeure)…")
    durees = lire_durees_hfsql()
    bilan: dict[str, Any] = {"simulation": not args.execute, "hfsql_rattachees": len(durees)}

    with get_session() as session:
        actuelles = session.execute(
            text(
                "SELECT id, duree_minutes, date_apparition, date_remise FROM dbo.interruptions "
                "WHERE YEAR(date_apparition) >= :a"
            ),
            {"a": args.depuis},
        ).all()
        corrections: list[dict[str, int]] = []
        exemples: list[dict[str, Any]] = []
        sans_duree = 0
        for sid, minutes, apparition, remise in actuelles:
            if sid not in durees:
                continue
            nouvelle = duree_minutes_interruption(durees[sid], apparition, remise)
            if nouvelle is None:
                sans_duree += 1
                continue
            if nouvelle != minutes:
                corrections.append({"id": int(sid), "m": nouvelle})
                if len(exemples) < 10:
                    exemples.append({"id": sid, "avant_h": round((minutes or 0) / 60, 2), "apres_h": round(nouvelle / 60, 2)})
        bilan.update(
            interruptions_sirv2=len(actuelles),
            a_corriger=len(corrections),
            sans_duree_hfsql_ni_dates=sans_duree,
        )
        print(f"\n{len(actuelles)} interruption(s) SIRV2 depuis {args.depuis} · "
              f"{len(corrections)} durée(s) à corriger · {sans_duree} sans durée exploitable")
        for e in exemples:
            print(f"  id {e['id']:>8} : {e['avant_h']:>10} h → {e['apres_h']} h")

        if args.execute and corrections:
            for i in range(0, len(corrections), _LOT):
                session.execute(
                    text("UPDATE dbo.interruptions SET duree_minutes = :m WHERE id = :id"),
                    corrections[i : i + _LOT],
                )
                session.commit()
            print(f"{len(corrections)} durée(s) corrigée(s).")
        else:
            session.rollback()

    rapport = get_settings().reports_dir / "backfill_duree_interruptions.json"
    rapport.write_text(json.dumps(bilan, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False))
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
