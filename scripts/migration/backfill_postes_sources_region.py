#!/usr/bin/env python3
"""Corrige la région des postes sources SIRV2 d'après les services de leurs départs.

La région des postes sources de SIRV2 n'est pas fiable (postes des services régionaux enregistrés
à Dakar). Règle SENELEC (02/11/2026) : SDDV, SDPG, SDRBD → Dakar ; services régionaux → Régions
(services rattachés à leur région par la migration c9d0e1f2a3b4). Un poste source prend la région
des services de ses départs (feeders) :
  - tous ses départs dans une région → cette région ;
  - départs des deux régions (« mixte », ex. SDRBD) → la région majoritaire, et le poste est
    listé pour vérification ;
  - aucun départ rattaché à un service de Dakar / Régions → inchangé.

Effets : le formulaire de saisie propose à un BCC les postes sources de Dakar, à un BRC ceux des
Régions ; la région d'une interruption sans service se prend sur son poste source.

Simulation par défaut. Relançable.

Usage :
    python scripts/migration/backfill_postes_sources_region.py
    python scripts/migration/backfill_postes_sources_region.py --execute
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

_DEPARTS = """
SELECT f.poste_source_id, s.region_id, s.code
FROM dbo.feeders f
JOIN dbo.services s ON s.id = f.service_id
JOIN dbo.regions r ON r.id = s.region_id AND r.code IN ('DAKAR', 'REGIONS')
WHERE f.poste_source_id IS NOT NULL
"""


def region_cible(departs: Counter) -> tuple[int | None, bool]:
    """(région majoritaire des départs, poste mixte ?) ; à égalité, la plus petite id (Dakar)."""
    if not departs:
        return None, False
    region = sorted(departs.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return region, len(departs) > 1


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
        postes = {
            int(i): (str(lib), int(r) if r is not None else None)
            for i, lib, r in session.execute(
                text("SELECT id, libelle, region_id FROM dbo.postes_sources")
            ).all()
        }
        departs: dict[int, Counter] = defaultdict(Counter)
        services: dict[int, Counter] = defaultdict(Counter)
        for ps, region, code in session.execute(text(_DEPARTS)).all():
            departs[int(ps)][int(region)] += 1
            services[int(ps)][str(code)] += 1

        a_corriger: list[tuple[int, int]] = []
        mixtes: list[dict[str, Any]] = []
        sans_depart = 0
        passages: Counter = Counter()
        for ps_id, (libelle, actuelle) in sorted(
            postes.items(), key=lambda kv: kv[1][0]
        ):
            cible, mixte = region_cible(departs.get(ps_id, Counter()))
            if cible is None:
                sans_depart += 1
                continue
            if mixte:
                mixtes.append(
                    {
                        "poste_source": libelle,
                        "region_retenue": libelles.get(cible),
                        "services": dict(services[ps_id]),
                    }
                )
            if cible != actuelle:
                a_corriger.append((cible, ps_id))
                passages[
                    f"{libelles.get(actuelle, '—') if actuelle else '—'} → {libelles.get(cible)}"
                ] += 1

        print(
            f"{len(postes)} poste(s) source(s) · {len(a_corriger)} région(s) à corriger · "
            f"{len(mixtes)} mixte(s) · {sans_depart} sans départ rattaché (inchangés)"
        )
        for passage, n in passages.most_common():
            print(f"  {passage} : {n}")
        if mixtes:
            print(
                "\nPostes sources mixtes (départs des deux régions) — région majoritaire retenue, à vérifier :"
            )
            for m in mixtes:
                print(
                    f"  {m['poste_source'][:32]:<32} → {m['region_retenue']:<8} | {m['services']}"
                )

        if args.execute and a_corriger:
            session.execute(
                text("UPDATE dbo.postes_sources SET region_id = :r WHERE id = :i"),
                [{"r": r, "i": i} for r, i in a_corriger],
            )
            session.commit()
            print(f"\n{len(a_corriger)} poste(s) source(s) corrigé(s).")
        else:
            session.rollback()

    bilan = {
        "simulation": not args.execute,
        "postes_sources": len(postes),
        "a_corriger": len(a_corriger),
        "mixtes": mixtes,
        "sans_depart": sans_depart,
    }
    rapport = get_settings().reports_dir / "backfill_postes_sources_region.json"
    rapport.write_text(
        json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
