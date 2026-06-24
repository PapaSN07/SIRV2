"""CLI — charge tous les seeds dev (RBAC → geo → réseau)."""

import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models.seed.seed_dev_accounts import seed_dev_accounts
from app.models.seed.seed_geo import seed_geo
from app.models.seed.seed_rbac import seed_rbac
from app.models.seed.seed_reseau import seed_reseau


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            print("→ seed_rbac …")
            await seed_rbac(session)
            print("→ seed_geo …")
            await seed_geo(session)
            print("→ seed_reseau …")
            await seed_reseau(session)
            print("→ seed_sig …")
            from app.models.seed.seed_sig import seed_sig

            await seed_sig(session)
            print("→ seed_dev_accounts …")
            await seed_dev_accounts(session)
            print("→ seed_interruptions …")
            from app.models.seed.seed_interruptions import seed_interruptions

            await seed_interruptions(session)
            print("→ seed_interruptions_transport …")
            from app.models.seed.seed_interruptions_transport import seed_interruptions_transport

            await seed_interruptions_transport(session)
            print("→ seed_indicateurs …")
            from app.models.seed.seed_indicateurs import seed_indicateurs

            await seed_indicateurs(session)
            print("→ seed_notifications …")
            from app.models.seed.seed_notifications import seed_notifications

            await seed_notifications(session)
            await session.commit()
            print("seed-dev : OK — RBAC + geo + réseau + SIG + interruptions + indicateurs + notifications chargés")
            print("  Comptes dev : bcc.dev / brc.dev / superviseur.dev — mot de passe DevSir123!")
            print("  Super admin : superadmin.dev — mot de passe DevSir123!")
        except Exception as exc:
            await session.rollback()
            print(f"seed-dev : ERREUR — {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
