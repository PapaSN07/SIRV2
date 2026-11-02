#!/usr/bin/env python3
"""Vérification (lecture seule) de la région des postes sources : SIR v1 contre SIRV2.

Pour chaque poste source :
  - région dans SIR v1 (table PostesSources) ;
  - région dans SIRV2 (dbo.postes_sources) ;
  - services des départs (feeders) qui en partent, dans SIR v1 et dans SIRV2, et la région
    qu'ils impliquent (SDDV, SDPG, SDRBD → Dakar ; SDRCE*, SDRCO*, SDRN*, SDDRCO2, DRS → Régions) ;
  - nombre d'interruptions de 2026 ;
et un verdict : cohérent, région SIRV2 différente de SIR v1, ou poste source mixte (départs de
services des deux régions — cas de SDRBD).

Affiche d'abord les colonnes des tables SIR v1, puis le tableau ; détail en CSV.

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_postes_sources.py
"""

from __future__ import annotations

import csv
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
from scripts.migration.transforms.rows import row_get  # noqa: E402

SERVICES_DAKAR = {"SDDV", "SDPG", "SDRBD"}
SERVICES_REGIONS = {
    "SDRCE1",
    "SDRCE2",
    "SDRCO1",
    "SDRCO2",
    "SDRCO3",
    "SDRN",
    "SDRN1",
    "SDRN2",
    "SDDRCO2",
    "DRS",
}


def region_du_service(code: str) -> str | None:
    c = code.strip().upper()
    return (
        "Dakar" if c in SERVICES_DAKAR else "Régions" if c in SERVICES_REGIONS else None
    )


def _cle(valeur: Any) -> str:
    return str(valeur).split(".")[0].strip() if valeur is not None else ""


def _colonne(row: dict[str, Any], *mots: str) -> Any:
    """Première colonne dont le nom contient l'un des mots (insensible à la casse)."""
    for nom, valeur in row.items():
        if any(m in str(nom).lower() for m in mots):
            return valeur
    return None


def verdict(
    region_v1: str | None, region_v2: str | None, regions_services: set[str]
) -> str:
    if len(regions_services) > 1:
        return "mixte (départs des deux régions)"
    attendue = next(iter(regions_services), None) or region_v1
    if attendue is None:
        return "indéterminé"
    if region_v2 != attendue:
        return f"à corriger : SIRV2 {region_v2 or '—'} → {attendue}"
    return "cohérent"


def main() -> int:
    ensure_dirs()
    conn = connect_hfsql()
    try:
        postes_v1 = fetch_all(conn, "SELECT * FROM PostesSources")
        feeders_v1 = fetch_all(conn, "SELECT * FROM Feeders")
        try:
            regions_v1 = {
                _cle(row_get(r, "IDRegions", "IDRegion")): r
                for r in fetch_all(conn, "SELECT * FROM Regions")
            }
        except Exception:  # noqa: BLE001
            regions_v1 = {}
    finally:
        conn.close()
    print(
        f"SIR v1 PostesSources : {len(postes_v1)} ligne(s), colonnes : {list(postes_v1[0]) if postes_v1 else []}"
    )
    print(
        f"SIR v1 Feeders : {len(feeders_v1)} ligne(s), colonnes : {list(feeders_v1[0]) if feeders_v1 else []}"
    )

    def libelle_region_v1(row: dict[str, Any]) -> str | None:
        texte = _colonne(row, "region")
        if texte is None:
            return None
        cle = _cle(texte)
        if cle in regions_v1:  # identifiant de région
            texte = _colonne(regions_v1[cle], "libelle", "region") or texte
        t = str(texte).strip()
        return t or None

    # Services des départs de chaque poste source dans SIR v1
    services_v1: dict[str, Counter] = defaultdict(Counter)
    for f in feeders_v1:
        ps = _cle(row_get(f, "IDPosteSource", "idpostesource"))
        services_v1[ps][
            str(row_get(f, "Service", "service") or "").strip().upper()
        ] += 1

    legacy_par_sir = {
        int(v): str(k)
        for k, v in IdMapStore().load("postes_sources").items()
        if str(v).isdigit()
    }
    with get_session() as session:
        v2 = session.execute(
            text(
                "SELECT p.id, p.code, p.libelle, ISNULL(r.libelle, '') AS region, "
                "(SELECT COUNT(*) FROM dbo.interruptions i WHERE i.poste_source_id = p.id "
                " AND i.type_direction = 'distribution' AND YEAR(i.date_apparition) = 2026) AS nb_2026 "
                "FROM dbo.postes_sources p LEFT JOIN dbo.regions r ON r.id = p.region_id"
            )
        ).all()
        services_v2: dict[int, Counter] = defaultdict(Counter)
        for ps_id, code in session.execute(
            text(
                "SELECT f.poste_source_id, s.code FROM dbo.feeders f JOIN dbo.services s ON s.id = f.service_id"
            )
        ).all():
            services_v2[int(ps_id)][str(code).upper()] += 1
        session.rollback()

    par_legacy = {
        _cle(row_get(p, "IDPosteSource", "IDPostesSources", "idpostesource")): p
        for p in postes_v1
    }
    lignes: list[dict[str, Any]] = []
    for r in v2:
        legacy = legacy_par_sir.get(int(r.id), "")
        p1 = par_legacy.get(legacy, {})
        region_v1 = libelle_region_v1(p1) if p1 else None
        svc = services_v2.get(int(r.id), Counter()) + services_v1.get(legacy, Counter())
        regions_services = {x for x in (region_du_service(c) for c in svc) if x}
        lignes.append(
            {
                "poste_source": r.libelle,
                "id_sirv2": r.id,
                "id_v1": legacy,
                "region_v1": region_v1 or "",
                "region_sirv2": r.region,
                "services_departs": ", ".join(
                    f"{c} ({n})" for c, n in svc.most_common()
                ),
                "interruptions_2026": r.nb_2026,
                "verdict": verdict(region_v1, r.region or None, regions_services),
            }
        )
    lignes.sort(
        key=lambda x: (x["verdict"] == "cohérent", -int(x["interruptions_2026"]))
    )
    bilan = Counter(x["verdict"].split(" :")[0] for x in lignes)
    print(f"\n{len(lignes)} poste(s) source(s) SIRV2 : {dict(bilan)}")
    print(
        "\n  poste source                 | v1        | SIRV2     | interr. 2026 | services des départs | verdict"
    )
    for x in lignes:
        if x["verdict"] == "cohérent" and not x["interruptions_2026"]:
            continue
        print(
            f"  {str(x['poste_source'])[:28]:<28} | {x['region_v1'][:9]:<9} | {x['region_sirv2'][:9]:<9} | "
            f"{x['interruptions_2026']:>12} | {x['services_departs'][:40]:<40} | {x['verdict']}"
        )

    chemin = get_settings().reports_dir / "probe_postes_sources.csv"
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f, fieldnames=list(lignes[0]) if lignes else ["poste_source"], delimiter=";"
        )
        w.writeheader()
        w.writerows(lignes)
    print(f"\nDétail : {chemin}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
