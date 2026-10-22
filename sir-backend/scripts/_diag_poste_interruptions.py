"""Diag rapide poste_interruptions (colonnes + taux de remplissage)."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    url = settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += ("&" if "?" in url else "?") + "TrustServerCertificate=yes"
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as c:
        cols = c.execute(
            text(
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'poste_interruptions'
                ORDER BY ORDINAL_POSITION
                """
            )
        ).all()
        print("=== COLUMNS ===")
        for r in cols:
            print(f"  {r[0]:25} {r[1]:15} null={r[2]}")

        stats = c.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN feeder_id IS NULL THEN 1 ELSE 0 END) AS null_feeder,
                    SUM(CASE WHEN service_id IS NULL THEN 1 ELSE 0 END) AS null_service,
                    SUM(CASE WHEN poste_source_id IS NULL THEN 1 ELSE 0 END) AS null_ps,
                    SUM(CASE WHEN feeder_id IS NOT NULL THEN 1 ELSE 0 END) AS with_feeder,
                    SUM(CASE WHEN service_id IS NOT NULL THEN 1 ELSE 0 END) AS with_service,
                    SUM(CASE WHEN poste_source_id IS NOT NULL THEN 1 ELSE 0 END) AS with_ps
                FROM dbo.poste_interruptions
                """
            )
        ).mappings().one()
        print("=== STATS ===")
        for k, v in dict(stats).items():
            print(f"  {k}: {v}")

        sample = c.execute(
            text(
                """
                SELECT TOP 5
                    pi.id, pi.interruption_id, pi.poste_id,
                    pi.feeder_id, pi.service_id, pi.poste_source_id,
                    pi.nombre_clients_touches
                FROM dbo.poste_interruptions pi
                ORDER BY pi.id DESC
                """
            )
        ).all()
        print("=== SAMPLE (5 latest) ===")
        for r in sample:
            print(" ", r)
    eng.dispose()


if __name__ == "__main__":
    main()
