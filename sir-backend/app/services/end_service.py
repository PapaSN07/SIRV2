"""Service END (Énergie Non Distribuée) — calcul et persistance."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interruptions import Interruption
from app.repositories import end_repository as repo
from app.services.indicateurs_cache_service import invalidate_end_cache

# TODO(CRSE): remplacer par la table regles_end après validation SENELEC.
# Coefficients de pondération provisoires par code nature.
REGLES_END_PAR_NATURE: dict[str, tuple[str, Decimal]] = {
    "INCIDENT": ("END_IMPUTABLE", Decimal("1.0")),
    "DELESTAGE": ("END_PROGRAMME", Decimal("1.0")),
    "MAINTENANCE": ("END_PROGRAMME", Decimal("1.0")),
}

DEFAULT_TYPE_END_CODE = "END_IMPUTABLE"
DEFAULT_COEFFICIENT = Decimal("1.0")


@dataclass(frozen=True)
class EndComputation:
    valeur_mwh: Decimal
    puissance_coupee_mw: Decimal
    duree_heures: Decimal
    type_end_id: int | None
    est_force_majeure: bool


def calcul_end(
    puissance_mw: float,
    duree_h: float,
    *,
    is_force_majeure: bool = False,
    coefficient: Decimal = DEFAULT_COEFFICIENT,
) -> Decimal:
    """END (MWh) = puissance (MW) × durée (h) × coefficient.

    Les interruptions force majeure sont exclues du calcul imputable (END = 0).
    # TODO(CRSE): formules de pondération à confirmer avec SENELEC.
    """
    if is_force_majeure:
        return Decimal("0")
    return Decimal(str(puissance_mw)) * Decimal(str(duree_h)) * coefficient


def resolve_puissance_coupee_mw(interruption: Interruption) -> Decimal:
    """Puissance coupée en MW — champ interruption, transit HTB ou somme postes."""
    if interruption.puissance_coupee_mw is not None:
        return Decimal(str(interruption.puissance_coupee_mw))

    transport = interruption.interruption_transport
    if transport is not None and transport.puissance_transit_mw is not None:
        return Decimal(str(transport.puissance_transit_mw))

    total_kva = Decimal("0")
    for link in interruption.postes_interrompus:
        poste = link.poste
        if poste is not None and poste.puissance_kva is not None:
            total_kva += Decimal(str(poste.puissance_kva))

    if total_kva > 0:
        return total_kva / Decimal("1000")

    return Decimal("0")


def resolve_duree_heures(interruption: Interruption) -> Decimal:
    if interruption.duree_minutes is None:
        return Decimal("0")
    return Decimal(str(interruption.duree_minutes)) / Decimal("60")


def _resolve_type_end_code(interruption: Interruption) -> str:
    distribution = interruption.interruption_distribution
    if distribution is not None and distribution.is_programme:
        return "END_PROGRAMME"

    nature = interruption.nature
    if nature is not None and nature.code in REGLES_END_PAR_NATURE:
        return REGLES_END_PAR_NATURE[nature.code][0]

    return DEFAULT_TYPE_END_CODE


def _resolve_coefficient(interruption: Interruption) -> Decimal:
    nature = interruption.nature
    if nature is not None and nature.code in REGLES_END_PAR_NATURE:
        return REGLES_END_PAR_NATURE[nature.code][1]
    return DEFAULT_COEFFICIENT


def compute_end_for_interruption(interruption: Interruption) -> EndComputation:
    """Calcule l'END à partir d'une interruption clôturée (sans accès DB)."""
    puissance = resolve_puissance_coupee_mw(interruption)
    duree_h = resolve_duree_heures(interruption)
    coefficient = _resolve_coefficient(interruption)
    est_fm = interruption.is_force_majeure

    valeur = calcul_end(
        float(puissance),
        float(duree_h),
        is_force_majeure=est_fm,
        coefficient=coefficient,
    )

    return EndComputation(
        valeur_mwh=valeur,
        puissance_coupee_mw=puissance,
        duree_heures=duree_h,
        type_end_id=None,
        est_force_majeure=est_fm,
    )


async def _resolve_type_end_id(db: AsyncSession, interruption: Interruption) -> int | None:
    code = _resolve_type_end_code(interruption)
    type_end = await repo.get_type_end_by_code(db, code)
    if type_end is None and code != DEFAULT_TYPE_END_CODE:
        type_end = await repo.get_type_end_by_code(db, DEFAULT_TYPE_END_CODE)
    return type_end.id if type_end is not None else None


async def calculer_et_persister_end(
    db: AsyncSession,
    interruption_id: int,
) -> dict[str, int | float | str | bool | None]:
    """Calcule l'END, persiste energie_nd + miroir end_mwh, invalide le cache Redis."""
    interruption = await repo.get_interruption_for_end(db, interruption_id)
    if interruption is None:
        raise ValueError(f"Interruption {interruption_id} introuvable")

    if interruption.statut not in ("cloture", "valide", "archive"):
        raise ValueError(
            f"Interruption {interruption_id} non clôturée (statut={interruption.statut})"
        )

    if interruption.date_remise is None or interruption.duree_minutes is None:
        raise ValueError(f"Interruption {interruption_id} : dates de clôture manquantes")

    computation = compute_end_for_interruption(interruption)
    type_end_id = await _resolve_type_end_id(db, interruption)

    end_mwh = float(computation.valeur_mwh)
    await repo.upsert_energie_nd(
        db,
        interruption_id=interruption_id,
        type_end_id=type_end_id,
        valeur_mwh=end_mwh,
        puissance_coupee_mw=float(computation.puissance_coupee_mw),
        duree_heures=float(computation.duree_heures),
        est_force_majeure=computation.est_force_majeure,
    )
    await repo.mirror_end_mwh(db, interruption_id, end_mwh)

    region_id: int | None = None
    if interruption.service_id is not None:
        region_id = await repo.get_region_id_for_service(db, interruption.service_id)
        if region_id is not None:
            invalidate_end_cache(region_id, interruption.date_remise)

    return {
        "interruption_id": interruption_id,
        "status": "calculated",
        "valeur_mwh": end_mwh,
        "est_force_majeure": computation.est_force_majeure,
        "type_end_id": type_end_id,
        "region_id": region_id,
    }
