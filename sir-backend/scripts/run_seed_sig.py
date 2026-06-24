"""CLI — seed topologie SIG minimal (Docker dev, sans HFSQL)."""

import asyncio
import json
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_sig import seed_sig


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            summary = await seed_sig(session)
            await session.commit()
            print(json.dumps({"status": "ok", "counts": summary}, indent=2))
        except Exception as exc:
            await session.rollback()
            print(f"seed_sig : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
