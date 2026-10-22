#!/usr/bin/env python3
"""Diagnostic liaison feeders ↔ troncons / troncons_sig."""

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
        r = conn.execute(
            text(
                "SELECT COUNT(*) total, "
                "SUM(CASE WHEN feeder_id IS NOT NULL THEN 1 ELSE 0 END) with_fid "
                "FROM dbo.troncons_sig"
            )
        ).one()
        print("troncons_sig:", dict(r._mapping))

        m = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT f.id) feeders_total,
                       COUNT(DISTINCT CASE WHEN ts.id IS NOT NULL THEN f.id END) with_sig
                FROM dbo.feeders f
                LEFT JOIN dbo.troncons_sig ts
                  ON ts.feeder_id = f.id
                  OR UPPER(ts.nom_feeder) = UPPER(f.libelle)
                  OR UPPER(ts.nom_feeder) = UPPER(f.code)
                WHERE f.is_active = 1
                """
            )
        ).one()
        print("feeders actifs avec match SIG:", dict(m._mapping))

        rows = conn.execute(
            text(
                """
                SELECT TOP 8 f.id, f.libelle,
                       (SELECT COUNT(*) FROM dbo.troncons t WHERE t.feeder_id=f.id AND t.is_active=1) nb_t,
                       (SELECT COUNT(*) FROM dbo.troncons_sig ts
                        WHERE ts.feeder_id=f.id OR UPPER(ts.nom_feeder)=UPPER(f.libelle)) nb_sig
                FROM dbo.feeders f
                WHERE f.is_active=1
                ORDER BY nb_sig ASC, f.id
                """
            )
        ).all()
        print("\nFeeders sans SIG (échantillon):")
        for row in rows:
            print(row)

        rows2 = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM dbo.troncons_sig ts
                JOIN dbo.feeders f ON f.id = 216
                WHERE ts.feeder_id = f.id
                   OR UPPER(ts.nom_feeder) = UPPER(f.libelle)
                   OR UPPER(ts.nom_feeder) = UPPER(f.code)
                   OR UPPER(ts.nom_feeder) = 'MERMOZ'
                   OR UPPER(f.libelle) LIKE UPPER(ts.nom_feeder) + ' %'
                """
            )
        ).scalar()
        print("SIG match MERMOZ 30KV (new logic approx):", rows2)
        rows3 = conn.execute(
            text("SELECT id, code, libelle FROM dbo.feeders WHERE libelle LIKE '%MERMOZ%'")
        ).all()
        print("feeders MERMOZ:", rows3)

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
