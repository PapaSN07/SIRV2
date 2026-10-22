#!/usr/bin/env python3
"""Diagnostic tronçons workflow × nature × postes impactés."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings


def _url() -> str:
    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def main() -> int:
    engine = create_engine(_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        print("=== Workflow tronçons ===")
        wf = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) total_wf,
                    SUM(CASE WHEN troncon_id IS NOT NULL THEN 1 ELSE 0 END) with_troncon,
                    SUM(CASE WHEN troncon_sig_id IS NOT NULL THEN 1 ELSE 0 END) with_sig
                FROM (SELECT w0.* FROM dbo.workflows w0 INNER JOIN dbo.etapes_workflow e0 ON e0.id = w0.etape_workflow_id AND e0.code = 'tronconnement') AS wt
                """
            )
        ).one()
        print(dict(wf._mapping))

        print("\n=== Par nature (distribution, duree > 5 min, avec postes ITD) ===")
        rows = conn.execute(
            text(
                """
                SELECT n.code, n.libelle,
                       COUNT(DISTINCT i.id) nb_int,
                       SUM(CASE WHEN pi.id IS NOT NULL THEN 1 ELSE 0 END) with_postes,
                       SUM(CASE WHEN w.troncon_id IS NOT NULL THEN 1 ELSE 0 END) with_troncon,
                       SUM(CASE WHEN w.troncon_sig_id IS NOT NULL THEN 1 ELSE 0 END) with_sig,
                       SUM(CASE WHEN w.troncon_id IS NULL AND w.troncon_sig_id IS NULL
                                 AND (w.noeud_amont_libelle IS NOT NULL OR i.localisation IS NOT NULL)
                            THEN 1 ELSE 0 END) with_libelle_only
                FROM dbo.interruptions i
                JOIN dbo.natures n ON n.id = i.nature_id
                LEFT JOIN (SELECT w0.* FROM dbo.workflows w0 INNER JOIN dbo.etapes_workflow e0 ON e0.id = w0.etape_workflow_id AND e0.code = 'tronconnement') w ON w.interruption_id = i.id
                LEFT JOIN dbo.poste_interruptions pi ON pi.interruption_id = i.id
                WHERE i.type_direction = 'distribution'
                  AND i.duree_minutes > 5
                GROUP BY n.code, n.libelle
                ORDER BY nb_int DESC
                """
            )
        ).all()
        for r in rows:
            print(r)

        print("\n=== PERMANENT : échantillon sans tronçon ===")
        rows2 = conn.execute(
            text(
                """
                SELECT TOP 10 i.id, i.numero_interruption, i.duree_minutes, f.libelle AS feeder,
                       i.localisation, w.troncon_id, w.troncon_sig_id,
                       w.noeud_amont_libelle, w.noeud_aval_libelle,
                       (SELECT COUNT(*) FROM dbo.poste_interruptions p WHERE p.interruption_id = i.id) nb_postes
                FROM dbo.interruptions i
                JOIN dbo.natures n ON n.id = i.nature_id AND n.code = 'PERMANENT'
                LEFT JOIN dbo.feeders f ON f.id = i.feeder_id
                LEFT JOIN (SELECT w0.* FROM dbo.workflows w0 INNER JOIN dbo.etapes_workflow e0 ON e0.id = w0.etape_workflow_id AND e0.code = 'tronconnement') w ON w.interruption_id = i.id
                WHERE i.type_direction = 'distribution'
                  AND i.duree_minutes > 5
                  AND w.troncon_id IS NULL AND w.troncon_sig_id IS NULL
                ORDER BY i.id DESC
                """
            )
        ).all()
        for r in rows2:
            print(r)

        print("\n=== Tronçons par feeder (legacy) ===")
        rows3 = conn.execute(
            text(
                """
                SELECT f.id, f.libelle,
                       COUNT(t.id) nb_troncons,
                       COUNT(DISTINCT w.interruption_id) nb_int_wf_troncon
                FROM dbo.feeders f
                LEFT JOIN dbo.troncons t ON t.feeder_id = f.id AND t.is_active = 1
                LEFT JOIN (SELECT w0.* FROM dbo.workflows w0 INNER JOIN dbo.etapes_workflow e0 ON e0.id = w0.etape_workflow_id AND e0.code = 'tronconnement') w ON w.troncon_id = t.id
                GROUP BY f.id, f.libelle
                HAVING COUNT(t.id) > 0
                ORDER BY nb_troncons DESC
                """
            )
        ).all()
        for r in rows3[:15]:
            print(r)

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
