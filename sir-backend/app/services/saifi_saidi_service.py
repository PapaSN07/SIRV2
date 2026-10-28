"""Service SAIFI/SAIDI — formule SENELEC (Power BI SIR, communiquée le 28/10/2026).

    NombreClient                 = Σ PosteInterruption.nombreclientposteEstime
    TotalDureeInterruption       = Σ Interruptions.dureeHeure                      (heures)
    NbClients_DateFin_Interuption = Σ NombreClientMois.Nombreclient du mois (année, mois)
                                   de la dernière DateApparition de la période
    SAIFI = NombreClient / NbClients_DateFin_Interuption
    SAIDI = Σ_interruptions (NombreClient × dureeHeure) / NbClients_DateFin_Interuption   (heures)

Aucune exclusion (force majeure comprise) : la formule SENELEC n'en prévoit pas.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicateurs import SaifiSaidi
from app.models.interruptions import Interruption
from app.repositories import pilotage_repository
from app.repositories import saifi_saidi_repository as repo
from app.services.indicateurs_cache_service import invalidate_indicateurs_cache


def calcul_saifi(clients_interrompus: int, total_clients: int) -> Decimal:
    """SAIFI = NombreClient / NbClients_DateFin_Interuption (0 si pas de base clients)."""
    if total_clients <= 0:
        return Decimal("0")
    return Decimal(clients_interrompus) / Decimal(total_clients)


def calcul_saidi(client_heures: float, total_clients: int) -> Decimal:
    """SAIDI = Σ(NombreClient × dureeHeure) / NbClients_DateFin_Interuption, en heures."""
    if total_clients <= 0:
        return Decimal("0")
    return Decimal(str(client_heures)) / Decimal(total_clients)


def clients_estimes(interruption: Interruption) -> int:
    """NombreClient : clients estimés des postes impactés (repli : clients touchés saisis)."""
    total = 0
    for link in interruption.postes_interrompus:
        valeur = link.nombre_clients_estime
        if valeur is None:
            valeur = link.nombre_clients_touches
        total += valeur or 0
    return total


def duree_heures(interruption: Interruption) -> float:
    """dureeHeure : durée de l'interruption en heures."""
    return (interruption.duree_minutes or 0) / 60.0


def compute_period_totals(
    interruptions: Sequence[Interruption],
) -> tuple[int, float, int]:
    """Retourne (NombreClient, Σ NombreClient × dureeHeure, nombre d'interruptions)."""
    clients_total = 0
    client_heures = 0.0
    for interruption in interruptions:
        clients = clients_estimes(interruption)
        clients_total += clients
        client_heures += clients * duree_heures(interruption)
    return clients_total, client_heures, len(interruptions)


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
    clients_total, client_heures, count = compute_period_totals(interruptions)

    saifi_val = float(calcul_saifi(clients_total, total_clients))
    saidi_val = float(calcul_saidi(client_heures, total_clients))

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

    if interruption.statut not in ("valide", "archive"):
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


async def recalculer_periode(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
) -> dict[str, int | str | None]:
    """Recalcule un mois de service sans partir d'une interruption validée (après une dévalidation)."""
    await recalculate_service_period(db, service_id=service_id, annee=annee, mois=mois)
    region_id = await repo.get_region_id_for_service(db, service_id)
    if region_id is not None:
        invalidate_indicateurs_cache(
            region_id,
            datetime(annee, mois, 1),
            indicateurs=("saifi", "saidi", "tableau-de-bord"),
        )
    return {"status": "calculated", "service_id": service_id, "annee": annee, "mois": mois}


@dataclass(frozen=True)
class SaifiSaidiPerimetre:
    saifi: float
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int


async def calculer_perimetre(
    db: AsyncSession,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    today: date | None = None,
) -> SaifiSaidiPerimetre:
    """SAIFI/SAIDI d'un périmètre (service, région, national) sur [debut, fin[.

    Le numérateur et le dénominateur sont sommés sur tout le périmètre, comme la mesure
    Power BI : le nombre de clients HFSQL est souvent porté par un service représentatif de
    la région, alors que les interruptions sont rattachées à chaque service. Un calcul
    service par service donnerait 0 partout où ces deux rattachements diffèrent.
    """
    totaux = await pilotage_repository.sommer_clients(db, service_ids, debut, fin)
    mois = await pilotage_repository.mois_derniere_apparition(db, service_ids, debut, fin)
    if mois is None:
        jour = today or date.today()
        borne = min(fin - timedelta(seconds=1), datetime(jour.year, jour.month, jour.day))
        mois = (borne.year, borne.month)
    reference = await pilotage_repository.clients_reference_exacte(db, service_ids, *mois)
    return SaifiSaidiPerimetre(
        saifi=float(calcul_saifi(totaux.clients, reference)),
        saidi=float(calcul_saidi(totaux.client_heures, reference)),
        nombre_interruptions=totaux.nombre,
        total_clients_reference=reference,
    )
