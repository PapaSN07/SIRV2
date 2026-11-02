#!/usr/bin/env python3
"""Région d'exploitation des interruptions de distribution : Dakar (BCC) / Régions (BRC).

Règle SENELEC (02/11/2026) : la région suit le réseau. SDDV (Dakar ville) et SDPG
(Pikine-Guédiawaye) sont à Dakar, les services régionaux (SDRCE*, SDRCO*, SDRN*…) en Régions ;
SDRBD (Rufisque-Bargny-Diamniadio) est à Dakar, mais certains de ses départs touchent les
Régions. La région d'une interruption est donc celle de son poste source, sinon celle de son
service (migration c9d0e1f2a3b4). Même règle que la saisie
(interruption_distribution_repository.region_du_depart).

La colonne « regions » de SIR v1 n'est pas utilisée : elle range par exemple 6 471 interruptions
SDDV de 2026 dans « Régions ».

Simulation par défaut : répartition par année et par service, avant / après. Relançable.

Usage :
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

_LOT = 5000

# Région du départ : poste source (Dakar / Régions), sinon service
_SQL = """
SELECT i.id, i.region_id, YEAR(i.date_apparition) AS annee, ISNULL(s.code, '(sans service)') AS service,
       COALESCE(rp.id, rs.id) AS region_cible,
       CASE WHEN rp.id IS NOT NULL THEN 'poste source' WHEN rs.id IS NOT NULL THEN 'service' ELSE 'aucune' END AS origine
FROM dbo.interruptions i
LEFT JOIN dbo.postes_sources p ON p.id = i.poste_source_id
LEFT JOIN dbo.regions rp ON rp.id = p.region_id AND rp.code IN ('DAKAR', 'REGIONS')
LEFT JOIN dbo.services s ON s.id = i.service_id
LEFT JOIN dbo.regions rs ON rs.id = s.region_id AND rs.code IN ('DAKAR', 'REGIONS')
WHERE i.type_direction = 'distribution'
"""


def corrections(
    lignes: list[tuple[int, int | None, int | None]],
) -> list[tuple[int, int]]:
    """(region_id, interruption_id) quand la région du départ est connue et diffère."""
    return [
        (cible, iid)
        for iid, actuelle, cible in lignes
        if cible is not None and actuelle != cible
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
    with get_session() as session:
        libelles = {
            int(i): str(lib)
            for i, lib in session.execute(
                text("SELECT id, libelle FROM dbo.regions")
            ).all()
        }
        rows = session.execute(text(_SQL)).all()
        a_corriger = corrections(
            [(int(r.id), r.region_id, r.region_cible) for r in rows]
        )
        par_annee: dict[int, Counter] = defaultdict(Counter)
        par_service: dict[str, Counter] = defaultdict(Counter)
        origines: Counter = Counter()
        derniere = max((int(r.annee) for r in rows), default=0)
        for r in rows:
            region = (
                libelles.get(r.region_cible, "(sans région)")
                if r.region_cible
                else "(sans région)"
            )
            par_annee[int(r.annee)][region] += 1
            if int(r.annee) == derniere:
                par_service[r.service][region] += 1
            origines[r.origine] += 1
        print(
            f"{len(rows)} interruption(s) de distribution · {len(a_corriger)} région(s) à écrire"
        )
        print(f"Région prise sur : {dict(origines)}")
        print("\nPar année :")
        for annee, compte in sorted(par_annee.items()):
            print(f"  {annee} | {dict(compte)}")
        print(f"\nPar service ({derniere or '—'}) :")
        for service, compte in sorted(par_service.items()):
            print(f"  {service:<16} | {dict(compte)}")
        bilan: dict[str, Any] = {
            "simulation": not args.execute,
            "interruptions": len(rows),
            "a_corriger": len(a_corriger),
            "origine": dict(origines),
        }
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
            print(f"\n{len(a_corriger)} région(s) écrite(s).")
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
