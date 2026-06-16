"""CLI — charge le seed réseau distribution en base."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_reseau import seed_reseau


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_reseau(session)
            await session.commit()
            print("seed_reseau : OK — réseau distribution chargé")
        except Exception as exc:
            await session.rollback()
            print(f"seed_reseau : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
