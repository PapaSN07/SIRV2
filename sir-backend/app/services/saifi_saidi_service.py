"""Service SAIFI/SAIDI — calcul et persistance (Sprint 5.1).

Formules placeholder CRSE (à valider SENELEC) :
  SAIFI = Σ(clients_interrompus) / total_clients_reference
  SAIDI = Σ(clients_interrompus × durée_minutes) / total_clients_reference

Les interruptions force majeure sont exclues du numérateur.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicateurs import SaifiSaidi
from app.models.interruptions import Interruption
from app.repositories import saifi_saidi_repository as repo
from app.services.indicateurs_cache_service import invalidate_indicateurs_cache

# TODO(CRSE): pondérations et règles d'exclusion à confirmer avec SENELEC.


def calcul_saifi(clients_interrompus: int, total_clients: int) -> Decimal:
    """SAIFI = clients interrompus / base clients de référence."""
    if total_clients <= 0:
        return Decimal("0")
    return Decimal(clients_interrompus) / Decimal(total_clients)


def calcul_saidi(client_minutes: int, total_clients: int) -> Decimal:
    """SAIDI = client-minutes / base clients de référence."""
    if total_clients <= 0:
        return Decimal("0")
    return Decimal(client_minutes) / Decimal(total_clients)


def sum_clients_interrompus(interruption: Interruption) -> int:
    total = 0
    for link in interruption.postes_interrompus:
        if link.nombre_clients_touches is not None:
            total += link.nombre_clients_touches
    return total


def compute_period_totals(
    interruptions: Sequence[Interruption],
) -> tuple[int, int, int]:
    """Retourne (clients_interrompus, client_minutes, nombre_interruptions)."""
    clients_total = 0
    client_minutes = 0
    count = 0

    for interruption in interruptions:
        if interruption.is_force_majeure:
            continue

        clients = sum_clients_interrompus(interruption)
        duree = interruption.duree_minutes or 0
        clients_total += clients
        client_minutes += clients * duree
        count += 1

    return clients_total, client_minutes, count


def aggregate_saifi_saidi_weighted(
    records: Sequence[SaifiSaidi],
) -> tuple[Decimal, Decimal, int, int]:
    """Agrégation pondérée service → délégation / région / national."""
    if not records:
        return Decimal("0"), Decimal("0"), 0, 0

    total_clients = sum(r.total_clients_reference for r in records)
    total_interruptions = sum(r.nombre_interruptions for r in records)

    if total_clients <= 0:
        return Decimal("0"), Decimal("0"), total_interruptions, 0

    saifi = sum(Decimal(str(r.saifi)) * r.total_clients_reference for r in records) / Decimal(
        total_clients
    )
    saidi = sum(Decimal(str(r.saidi)) * r.total_clients_reference for r in records) / Decimal(
        total_clients
    )
    return saifi, saidi, total_interruptions, total_clients


async def recalculate_service_period(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
) -> SaifiSaidi:
    total_clients = await repo.get_nombre_clients_reference(
        db, service_id=service_id, annee=annee, mois=mois
    )
    if total_clients is None or total_clients <= 0:
        raise ValueError(
            f"Nombre de clients de référence absent pour service {service_id} "
            f"({annee}-{mois:02d})"
        )

    interruptions = await repo.list_validated_interruptions_for_service_period(
        db, service_id=service_id, annee=annee, mois=mois
    )
    clients_total, client_minutes, count = compute_period_totals(interruptions)

    saifi_val = float(calcul_saifi(clients_total, total_clients))
    saidi_val = float(calcul_saidi(client_minutes, total_clients))

    return await repo.upsert_saifi_saidi(
        db,
        service_id=service_id,
        annee=annee,
        mois=mois,
        saifi=saifi_val,
        saidi=saidi_val,
        nombre_interruptions=count,
        total_clients_reference=total_clients,
    )


async def calculer_et_persister_saifi_saidi(
    db: AsyncSession,
    interruption_id: int,
) -> dict[str, int | float | str | None]:
    """Recalcule SAIFI/SAIDI pour le service/période de l'interruption validée."""
    interruption = await repo.get_interruption_for_saifi_saidi(db, interruption_id)
    if interruption is None:
        return {
            "interruption_id": interruption_id,
            "status": "skipped_not_distribution",
            "service_id": None,
        }

    if interruption.statut != "valide":
        raise ValueError(
            f"Interruption {interruption_id} non validée (statut={interruption.statut})"
        )

    if interruption.service_id is None:
        return {
            "interruption_id": interruption_id,
            "status": "skipped_no_service",
            "service_id": None,
        }

    annee = interruption.date_apparition.year
    mois = interruption.date_apparition.month

    record = await recalculate_service_period(
        db,
        service_id=interruption.service_id,
        annee=annee,
        mois=mois,
    )

    region_id: int | None = await repo.get_region_id_for_service(db, interruption.service_id)
    if region_id is not None:
        periode_ref = datetime(annee, mois, 1)
        invalidate_indicateurs_cache(
            region_id,
            periode_ref,
            indicateurs=("saifi", "saidi", "tableau-de-bord"),
        )

    return {
        "interruption_id": interruption_id,
        "status": "calculated",
        "service_id": record.service_id,
        "annee": annee,
        "mois": mois,
        "saifi": float(record.saifi),
        "saidi": float(record.saidi),
        "nombre_interruptions": record.nombre_interruptions,
        "total_clients_reference": record.total_clients_reference,
        "region_id": region_id,
    }


async def get_aggregate_for_region(
    db: AsyncSession,
    *,
    region_id: int,
    annee: int,
    mois: int,
) -> tuple[Decimal, Decimal, int, int]:
    service_ids = await repo.list_service_ids_for_region(db, region_id)
    records = await repo.list_saifi_saidi_for_services(
        db, service_ids=service_ids, annee=annee, mois=mois
    )
    return aggregate_saifi_saidi_weighted(records)


async def get_aggregate_for_delegation(
    db: AsyncSession,
    *,
    delegation_id: int,
    annee: int,
    mois: int,
) -> tuple[Decimal, Decimal, int, int]:
    service_ids = await repo.list_service_ids_for_delegation(db, delegation_id)
    records = await repo.list_saifi_saidi_for_services(
        db, service_ids=service_ids, annee=annee, mois=mois
    )
    return aggregate_saifi_saidi_weighted(records)


async def get_aggregate_national(
    db: AsyncSession,
    *,
    annee: int,
    mois: int,
) -> tuple[Decimal, Decimal, int, int]:
    service_ids = await repo.list_all_service_ids(db)
    records = await repo.list_saifi_saidi_for_services(
        db, service_ids=service_ids, annee=annee, mois=mois
    )
    return aggregate_saifi_saidi_weighted(records)
