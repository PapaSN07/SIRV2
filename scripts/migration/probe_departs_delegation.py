#!/usr/bin/env python3
"""Sonde (lecture seule) : part de chaque délégation dans le réseau de chaque départ (Troncon_SIG).

Seule Troncon_SIG porte la délégation (PosteSource_SIG et FEEDERS_SIG n'en ont pas). La table
répète des tronçons (même objectid sous plusieurs départs) : on dédoublonne par
(départ, id_troncon_sig) et on pondère par la longueur (shape_leng).

Délégations : DRD1, DRD2, DRD3 → Dakar ; DRN, DRS, DRCE1, DRCE2, DRCO, DRCO2 (DRCOY) → Régions.

Affiche, pour les départs des services demandés (SDRBD par défaut), la répartition en km par
délégation, la part Dakar / Régions et la région majoritaire proposée ; tous les départs en CSV.

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_departs_delegation.py
    python scripts/migration/probe_departs_delegation.py --services SDRBD SDDV SDPG
"""

from __future__ import annotations

import argparse
import csv
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
from scripts.migration.probe_sig_regions import cle_nom  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402

DELEGATIONS_DAKAR = {"DRD1", "DRD2", "DRD3"}
DELEGATIONS_REGIONS = {"DRN", "DRS", "DRCE1", "DRCE2", "DRCO", "DRCO2", "DRCOY"}


def region_delegation(code: str) -> str | None:
    c = code.strip().upper()
    return (
        "Dakar"
        if c in DELEGATIONS_DAKAR
        else "Régions"
        if c in DELEGATIONS_REGIONS
        else None
    )


def repartition(km_par_delegation: dict[str, float]) -> tuple[float, float, str | None]:
    """(km Dakar, km Régions, région majoritaire en km)."""
    dakar = sum(
        v for d, v in km_par_delegation.items() if region_delegation(d) == "Dakar"
    )
    regions = sum(
        v for d, v in km_par_delegation.items() if region_delegation(d) == "Régions"
    )
    if dakar == regions == 0:
        return 0.0, 0.0, None
    return dakar, regions, "Dakar" if dakar >= regions else "Régions"


def _f(valeur: Any) -> float:
    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--services",
        nargs="*",
        default=["SDRBD"],
        help="Services à détailler à l'écran",
    )
    args = parser.parse_args()
    ensure_dirs()
    conn = connect_hfsql()
    try:
        rows = fetch_all(
            conn,
            "SELECT nomfeeder, delegation, id_troncon_sig, shape_leng FROM Troncon_SIG",
        )
    finally:
        conn.close()
    vus: set[tuple[str, str]] = set()
    km: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        depart = str(row_get(r, "nomfeeder") or "").strip()
        cle = (cle_nom(depart), str(row_get(r, "id_troncon_sig")))
        if not depart or cle in vus:
            continue
        vus.add(cle)
        km[depart][str(row_get(r, "delegation") or "").strip().upper() or "(vide)"] += (
            _f(row_get(r, "shape_leng")) / 1000
        )
    print(
        f"Troncon_SIG : {len(rows)} ligne(s), {len(vus)} tronçon(s) distinct(s) par départ, {len(km)} départ(s)"
    )

    with get_session() as session:
        feeders = {
            cle_nom(lib): (int(i), str(svc or "—"))
            for i, lib, svc in session.execute(
                text(
                    "SELECT f.id, f.libelle, s.code FROM dbo.feeders f LEFT JOIN dbo.services s ON s.id = f.service_id"
                )
            ).all()
        }
        session.rollback()

    lignes: list[dict[str, Any]] = []
    for depart, par_deleg in km.items():
        fid, service = feeders.get(cle_nom(depart), (None, "absent SIRV2"))
        dakar, regions, majoritaire = repartition(par_deleg)
        total = dakar + regions
        lignes.append(
            {
                "depart": depart,
                "feeder_id_sirv2": fid or "",
                "service": service,
                "km_dakar": round(dakar, 1),
                "km_regions": round(regions, 1),
                "part_regions_pct": round(100 * regions / total) if total else "",
                "region_proposee": majoritaire or "",
                "detail": ", ".join(
                    f"{d} {v:.1f} km"
                    for d, v in sorted(par_deleg.items(), key=lambda kv: -kv[1])
                ),
            }
        )
    lignes.sort(key=lambda x: (x["service"], x["depart"]))
    voulus = {s.upper() for s in args.services}
    print(
        "\n  départ                         | service | km Dakar | km Régions | % Régions | proposée | détail"
    )
    for x in lignes:
        if x["service"].upper() not in voulus:
            continue
        print(
            f"  {x['depart'][:30]:<30} | {x['service']:<7} | {x['km_dakar']:>8} | {x['km_regions']:>10} | "
            f"{x['part_regions_pct']:>9} | {x['region_proposee']:<8} | {x['detail'][:70]}"
        )
    chemin = get_settings().reports_dir / "probe_departs_delegation.csv"
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f, fieldnames=list(lignes[0]) if lignes else ["depart"], delimiter=";"
        )
        w.writeheader()
        w.writerows(lignes)
    print(f"\nTous les départs : {chemin}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
