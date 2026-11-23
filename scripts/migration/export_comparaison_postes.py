#!/usr/bin/env python3
"""Export (lecture seule) des postes SIRV2, des nœuds SIG et des postes des schémas unifilaires.

Sert à comparer les trois sources (carte fusionnée, rapport de comparaison SIR / schéma / SIG).
Rien n'est écrit en base. Les fichiers vont dans scripts/migration/reports/comparaison_postes/ :
    postes_sirv2.csv, noeuds_sig.csv, schemas.csv, schema_postes.csv, schema_graphe_<id>.json.gz

Usage (poste SENELEC, accès à la base SIRV2) :
    python scripts/migration/export_comparaison_postes.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402

SORTIE = _ROOT / "scripts" / "migration" / "reports" / "comparaison_postes"

REQUETES = {
    "postes_sirv2": """
        SELECT p.id, p.code, p.libelle, p.is_active, p.nombre_clients, p.puissance_kva,
               p.feeder_id, f.code AS feeder_code, f.libelle AS feeder, f.is_active AS feeder_actif,
               ps.id AS poste_source_id, ps.libelle AS poste_source,
               COALESCE(sp.libelle, sf.libelle) AS service, COALESCE(rp.libelle, rf.libelle) AS region
        FROM dbo.postes p
        LEFT JOIN dbo.feeders f ON f.id = p.feeder_id
        LEFT JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id
        LEFT JOIN dbo.services sp ON sp.id = p.service_id
        LEFT JOIN dbo.services sf ON sf.id = f.service_id
        LEFT JOIN dbo.regions rp ON rp.id = sp.region_id
        LEFT JOIN dbo.regions rf ON rf.id = sf.region_id
    """,
    "noeuds_sig": """
        SELECT id, nom, nom_feeder, feeder_id, station, UPPER(TRIM(categorie)) AS categorie,
               coord_x, coord_y, delegation, region, puissance, famille_poste
        FROM dbo.noeuds_sig
    """,
    "schemas": "SELECT id, nom, region_id, nb_postes FROM dbo.schemas_unifilaires WHERE is_active = 1",
    "schema_postes": """
        SELECT sp.schema_id, sp.rang, sp.libelle, sp.forme, sp.puissance_kva, sp.poste_id, sp.rapprochement,
               (sp.x0 + sp.x1) / 2 AS x, (sp.y0 + sp.y1) / 2 AS y
        FROM dbo.schema_unifilaire_postes sp
        JOIN dbo.schemas_unifilaires s ON s.id = sp.schema_id AND s.is_active = 1
    """,
}


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    with get_session() as session:
        for nom, sql in REQUETES.items():
            resultat = session.execute(text(sql))
            colonnes = list(resultat.keys())
            lignes = resultat.all()
            with (SORTIE / f"{nom}.csv").open("w", encoding="utf-8-sig", newline="") as f:
                ecrivain = csv.writer(f, delimiter=";")
                ecrivain.writerow(colonnes)
                ecrivain.writerows(lignes)
            print(f"{nom} : {len(lignes)} lignes")
        for schema_id, graphe in session.execute(
            text("SELECT id, graphe FROM dbo.schemas_unifilaires WHERE is_active = 1")
        ).all():
            (SORTIE / f"schema_graphe_{schema_id}.json.gz").write_bytes(bytes(graphe))
            print(f"graphe du schéma {schema_id} : {len(graphe) // 1024} Ko")
    print(f"Fichiers : {SORTIE}")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
