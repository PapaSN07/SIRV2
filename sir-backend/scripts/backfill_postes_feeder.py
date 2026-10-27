"""Rattache à leur feeder les postes MT/BT qui n'en ont pas, d'après l'historique des coupures.

Un poste sans feeder_id (créé par la migration depuis PosteInterruption) n'apparaît pas dans la
liste « Postes impactés » des nouvelles interruptions. On lui attribue le feeder sur lequel il a
été le plus souvent impacté (et le service de ce feeder si le poste n'en a pas).

Par défaut : simulation, rien n'est écrit. Tester d'abord sur une copie de la base.

Usage :
    docker compose exec api python -m scripts.backfill_postes_feeder            # simulation
    docker compose exec api python -m scripts.backfill_postes_feeder --execute  # écriture
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

# Feeder majoritaire par poste ; égalité départagée par la coupure la plus récente.
_CANDIDATS = """
WITH comptes AS (
    SELECT pi.poste_id, pi.feeder_id, COUNT(*) AS nb, MAX(pi.id) AS dernier
    FROM dbo.poste_interruptions pi
    JOIN dbo.postes p ON p.id = pi.poste_id
    JOIN dbo.feeders f ON f.id = pi.feeder_id AND f.is_active = 1
    WHERE p.feeder_id IS NULL AND pi.feeder_id IS NOT NULL
    GROUP BY pi.poste_id, pi.feeder_id
),
classes AS (
    SELECT poste_id, feeder_id, nb,
           ROW_NUMBER() OVER (PARTITION BY poste_id ORDER BY nb DESC, dernier DESC) AS rang,
           COUNT(*) OVER (PARTITION BY poste_id) AS nb_feeders
    FROM comptes
)
SELECT c.poste_id, p.code, p.libelle, c.feeder_id, f.libelle AS feeder, c.nb, c.nb_feeders
FROM classes c
JOIN dbo.postes p ON p.id = c.poste_id
JOIN dbo.feeders f ON f.id = c.feeder_id
WHERE c.rang = 1
ORDER BY f.libelle, p.libelle
"""

_MAJ = """
UPDATE p
SET p.feeder_id = :feeder_id,
    p.service_id = COALESCE(p.service_id, f.service_id)
FROM dbo.postes p
JOIN dbo.feeders f ON f.id = :feeder_id
WHERE p.id = :poste_id AND p.feeder_id IS NULL
"""


async def main(execute: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(_CANDIDATS))).all()
        ambigus = [r for r in rows if r.nb_feeders > 1]
        print(f"Postes sans feeder rattachables : {len(rows)} (dont {len(ambigus)} vus sur plusieurs feeders)")
        for r in rows[:30]:
            note = f"  (vu sur {r.nb_feeders} feeders)" if r.nb_feeders > 1 else ""
            print(f"  {r.code:<14} {str(r.libelle)[:40]:<40} → {r.feeder} ({r.nb} coupure(s)){note}")
        if len(rows) > 30:
            print(f"  … et {len(rows) - 30} autre(s)")

        if not execute:
            print("\nSimulation : aucune modification. Relancer avec --execute pour appliquer.")
            return
        for r in rows:
            await db.execute(text(_MAJ), {"feeder_id": r.feeder_id, "poste_id": r.poste_id})
        await db.commit()
        print(f"\n{len(rows)} poste(s) rattaché(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    asyncio.run(main(parser.parse_args().execute))
