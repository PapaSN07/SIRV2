"""Recalcule SAIFI/SAIDI (formule SENELEC) pour chaque service et chaque mois.

À lancer après l'import de NombreClientMois ou un changement de formule.

Usage :
    docker compose exec api python -m scripts.recalcul_saifi_saidi --depuis 2024-01
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services import saifi_saidi_service


async def main(depuis: str) -> None:
    annee0, mois0 = (int(x) for x in depuis.split("-"))
    async with AsyncSessionLocal() as db:
        periodes = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT service_id, annee, mois FROM dbo.nombre_client_mois
                    WHERE annee * 100 + mois >= :debut AND annee * 100 + mois <= :fin
                    ORDER BY annee, mois, service_id
                    """
                ),
                {"debut": annee0 * 100 + mois0, "fin": date.today().year * 100 + date.today().month},
            )
        ).all()
        faits, sans_base = 0, 0
        for service_id, annee, mois in periodes:
            try:
                await saifi_saidi_service.recalculer_periode(
                    db, service_id=int(service_id), annee=int(annee), mois=int(mois)
                )
                await db.commit()
                faits += 1
            except ValueError:
                await db.rollback()
                sans_base += 1
        print(f"{faits} service-mois recalculé(s), {sans_base} sans base clients.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depuis", default=f"{date.today().year}-01", help="AAAA-MM")
    asyncio.run(main(parser.parse_args().depuis))
