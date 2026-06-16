"""CLI — charge le seed interruptions distribution."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_interruptions import seed_interruptions


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            print("→ seed_interruptions …")
            await seed_interruptions(session)
            await session.commit()
            print("seed-interruptions : OK — 3 interruptions distribution chargées")
            print("  Comptes dev : bcc.dev / superviseur.dev — mot de passe DevSir123!")
        except Exception as exc:
            await session.rollback()
            print(f"seed-interruptions : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
