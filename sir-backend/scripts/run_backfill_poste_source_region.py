"""Backfill postes_sources.region_id depuis feeders → services → région."""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


_BACKFILL_SQL = text(
    """
    UPDATE ps
    SET region_id = src.region_id
    FROM dbo.postes_sources ps
    INNER JOIN (
        SELECT f.poste_source_id, MIN(d.region_id) AS region_id
        FROM dbo.feeders f
        INNER JOIN dbo.services s ON s.id = f.service_id
        INNER JOIN dbo.agences a ON a.id = s.agence_id
        INNER JOIN dbo.delegations d ON d.id = a.delegation_id
        WHERE f.poste_source_id IS NOT NULL
          AND d.region_id IS NOT NULL
        GROUP BY f.poste_source_id
    ) src ON src.poste_source_id = ps.id
    WHERE ps.region_id IS NULL
    """
)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        before = (
            await db.execute(
                text("SELECT COUNT(*) FROM dbo.postes_sources WHERE region_id IS NULL")
            )
        ).scalar_one()
        await db.execute(_BACKFILL_SQL)
        await db.commit()
        after = (
            await db.execute(
                text("SELECT COUNT(*) FROM dbo.postes_sources WHERE region_id IS NULL")
            )
        ).scalar_one()
        dakar = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM dbo.postes_sources "
                    "WHERE is_active = 1 AND region_id = 1"
                )
            )
        ).scalar_one()
        print(f"postes_sources sans region_id: {before} -> {after}")
        print(f"postes_sources actifs Dakar (region_id=1): {dakar}")


if __name__ == "__main__":
    asyncio.run(main())
