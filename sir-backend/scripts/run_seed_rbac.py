"""CLI — charge le seed RBAC en base de données."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_rbac import seed_rbac


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_rbac(session)
            await session.commit()
            print("seed_rbac : OK — rôles et permissions chargés")
        except Exception as exc:
            await session.rollback()
            print(f"seed_rbac : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
