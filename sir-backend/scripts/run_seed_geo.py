"""CLI — charge le seed géographique en base de données."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_geo import seed_geo


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_geo(session)
            await session.commit()
            print("seed_geo : OK — hiérarchie géographique chargée")
        except Exception as exc:
            await session.rollback()
            print(f"seed_geo : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
