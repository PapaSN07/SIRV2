"""Test rapide connexion DB profil senelec — usage: SIR_PROFILE=senelec python -m scripts._test_db_senelec"""
import asyncio

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal


async def main() -> None:
    print(f"Profil DB: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")
    async with AsyncSessionLocal() as db:
        ok = (await db.execute(text("SELECT 1"))).scalar_one()
        print(f"SELECT 1 => {ok}")
        count = (await db.execute(text("SELECT COUNT(*) FROM interruptions"))).scalar_one()
        print(f"interruptions: {count}")
        natures = (await db.execute(text("SELECT COUNT(*) FROM natures"))).scalar_one()
        print(f"natures: {natures}")


if __name__ == "__main__":
    asyncio.run(main())
