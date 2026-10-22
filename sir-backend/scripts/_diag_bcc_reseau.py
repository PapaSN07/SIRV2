"""Diagnostic BCC — périmètre et postes sources."""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        users = (
            await db.execute(
                text(
                    """
                    SELECT u.login, r.nom, ur.scope_service_id
                    FROM dbo.utilisateurs u
                    JOIN dbo.user_roles ur ON ur.utilisateur_id = u.id
                    JOIN dbo.roles r ON r.id = ur.role_id
                    WHERE r.nom = 'BCC' OR u.login LIKE '%bcc%'
                    """
                )
            )
        ).all()
        print("Comptes BCC:", users)

        regions = (
            await db.execute(text("SELECT id, code, libelle FROM dbo.regions"))
        ).all()
        print("Regions:", regions)

        ps_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM dbo.postes_sources WHERE is_active = 1")
            )
        ).scalar_one()
        print("postes_sources actifs:", ps_count)

        by_region = (
            await db.execute(
                text(
                    """
                    SELECT region_id, COUNT(*) AS n
                    FROM dbo.postes_sources WHERE is_active = 1
                    GROUP BY region_id ORDER BY n DESC
                    """
                )
            )
        ).all()
        print("postes_sources par region_id:", by_region)

        for login, role, scope in users[:3]:
            if scope is None:
                continue
            n = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM dbo.postes_sources "
                        "WHERE is_active = 1 AND region_id = :rid"
                    ),
                    {"rid": scope},
                )
            ).scalar_one()
            print(f"  scope={scope} -> postes_sources pour region_id={scope}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
