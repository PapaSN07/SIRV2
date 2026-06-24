#!/usr/bin/env python3
"""Configure les comptes dev bcc.dev et brc.dev (idempotent)."""

import asyncio
import json
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_dev_accounts import seed_dev_accounts


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            summary = await seed_dev_accounts(session)
            await session.commit()
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "password": "DevSir123!",
                        "accounts": summary,
                    },
                    indent=2,
                )
            )
            print("\nConnexion :")
            print("  bcc.dev  — rôle BCC  (périmètre : région Dakar / SVC-DKR-01)")
            print("  brc.dev  — rôle BRC  (périmètre : région Thiès / SVC-THS-01)")
            print("  Mot de passe : DevSir123!")
        except Exception as exc:
            await session.rollback()
            print(f"configure_dev_accounts : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
