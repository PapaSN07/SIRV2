#!/usr/bin/env python3
"""Sonde (lecture seule) : répartition Dakar (BCC) / Régions (BRC) dans SIR v1 et SIRV2.

SIR v1 distingue deux « régions » d'exploitation : Dakar (BCC) et Régions (les autres régions,
BRC). Le contrôle diag_interruptions_end.py a rangé toutes les interruptions de juin → octobre
2026 dans Dakar : cette sonde vérifie si c'est la réalité ou un mauvais rattachement des
services SIRV2.

Affiche :
  - SIRV2 : services par région (avec le nombre d'interruptions de 2026 et de clients d'octobre) ;
  - SIRV2 : interruptions de distribution par région et par année ;
  - SIR v1 : interruptions 2026 par valeur de la colonne « regions » et par service.

Usage :
    python scripts/migration/probe_regions.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402


def main() -> int:
    with get_session() as session:
        print("=== SIRV2 : régions")
        for ident, code, libelle in session.execute(
            text("SELECT id, code, libelle FROM dbo.regions ORDER BY id")
        ).all():
            print(f"  {ident} · {code} · {libelle}")

        print("\n=== SIRV2 : services par région (interruptions 2026, clients 10/2026)")
        rows = session.execute(
            text(
                "SELECT ISNULL(r.libelle, '(sans région)') AS region, s.id, s.code, s.libelle, "
                "(SELECT COUNT(*) FROM dbo.interruptions i WHERE i.service_id = s.id "
                " AND i.type_direction = 'distribution' AND YEAR(i.date_apparition) = 2026) AS nb_2026, "
                "(SELECT SUM(CAST(n.nombre_clients AS BIGINT)) FROM dbo.nombre_client_mois n "
                " WHERE n.service_id = s.id AND n.annee = 2026 AND n.mois = 10) AS clients_10 "
                "FROM dbo.services s LEFT JOIN dbo.regions r ON r.id = s.region_id ORDER BY region, s.libelle"
            )
        ).all()
        for r in rows:
            print(
                f"  {r.region:<14} | {r.id:>4} | {r.code:<10} | {r.libelle[:30]:<30} | {r.nb_2026:>6} | {r.clients_10 or ''}"
            )

        print("\n=== SIRV2 : interruptions de distribution par région et par année")
        for region, annee, nb in session.execute(
            text(
                "SELECT ISNULL(r.libelle, '(sans région)'), YEAR(i.date_apparition), COUNT(*) "
                "FROM dbo.interruptions i "
                "LEFT JOIN dbo.regions r ON r.id = i.region_id WHERE i.type_direction = 'distribution' "
                "GROUP BY ISNULL(r.libelle, '(sans région)'), YEAR(i.date_apparition) ORDER BY 2, 1"
            )
        ).all():
            print(f"  {annee} · {region:<14} · {nb}")
        print(
            "\n=== SIRV2 : délégations (région) et contrats du dernier mois de la base clients"
        )
        for code, libelle, region, agences, contrats in session.execute(
            text(
                "SELECT d.code, d.libelle, ISNULL(r.libelle, '(sans région)'), COUNT(DISTINCT a.id), "
                "SUM(CAST(c.nb_contrats AS BIGINT)) FROM dbo.delegations d "
                "LEFT JOIN dbo.regions r ON r.id = d.region_id LEFT JOIN dbo.agences a ON a.delegation_id = d.id "
                "LEFT JOIN dbo.contrats_unites_releve c ON c.agence_id = a.id AND c.annee * 100 + c.mois = "
                "(SELECT MAX(annee * 100 + mois) FROM dbo.contrats_unites_releve) "
                "GROUP BY d.code, d.libelle, ISNULL(r.libelle, '(sans région)') ORDER BY 3, 1"
            )
        ).all():
            print(
                f"  {region:<14} | {code:<8} | {libelle[:28]:<28} | {agences:>3} agence(s) | {contrats or 0:>9} contrats"
            )
        session.rollback()

    print("\n=== SIR v1 : interruptions 2026 par colonne « regions » et par service")
    conn = connect_hfsql()
    try:
        lignes = fetch_all(
            conn,
            "SELECT regions, Service FROM Interruptions WHERE DateApparition >= '20260101'",
        )
    finally:
        conn.close()
    par_region = Counter(str(row_get(r, "regions") or "(vide)").strip() for r in lignes)
    par_service = Counter(
        (
            str(row_get(r, "regions") or "(vide)").strip(),
            str(row_get(r, "Service") or "(vide)").strip(),
        )
        for r in lignes
    )
    print(f"  {len(lignes)} interruption(s) : {dict(par_region)}")
    for (region, service), nb in sorted(par_service.items()):
        print(f"  {region:<14} | {service[:30]:<30} | {nb}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
