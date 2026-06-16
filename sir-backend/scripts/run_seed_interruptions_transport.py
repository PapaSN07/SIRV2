"""CLI — charge le seed interruptions transport / OMVG."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_interruptions_transport import seed_interruptions_transport


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_interruptions_transport(session)
            await session.commit()
            print("seed-interruptions-transport : OK")
        except Exception as exc:
            await session.rollback()
            print(f"seed-interruptions-transport : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
