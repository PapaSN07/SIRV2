"""CLI — charge le seed indicateurs (nombre_client_mois + démo SAIFI/SAIDI/END)."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_indicateurs import seed_indicateurs


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            print("→ seed_indicateurs …")
            await seed_indicateurs(session)
            await session.commit()
            print("seed-indicateurs : OK — nombre_client_mois + energie_nd + saifi_saidi chargés")
            print("  Compte dev : saqs.dev — mot de passe DevSir123!")
        except Exception as exc:
            await session.rollback()
            print(f"seed-indicateurs : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
