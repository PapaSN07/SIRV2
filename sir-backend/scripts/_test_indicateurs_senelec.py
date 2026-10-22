"""Test indicateurs sur données réelles SENELEC (sans Redis/API).

Usage (bureau SENELEC) :
    cd sir-backend
    $env:SIR_PROFILE = "senelec"
    python -m scripts._test_indicateurs_senelec
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy import extract, func, select, text

from app.core.database import AsyncSessionLocal
from app.models.geo import Region, Service
from app.models.indicateurs import SaifiSaidi
from app.models.interruptions import Interruption, InterruptionDistribution
from app.models.referentiel import Cause, Nature
from app.repositories import indicateurs_repository as repo


async def main() -> None:
    now = datetime.now()
    annee, mois = now.year, now.month
    print(f"=== Indicateurs SIRV2 — srv-bddomtech — {mois:02d}/{annee} ===\n")

    async with AsyncSessionLocal() as db:
        regions = (
            await db.execute(select(Region.id, Region.code, Region.libelle).order_by(Region.id))
        ).all()
        print("Régions :")
        for r in regions[:8]:
            print(f"  [{r.id}] {r.code} — {r.libelle}")
        if len(regions) > 8:
            print(f"  … ({len(regions)} au total)")

        # Première région avec des services
        region_id = regions[0].id if regions else 1
        service_ids = await repo.list_service_ids_for_region(db, region_id)
        print(f"\nScope test : region_id={region_id}, {len(service_ids)} services")

        end_rows = await repo.aggregate_end_by_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        end_total = sum(r.end_mwh for r in end_rows)
        print(f"\nEND {mois:02d}/{annee} (date_remise) : {end_total:.2f} MWh — {len(end_rows)} services avec données")

        saifi_rows = await repo.list_saifi_saidi_for_services(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        if saifi_rows:
            from app.services import saifi_saidi_service

            saifi, saidi, nb, clients = saifi_saidi_service.aggregate_saifi_saidi_weighted(
                saifi_rows
            )
            print(f"SAIFI pondéré : {saifi:.4f} — SAIDI : {saidi:.2f} min — {nb} int. — base {clients} clients")
        else:
            print("SAIFI/SAIDI : aucun enregistrement saifi_saidi pour cette période (worker ou import requis)")

        nb_actives = await repo.count_distribution_interruptions(
            db, service_ids=service_ids, statut="en_cours"
        )
        nb_mois = await repo.count_distribution_interruptions(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        print(f"Interruptions : {nb_actives} en cours — {nb_mois} sur {mois:02d}/{annee} (date_apparition)")

        causes = await repo.aggregate_interruptions_by_cause(
            db, service_ids=service_ids, annee=annee, mois=mois, limit=5
        )
        print("\nTop causes :")
        for c in causes:
            print(f"  - {c.label}: {c.nombre}")

        await db.commit()  # libère le curseur ODBC avant requête suivante

        natures = await repo.aggregate_interruptions_by_nature(
            db, service_ids=service_ids, annee=annee, mois=mois
        )
        print("\nRépartition natures FIS :")
        for n in natures:
            print(f"  - {n.code} ({n.libelle}): {n.nombre} int., END {n.end_mwh * 1000:.0f} kWh")

        await db.commit()

        top = await repo.aggregate_end_by_feeders(
            db, service_ids=service_ids, annee=annee, mois=mois, limit=5
        )
        print("\nTop 5 feeders END :")
        for f in top:
            print(f"  - {f.code} {f.libelle}: {f.end_mwh:.2f} MWh ({f.nombre_interruptions} int.)")

        # Sanity check END (échantillon)
        sample_end = (
            await db.execute(
                text(
                    "SELECT TOP 3 id.end_mwh FROM interruptions_distribution id "
                    "JOIN interruptions i ON i.id = id.interruption_id "
                    "WHERE id.end_mwh IS NOT NULL ORDER BY id.end_mwh DESC"
                )
            )
        ).all()
        print("\nÉchantillon end_mwh max :", [float(r[0]) for r in sample_end])

        nb_saifi = (await db.execute(select(func.count()).select_from(SaifiSaidi))).scalar_one()
        nb_clients = (await db.execute(text("SELECT COUNT(*) FROM nombre_client_mois"))).scalar_one()
        total_int = (await db.execute(select(func.count()).select_from(Interruption))).scalar_one()
        with_end = (
            await db.execute(
                select(func.count())
                .select_from(InterruptionDistribution)
                .where(InterruptionDistribution.end_mwh.isnot(None))
            )
        ).scalar_one()
        print(
            f"\nBase globale : {total_int} interruptions — {with_end} avec end_mwh — "
            f"saifi_saidi={nb_saifi} — nombre_client_mois={nb_clients}"
        )

        nature_codes = (
            await db.execute(select(Nature.code, Nature.libelle).order_by(Nature.code))
        ).all()
        print(f"Référentiel natures ({len(nature_codes)}) :")
        for code, lib in nature_codes:
            print(f"  - {code}: {lib}")


if __name__ == "__main__":
    asyncio.run(main())
