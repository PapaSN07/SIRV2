#!/usr/bin/env python3
"""Sonde (lecture seule) : où trouver les postes coupés des interruptions récentes ?

Pour chaque mois depuis --depuis, compte les interruptions de distribution reprises dans SIRV2 :
  - qui ont déjà leurs postes dans SIRV2 (poste_interruptions) ;
  - présentes dans IndicateursTransportDistribution.PosteInterruption (source de l'import, Power BI) ;
  - présentes dans SIR v1 HFSQL PosteInterruption (source d'origine) ;
et, pour celles absentes d'ITD, leur statut (en cours, clôturée, validée…).

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_postes_delta.py --depuis 2026-06-01
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.itd_sqlserver import connect_itd  # noqa: E402

_LOT = 200


def _presents(cur, table: str, legacy_ids: list[int], lot: int = _LOT) -> set[int]:
    """NInterruption de la liste présents dans la table (requêtes IN par lots)."""
    trouves: set[int] = set()
    for i in range(0, len(legacy_ids), lot):
        morceau = legacy_ids[i : i + lot]
        cur.execute(
            f"SELECT DISTINCT NInterruption FROM {table} WHERE NInterruption IN ({','.join(str(x) for x in morceau)})"
        )
        trouves.update(int(r[0]) for r in cur.fetchall() if r[0] is not None)
    return trouves


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--depuis", required=True, type=lambda s: datetime.strptime(s, "%Y-%m-%d")
    )
    args = parser.parse_args()

    legacy_par_sir = {
        int(v): int(k)
        for k, v in IdMapStore().load("interruptions").items()
        if str(k).isdigit()
    }
    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT i.id, i.date_apparition, i.statut, "
                "CASE WHEN EXISTS (SELECT 1 FROM dbo.poste_interruptions pi WHERE pi.interruption_id = i.id) "
                "THEN 1 ELSE 0 END AS a_postes "
                "FROM dbo.interruptions i WHERE i.type_direction = 'distribution' AND i.date_apparition >= :d"
            ),
            {"d": args.depuis},
        ).all()
        session.rollback()
    par_mois: dict[str, list] = defaultdict(list)
    for r in rows:
        legacy = legacy_par_sir.get(int(r.id))
        if legacy is not None:
            par_mois[f"{r.date_apparition:%Y-%m}"].append(
                (legacy, r.statut, bool(r.a_postes))
            )
    tous = sorted({lg for v in par_mois.values() for lg, _, _ in v})
    print(
        f"{len(rows)} interruption(s) de distribution SIRV2 depuis le {args.depuis:%d/%m/%Y}, {len(tous)} reprise(s)"
    )

    itd = connect_itd()
    try:
        cur = itd.cursor()
        dans_itd = _presents(cur, "dbo.PosteInterruption", tous, 1000)
        cur.execute("SELECT MAX(NInterruption), COUNT(*) FROM dbo.PosteInterruption")
        max_itd, total_itd = cur.fetchone()
    finally:
        itd.close()
    print(f"ITD PosteInterruption : {total_itd} lignes, NInterruption max {max_itd}")

    hf = connect_hfsql()
    try:
        dans_hfsql = _presents(hf.cursor(), "PosteInterruption", tous)
    except Exception as exc:  # noqa: BLE001
        print(f"HFSQL PosteInterruption illisible : {str(exc)[:200]}")
        dans_hfsql = set()
    finally:
        hf.close()

    print(
        "\n  mois | reprises | avec postes SIRV2 | dans ITD | dans HFSQL | absentes d'ITD par statut"
    )
    for mois in sorted(par_mois):
        v = par_mois[mois]
        absents = Counter(st for lg, st, _ in v if lg not in dans_itd)
        print(
            f"  {mois} | {len(v)} | {sum(1 for *_, a in v if a)} | {sum(1 for lg, *_ in v if lg in dans_itd)} | "
            f"{sum(1 for lg, *_ in v if lg in dans_hfsql)} | {dict(absents)}"
        )
    print(
        f"\nNInterruption SIR v1 le plus récent repris : {max(tous) if tous else '—'}"
    )
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
