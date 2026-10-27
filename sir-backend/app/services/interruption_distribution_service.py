"""Service métier — interruptions réseau distribution (Sprint 3)."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.interruption_statut_historique import (
    ACTION_CLOTURE,
    ACTION_CREATION,
    ACTION_VALIDATION,
)
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.reseau import Poste
from app.models.sig import TronconSig as TronconSigOrm
from app.models.utilisateurs import Utilisateur
from app.repositories import interruption_distribution_repository as repo
from app.repositories import end_repository as end_repo
from app.repositories import interruption_workflow_repository as workflow_repo
from app.repositories import referentiel_repository as ref_repo
from app.repositories import reseau_distribution_repository as reseau_repo
from app.repositories import sig_repository as sig_repo
from app.repositories.reseau_distribution_repository import ScopeFilter
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_statut import (
    ArchivageRequest,
    ArchivageResponse,
    MotifRequest,
    StatutHistoriqueResponse,
    ValidationLotEchec,
    ValidationLotRequest,
    ValidationLotResponse,
)
from app.services import interruption_cycle_service
from app.schemas.interruption_distribution import (
    EnergieNdSummaryResponse,
    InterruptionDistributionCreate,
    InterruptionDistributionDetailResponse,
    InterruptionDistributionResponse,
    InterruptionClotureRequest,
    InterruptionDistributionStatsResponse,
    InterruptionDistributionUpdate,
    PosteImpacteBulkResponse,
    PosteImpacteFromSigRequest,
    PosteImpacteResponse,
    PosteInterruptionCreate,
    UtilisateurSummaryResponse,
)
from app.utils.audit import ACTION_CREATE, ACTION_DELETE, ACTION_UPDATE, log_audit

from app.services.indicateurs_cache_service import invalidate_indicateurs_cache

_DISTRIBUTION_TYPE_RESEAU = frozenset({"distribution", "commun"})
READ_ROLES = frozenset({"BCC", "BRC", "ADMIN_SCR", "ADMIN_SAQS", "SUPERVISEUR"})
VALIDATE_ROLES = frozenset({"SUPERVISEUR", "ADMIN_SCR", "ADMIN_SAQS"})

def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _ensure_not_transport_role(user: Utilisateur) -> None:
    """Blocage explicite Dispatcher / Admin Dispatching sur la distribution."""
    if is_superadmin(user):
        return
    if _user_role_names(user).intersection({"DISPATCHER", "ADMIN_DISPATCHING"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès interruptions distribution non autorisé pour ce rôle",
            },
        )


def _ensure_can_read(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    _ensure_not_transport_role(user)
    if not _user_role_names(user).intersection(READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès lecture interruptions distribution non autorisé",
            },
        )


def _read_scope(user: Utilisateur) -> ScopeFilter | None:
    """Scope repository : BCC/BRC → région · Superviseur → service · Admin → national."""
    if is_superadmin(user):
        return None
    roles = _user_role_names(user)
    if roles.intersection({"ADMIN_SCR", "ADMIN_SAQS"}):
        return None
    if roles.intersection({"BCC", "BRC"}):
        region_id = user.user_roles[0].scope_service_id
        if region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre régional non configuré pour ce compte",
                },
            )
        return ScopeFilter(region_id=region_id)
    if "SUPERVISEUR" in roles:
        service_id = user.user_roles[0].scope_service_id
        if service_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre de service non configuré pour ce compte",
                },
            )
        return ScopeFilter(service_id=service_id)
    return None


async def _ensure_service_in_write_scope(
    db: AsyncSession,
    user: Utilisateur,
    service_id: int,
) -> None:
    """Vérifie le périmètre d'écriture : BCC/BRC → région · Superviseur → service."""
    scope = _read_scope(user)
    if scope is None:
        return

    if scope.service_id is not None:
        if service_id != scope.service_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : service_id non autorisé",
                },
            )
        return

    if scope.region_id is not None:
        in_region = await repo.service_in_region(db, service_id, scope.region_id)
        if not in_region:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : region_id non autorisé",
                },
            )


async def _ensure_interruption_in_scope(
    db: AsyncSession,
    user: Utilisateur,
    interruption: Interruption,
) -> None:
    """Vérifie que l'utilisateur peut lire cette interruption (même règles que la liste)."""
    scope = _read_scope(user)
    if scope is None:
        return

    if interruption.service_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Interruption hors périmètre",
            },
        )

    if scope.service_id is not None:
        if interruption.service_id != scope.service_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : service_id non autorisé",
                },
            )
        return

    if scope.region_id is not None:
        in_region = await repo.service_in_region(db, interruption.service_id, scope.region_id)
        if not in_region:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : region_id non autorisé",
                },
            )


def _user_summary(user) -> UtilisateurSummaryResponse | None:
    if user is None:
        return None
    return UtilisateurSummaryResponse(
        id=user.id,
        login=user.login,
        nom=user.nom,
        prenom=user.prenom,
    )


def _to_detail_response(
    interruption: Interruption,
    distribution: InterruptionDistribution,
) -> InterruptionDistributionDetailResponse:
    base = _to_response(interruption, distribution)
    end_mwh = base.end_mwh
    energie_nd_summary: EnergieNdSummaryResponse | None = None

    if interruption.energie_nd is not None:
        nd = interruption.energie_nd
        energie_nd_summary = EnergieNdSummaryResponse(
            valeur_mwh=float(nd.valeur_mwh),
            puissance_coupee_mw=float(nd.puissance_coupee_mw),
            duree_heures=float(nd.duree_heures),
            est_force_majeure=nd.est_force_majeure,
            calculated_at=nd.calculated_at,
        )
        end_mwh = float(nd.valeur_mwh)
    elif end_mwh is None and distribution.end_mwh is not None:
        end_mwh = float(distribution.end_mwh)

    postes = [_poste_to_response(pi) for pi in interruption.postes_interrompus]

    detail_data = base.model_dump()
    detail_data["end_mwh"] = end_mwh

    return InterruptionDistributionDetailResponse(
        **detail_data,
        signalisation_libelle=interruption.signalisation.libelle
        if interruption.signalisation
        else None,
        service_code=interruption.service.code if interruption.service else None,
        postes_impactes=postes,
        energie_nd=energie_nd_summary,
        created_by=_user_summary(interruption.created_by),
        validated_by=_user_summary(interruption.validated_by),
        validated_by_id=interruption.validated_by_id,
        updated_by=_user_summary(interruption.updated_by),
    )


async def _validate_referentiel_distribution(
    db: AsyncSession,
    *,
    cause_id: int,
    nature_id: int,
    siege_id: int,
    signalisation_id: int,
) -> None:
    cause = await ref_repo.get_by_id(db, "causes", cause_id)
    if cause is None or not cause.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Cause {cause_id} introuvable ou inactive",
            },
        )
    if cause.type_reseau not in _DISTRIBUTION_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "La cause doit être de type distribution ou commun",
            },
        )

    nature = await ref_repo.get_by_id(db, "natures", nature_id)
    if nature is None or not nature.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Nature {nature_id} introuvable ou inactive",
            },
        )

    siege = await ref_repo.get_by_id(db, "sieges", siege_id)
    if siege is None or not siege.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Siège {siege_id} introuvable ou inactive",
            },
        )
    if siege.type_reseau not in _DISTRIBUTION_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le siège doit être de type distribution ou commun",
            },
        )

    signalisation = await ref_repo.get_by_id(db, "signalisations", signalisation_id)
    if signalisation is None or not signalisation.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Signalisation {signalisation_id} introuvable ou inactive",
            },
        )
    if signalisation.type_reseau not in _DISTRIBUTION_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "La signalisation doit être de type distribution ou commun",
            },
        )


async def _validate_type_saisie(
    db: AsyncSession,
    *,
    type_end_id: int | None,
    type_reseau_id: int | None,
) -> None:
    for resource, item_id, label in (
        ("types_end", type_end_id, "Type END"),
        ("types_reseaux", type_reseau_id, "Type réseau"),
    ):
        if item_id is None:
            continue
        record = await ref_repo.get_by_id(db, resource, item_id)
        if record is None or not record.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"{label} {item_id} introuvable ou inactif",
                },
            )


async def _validate_intervenants(
    db: AsyncSession,
    *,
    entreprise_id: int | None,
    prestataire_id: int | None,
) -> None:
    for resource, item_id, label in (
        ("entreprises", entreprise_id, "Entreprise"),
        ("prestataires", prestataire_id, "Prestataire"),
    ):
        if item_id is None:
            continue
        record = await ref_repo.get_by_id(db, resource, item_id)
        if record is None or not record.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"{label} {item_id} introuvable ou inactif",
                },
            )


def _region_libelle(interruption: Interruption) -> str | None:
    service = interruption.service
    if service is None or service.agence is None:
        return None
    delegation = service.agence.delegation
    if delegation is None or delegation.region is None:
        return None
    return delegation.region.libelle


def _to_response(
    interruption: Interruption,
    distribution: InterruptionDistribution,
) -> InterruptionDistributionResponse:
    return InterruptionDistributionResponse(
        id=interruption.id,
        numero_interruption=interruption.numero_interruption,
        type_direction="distribution",
        direction_source_id=interruption.direction_source_id,
        statut=interruption.statut,  # type: ignore[arg-type]
        statut_id=interruption.statut_id,
        entreprise_id=interruption.entreprise_id,
        prestataire_id=interruption.prestataire_id,
        service_id=interruption.service_id,
        feeder_id=interruption.feeder_id,
        sous_feeder_id=interruption.sous_feeder_id,
        poste_source_id=interruption.poste_source_id,
        date_apparition=interruption.date_apparition,
        date_remise=interruption.date_remise,
        duree_minutes=interruption.duree_minutes,
        cause_id=interruption.cause_id,
        nature_id=interruption.nature_id,
        siege_id=interruption.siege_id,
        signalisation_id=interruption.signalisation_id,
        type_end_id=interruption.type_end_id,
        type_reseau_id=interruption.type_reseau_id,
        puissance_coupee_mw=float(interruption.puissance_coupee_mw)
        if interruption.puissance_coupee_mw is not None
        else None,
        localisation=interruption.localisation,
        observations=interruption.observations,
        is_force_majeure=interruption.is_force_majeure,
        is_fugitive=interruption.is_fugitive,
        tension_kv=float(distribution.tension_kv) if distribution.tension_kv is not None else None,
        nombre_clients_mt=distribution.nombre_clients_mt,
        nombre_clients_bt=distribution.nombre_clients_bt,
        end_mwh=float(distribution.end_mwh) if distribution.end_mwh is not None else None,
        is_programme=distribution.is_programme,
        has_extension_bt=distribution.has_extension_bt,
        created_by_id=interruption.created_by_id,
        updated_by_id=interruption.updated_by_id,
        created_at=interruption.created_at,
        updated_at=interruption.updated_at,
        entreprise_libelle=interruption.entreprise.libelle if interruption.entreprise else None,
        prestataire_libelle=interruption.prestataire.libelle
        if interruption.prestataire
        else None,
        cause_libelle=interruption.cause.libelle if interruption.cause else None,
        nature_libelle=interruption.nature.libelle if interruption.nature else None,
        siege_libelle=interruption.siege.libelle if interruption.siege else None,
        service_libelle=interruption.service.libelle if interruption.service else None,
        poste_source_libelle=interruption.poste_source.libelle
        if interruption.poste_source
        else None,
        feeder_libelle=interruption.feeder.libelle if interruption.feeder else None,
        type_end_libelle=interruption.type_end.libelle if interruption.type_end else None,
        type_reseau_libelle=interruption.type_reseau.libelle if interruption.type_reseau else None,
        sous_feeder_libelle=interruption.sous_feeder.libelle
        if interruption.sous_feeder
        else None,
        region_libelle=_region_libelle(interruption),
    )


async def _response_after_commit(
    db: AsyncSession,
    interruption_id: int,
) -> InterruptionDistributionResponse:
    """Recharge l'interruption après commit (évite lazy load → MissingGreenlet)."""
    interruption = await repo.get_interruption_for_response(db, interruption_id)
    if interruption is None or interruption.interruption_distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable après enregistrement",
            },
        )
    return _to_response(interruption, interruption.interruption_distribution)


async def create(
    db: AsyncSession,
    body: InterruptionDistributionCreate,
    current_user: Utilisateur,
) -> InterruptionDistributionResponse:
    """Crée une interruption distribution (statut initial en_cours)."""
    _ensure_not_transport_role(current_user)

    feeder = await reseau_repo.get_feeder(db, body.feeder_id)
    if feeder is None or not feeder.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Feeder {body.feeder_id} introuvable ou inactif",
            },
        )

    if feeder.service_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le feeder doit être rattaché à un service",
            },
        )

    if feeder.poste_source_id != body.poste_source_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le feeder ne correspond pas au poste source sélectionné",
            },
        )

    sous_feeder_id: int | None = None
    if body.sous_feeder_id is not None:
        sous_feeder = await reseau_repo.get_sous_feeder(db, body.sous_feeder_id)
        if sous_feeder is None or not sous_feeder.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Sous-feeder {body.sous_feeder_id} introuvable ou inactif",
                },
            )
        if sous_feeder.feeder_id != feeder.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Le sous-feeder ne correspond pas au feeder sélectionné",
                },
            )
        sous_feeder_id = sous_feeder.id

    await _ensure_service_in_write_scope(db, current_user, feeder.service_id)

    await _validate_referentiel_distribution(
        db,
        cause_id=body.cause_id,
        nature_id=body.nature_id,
        siege_id=body.siege_id,
        signalisation_id=body.signalisation_id,
    )
    await _validate_intervenants(
        db, entreprise_id=body.entreprise_id, prestataire_id=body.prestataire_id
    )
    await _validate_type_saisie(
        db, type_end_id=body.type_end_id, type_reseau_id=body.type_reseau_id
    )

    year = body.date_apparition.year
    numero = await repo.next_numero_interruption(db, year=year)

    interruption_values = {
        "numero_interruption": numero,
        "type_direction": "distribution",
        "statut": "en_cours",
        "service_id": feeder.service_id,
        "feeder_id": feeder.id,
        "sous_feeder_id": sous_feeder_id,
        "poste_source_id": feeder.poste_source_id,
        "date_apparition": body.date_apparition,
        "cause_id": body.cause_id,
        "nature_id": body.nature_id,
        "siege_id": body.siege_id,
        "signalisation_id": body.signalisation_id,
        "type_end_id": body.type_end_id,
        "type_reseau_id": body.type_reseau_id,
        "puissance_coupee_mw": body.puissance_coupee_mw,
        "localisation": body.localisation,
        "observations": body.observations,
        "is_force_majeure": body.is_force_majeure,
        "is_fugitive": body.is_fugitive,
        "entreprise_id": body.entreprise_id,
        "prestataire_id": body.prestataire_id,
        "created_by_id": current_user.id,
    }

    distribution_values = {
        "tension_kv": body.tension_kv,
        "nombre_clients_mt": body.nombre_clients_mt,
        "nombre_clients_bt": body.nombre_clients_bt,
        "is_programme": body.is_programme,
        "has_extension_bt": body.has_extension_bt,
    }

    interruption, distribution = await repo.create_interruption_distribution(
        db,
        interruption_values=interruption_values,
        distribution_values=distribution_values,
    )

    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={
            "numero_interruption": numero,
            "type_direction": "distribution",
            "statut": "en_cours",
            "feeder_id": feeder.id,
            "service_id": feeder.service_id,
        },
    )
    await interruption_cycle_service.enregistrer(
        db, interruption, action=ACTION_CREATION, ancien_statut=None, user=current_user
    )

    await db.commit()

    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_CREEE,
        entity_type="interruption",
        entity_id=interruption.id,
        service_id=feeder.service_id,
    )

    return await _response_after_commit(db, interruption.id)


async def _validate_list_filters(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    region_id: int | None,
    service_id: int | None,
) -> None:
    """Vérifie que les filtres explicites restent dans le périmètre BCC/BRC."""
    scope = _read_scope(current_user)
    roles = _user_role_names(current_user)

    if roles.intersection({"BCC", "BRC"}) and scope is not None and scope.region_id is not None:
        if region_id is not None and region_id != scope.region_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : région non autorisée",
                },
            )
        if service_id is not None:
            in_region = await repo.service_in_region(db, service_id, scope.region_id)
            if not in_region:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "status": "error",
                        "data": None,
                        "error": "Hors périmètre : service hors région",
                    },
                )

    if "SUPERVISEUR" in roles and scope is not None and scope.service_id is not None:
        if service_id is not None and service_id != scope.service_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : service non autorisé",
                },
            )


async def list_items(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    page: int = 1,
    page_size: int = 20,
    region_id: int | None = None,
    service_id: int | None = None,
    feeder_id: int | None = None,
    nature_id: int | None = None,
    ouverture: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    _max_page_size: int | None = None,
) -> PaginatedResponse[InterruptionDistributionResponse]:
    """Liste paginée des interruptions distribution avec scope RBAC automatique."""
    _ensure_can_read(current_user)
    scope = _read_scope(current_user)

    if ouverture is not None and ouverture not in ("ouvert", "ferme"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "ouverture doit valoir 'ouvert' ou 'ferme'",
            },
        )

    await _validate_list_filters(db, current_user, region_id=region_id, service_id=service_id)

    if date_debut is not None and date_fin is not None and date_debut > date_fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "date_debut doit être antérieure ou égale à date_fin",
            },
        )

    result = await repo.list_interruptions_paginated(
        db,
        page=page,
        page_size=page_size,
        scope=scope,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        max_page_size=_max_page_size,
    )

    items: list[InterruptionDistributionResponse] = []
    for interruption in result.items:
        distribution = interruption.interruption_distribution
        if distribution is None:
            continue
        items.append(_to_response(interruption, distribution))

    # Ancienneté dans la file de validation : date de clôture (historique), sinon dernière mise à jour
    clotures = [i for i in items if i.statut == "cloture"]
    if clotures:
        dates = await interruption_cycle_service.dates_cloture(db, [i.id for i in clotures])
        for item in clotures:
            item.date_cloture = dates.get(item.id, item.updated_at)

    return PaginatedResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_stats(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    region_id: int | None = None,
    service_id: int | None = None,
    feeder_id: int | None = None,
    nature_id: int | None = None,
    ouverture: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> InterruptionDistributionStatsResponse:
    """Compteurs liste (total, non validées, en cours) dans le périmètre RBAC."""
    _ensure_can_read(current_user)
    scope = _read_scope(current_user)
    await _validate_list_filters(db, current_user, region_id=region_id, service_id=service_id)

    filter_kwargs = {
        "region_id": region_id,
        "service_id": service_id,
        "feeder_id": feeder_id,
        "nature_id": nature_id,
        "ouverture": ouverture,
        "statut": statut,
        "date_debut": date_debut,
        "date_fin": date_fin,
    }
    total = await repo.count_interruptions_scoped(db, scope=scope, **filter_kwargs)
    non_validees = await repo.count_interruptions_scoped(
        db, scope=scope, non_validees_only=True, **filter_kwargs
    )
    en_cours = await repo.count_interruptions_scoped(
        db,
        scope=scope,
        ouverture="ouvert",
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        statut=None,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return InterruptionDistributionStatsResponse(
        total=total,
        non_validees=non_validees,
        en_cours=en_cours,
    )


async def get_item(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> InterruptionDistributionDetailResponse:
    """Détail complet d'une interruption distribution."""
    _ensure_can_read(current_user)

    interruption = await repo.get_interruption_detail(db, interruption_id)
    if interruption is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )

    await _ensure_interruption_in_scope(db, current_user, interruption)

    distribution = interruption.interruption_distribution
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Détail distribution introuvable pour l'interruption {interruption_id}",
            },
        )

    return _to_detail_response(interruption, distribution)


def _poste_to_response(pi: PosteInterruption) -> PosteImpacteResponse:
    return PosteImpacteResponse(
        poste_id=pi.poste_id,
        poste_code=pi.poste.code if pi.poste else None,
        poste_libelle=pi.poste.libelle if pi.poste else None,
        nombre_clients_touches=pi.nombre_clients_touches,
        date_interruption=pi.date_interruption,
        feeder_id=pi.feeder_id,
        service_id=pi.service_id,
        poste_source_id=pi.poste_source_id,
    )


def _context_ids_for_poste_link(
    interruption: Interruption,
    poste: Poste,
) -> tuple[int | None, int | None, int | None]:
    """Dénormalise feeder / service / poste_source pour poste_interruptions."""
    feeder_id = interruption.feeder_id or poste.feeder_id
    service_id = interruption.service_id or poste.service_id
    poste_source_id = interruption.poste_source_id
    return feeder_id, service_id, poste_source_id


def _poste_in_perimeter(poste: Poste, interruption: Interruption) -> bool:
    if interruption.service_id is not None and poste.service_id == interruption.service_id:
        return True
    if interruption.feeder_id is not None and poste.feeder_id == interruption.feeder_id:
        return True
    return False


async def _poste_dans_perimetre(db: AsyncSession, poste: Poste, interruption: Interruption) -> bool:
    """Comme `_poste_in_perimeter`, plus les postes sans feeder déjà coupés sur ce feeder.

    Même règle que la liste « Postes impactés » (reseau_distribution_repository.list_postes).
    """
    if _poste_in_perimeter(poste, interruption):
        return True
    if poste.feeder_id is None and interruption.feeder_id is not None:
        return await repo.poste_deja_impacte_sur_feeder(db, poste.id, interruption.feeder_id)
    return False


def _ensure_statut_en_cours(interruption: Interruption) -> None:
    if interruption.statut != "en_cours":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Modification autorisée uniquement pour une interruption en_cours",
            },
        )


def _ensure_statut_cloture(interruption: Interruption) -> None:
    if interruption.statut != "cloture":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Validation autorisée uniquement pour une interruption cloture",
            },
        )


def _ensure_can_validate(user: Utilisateur) -> None:
    """Validation réservée Superviseur, Admin SCR et Admin SAQS."""
    if is_superadmin(user):
        return
    _ensure_not_transport_role(user)
    if not _user_role_names(user).intersection(VALIDATE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Validation réservée aux Superviseurs, Admin SCR et Admin SAQS",
            },
        )


async def _get_interruption_accessible(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> Interruption:
    _ensure_can_read(current_user)
    interruption = await repo.get_interruption(db, interruption_id)
    if interruption is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )
    await _ensure_interruption_in_scope(db, current_user, interruption)
    return interruption


async def list_postes(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> list[PosteImpacteResponse]:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    links = await repo.list_postes_for_interruption(db, interruption.id)
    return [_poste_to_response(pi) for pi in links]


async def add_poste(
    db: AsyncSession,
    interruption_id: int,
    body: PosteInterruptionCreate,
    current_user: Utilisateur,
) -> PosteImpacteResponse:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)

    poste = await reseau_repo.get_poste(db, body.poste_id)
    if poste is None or not poste.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Poste {body.poste_id} introuvable ou inactif",
            },
        )

    if not await _poste_dans_perimetre(db, poste, interruption):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le poste n'appartient pas au périmètre feeder/service de l'interruption",
            },
        )

    existing = await repo.get_poste_interruption_link(db, interruption.id, body.poste_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Ce poste est déjà associé à l'interruption",
            },
        )

    feeder_id, service_id, poste_source_id = _context_ids_for_poste_link(interruption, poste)
    link = await repo.add_poste_interruption(
        db,
        interruption_id=interruption.id,
        poste_id=body.poste_id,
        nombre_clients_touches=body.nombre_clients_touches,
        date_interruption=body.date_interruption or interruption.date_apparition,
        feeder_id=feeder_id,
        service_id=service_id,
        poste_source_id=poste_source_id,
    )
    link.poste = poste

    await log_audit(
        db,
        table_name="poste_interruptions",
        record_id=link.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={
            "interruption_id": interruption.id,
            "poste_id": body.poste_id,
            "feeder_id": feeder_id,
            "service_id": service_id,
            "poste_source_id": poste_source_id,
        },
    )

    await db.commit()
    return _poste_to_response(link)


def _sig_node_tokens(troncons: list[TronconSigOrm]) -> set[str]:
    tokens: set[str] = set()
    for troncon in troncons:
        for value in (
            troncon.nom_noeud_amont,
            troncon.nom_noeud_aval,
            troncon.code_noeud_amont,
            troncon.code_noeud_aval,
            troncon.nom_troncon,
        ):
            if value:
                token = value.strip().lower()
                if len(token) >= 2:
                    tokens.add(token)
    return tokens


def _poste_matches_sig_nodes(poste: Poste, tokens: set[str]) -> bool:
    if not tokens:
        return False
    for raw in (poste.code, poste.libelle):
        if not raw:
            continue
        value = raw.strip().lower()
        if value in tokens:
            return True
        for token in tokens:
            if len(token) >= 3 and (token in value or value in token):
                return True
    return False


async def _bulk_link_postes(
    db: AsyncSession,
    interruption: Interruption,
    postes: list[Poste],
    current_user: Utilisateur,
) -> PosteImpacteBulkResponse:
    linked_ids = await repo.list_linked_poste_ids(db, interruption.id)
    added: list[PosteImpacteResponse] = []
    skipped = 0

    for poste in postes:
        if poste.id in linked_ids:
            skipped += 1
            continue
        if not await _poste_dans_perimetre(db, poste, interruption):
            skipped += 1
            continue
        feeder_id, service_id, poste_source_id = _context_ids_for_poste_link(
            interruption, poste
        )
        link = await repo.add_poste_interruption(
            db,
            interruption_id=interruption.id,
            poste_id=poste.id,
            nombre_clients_touches=poste.nombre_clients,
            date_interruption=interruption.date_apparition,
            feeder_id=feeder_id,
            service_id=service_id,
            poste_source_id=poste_source_id,
        )
        link.poste = poste
        linked_ids.add(poste.id)
        added.append(_poste_to_response(link))
        await log_audit(
            db,
            table_name="poste_interruptions",
            record_id=link.id,
            action=ACTION_CREATE,
            user_id=current_user.id,
            new_values={
                "interruption_id": interruption.id,
                "poste_id": poste.id,
                "feeder_id": feeder_id,
                "service_id": service_id,
                "poste_source_id": poste_source_id,
                "bulk": True,
            },
        )

    await db.commit()
    return PosteImpacteBulkResponse(
        added_count=len(added),
        skipped_count=skipped,
        items=added,
    )


async def add_postes_from_feeder(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> PosteImpacteBulkResponse:
    """Associe tous les postes actifs du feeder de l'interruption."""
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)
    if interruption.feeder_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "L'interruption n'a pas de feeder associé",
            },
        )

    postes = await reseau_repo.list_postes(db, feeder_id=interruption.feeder_id)
    return await _bulk_link_postes(db, interruption, postes, current_user)


async def add_postes_from_sig_troncon(
    db: AsyncSession,
    interruption_id: int,
    body: PosteImpacteFromSigRequest,
    current_user: Utilisateur,
) -> PosteImpacteBulkResponse:
    """Associe les postes correspondant au tronçon SIG (chaîne aval incluse)."""
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)

    troncon_sig_id = body.troncon_sig_id
    if troncon_sig_id is None:
        troncon_sig_id = await workflow_repo.get_troncon_sig_id_for_interruption(
            db, interruption.id
        )
    if troncon_sig_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Aucun tronçon SIG sélectionné dans le workflow",
            },
        )

    troncon = await sig_repo.get_troncon_sig(db, troncon_sig_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Tronçon SIG {troncon_sig_id} introuvable",
            },
        )

    feeder_id = troncon.feeder_id or interruption.feeder_id
    if feeder_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Impossible de résoudre le feeder pour ce tronçon SIG",
            },
        )

    feeder = await sig_repo.get_feeder(db, feeder_id)
    if feeder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Feeder {feeder_id} introuvable",
            },
        )

    chain = await sig_repo.build_chaine_aval(db, feeder, troncon, limit=body.chain_limit)
    tokens = _sig_node_tokens(chain)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Tronçon SIG sans nœuds exploitables pour la correspondance postes",
            },
        )

    postes = [
        poste
        for poste in await reseau_repo.list_postes(db, feeder_id=feeder_id)
        if _poste_matches_sig_nodes(poste, tokens)
    ]
    if not postes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Aucun poste MT/BT ne correspond aux nœuds du tronçon SIG",
            },
        )

    return await _bulk_link_postes(db, interruption, postes, current_user)


async def remove_poste(
    db: AsyncSession,
    interruption_id: int,
    poste_id: int,
    current_user: Utilisateur,
) -> None:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)

    deleted = await repo.delete_poste_interruption(db, interruption.id, poste_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Poste {poste_id} non associé à l'interruption {interruption_id}",
            },
        )

    await log_audit(
        db,
        table_name="poste_interruptions",
        record_id=interruption.id,
        action=ACTION_DELETE,
        user_id=current_user.id,
        old_values={"interruption_id": interruption.id, "poste_id": poste_id},
    )

    await db.commit()


def _ensure_can_modify(user: Utilisateur, interruption: Interruption) -> None:
    """BCC : créateur · BRC / Admin SCR : périmètre déjà validé."""
    if is_superadmin(user):
        return
    roles = _user_role_names(user)
    if roles.intersection({"ADMIN_SCR", "BRC"}):
        return
    if interruption.created_by_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Seul le créateur ou Admin SCR peut modifier cette interruption",
        },
    )


def _snapshot_interruption(interruption: Interruption) -> dict[str, object]:
    distribution = interruption.interruption_distribution
    snapshot: dict[str, object] = {
        "date_apparition": interruption.date_apparition.isoformat(),
        "cause_id": interruption.cause_id,
        "nature_id": interruption.nature_id,
        "siege_id": interruption.siege_id,
        "signalisation_id": interruption.signalisation_id,
        "puissance_coupee_mw": float(interruption.puissance_coupee_mw)
        if interruption.puissance_coupee_mw is not None
        else None,
        "localisation": interruption.localisation,
        "observations": interruption.observations,
        "is_force_majeure": interruption.is_force_majeure,
        "is_fugitive": interruption.is_fugitive,
        "entreprise_id": interruption.entreprise_id,
        "prestataire_id": interruption.prestataire_id,
    }
    if distribution is not None:
        snapshot.update(
            {
                "tension_kv": float(distribution.tension_kv)
                if distribution.tension_kv is not None
                else None,
                "nombre_clients_mt": distribution.nombre_clients_mt,
                "nombre_clients_bt": distribution.nombre_clients_bt,
                "is_programme": distribution.is_programme,
                "has_extension_bt": distribution.has_extension_bt,
            }
        )
    return snapshot


async def update(
    db: AsyncSession,
    interruption_id: int,
    body: InterruptionDistributionUpdate,
    current_user: Utilisateur,
) -> InterruptionDistributionResponse:
    """Met à jour une interruption distribution (statut en_cours uniquement)."""
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)
    _ensure_can_modify(current_user, interruption)

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Aucun champ à mettre à jour",
            },
        )

    old_values = _snapshot_interruption(interruption)

    cause_id = updates.get("cause_id", interruption.cause_id)
    nature_id = updates.get("nature_id", interruption.nature_id)
    siege_id = updates.get("siege_id", interruption.siege_id)
    signalisation_id = updates.get("signalisation_id", interruption.signalisation_id)

    if any(k in updates for k in ("cause_id", "nature_id", "siege_id", "signalisation_id")):
        await _validate_referentiel_distribution(
            db,
            cause_id=cause_id,
            nature_id=nature_id,
            siege_id=siege_id,
            signalisation_id=signalisation_id,
        )
    if "type_end_id" in updates or "type_reseau_id" in updates:
        await _validate_type_saisie(
            db,
            type_end_id=updates.get("type_end_id"),
            type_reseau_id=updates.get("type_reseau_id"),
        )
    if "entreprise_id" in updates or "prestataire_id" in updates:
        await _validate_intervenants(
            db,
            entreprise_id=updates.get("entreprise_id"),
            prestataire_id=updates.get("prestataire_id"),
        )

    interruption_fields = {
        "date_apparition",
        "cause_id",
        "nature_id",
        "siege_id",
        "signalisation_id",
        "type_end_id",
        "type_reseau_id",
        "puissance_coupee_mw",
        "localisation",
        "observations",
        "is_force_majeure",
        "is_fugitive",
        "entreprise_id",
        "prestataire_id",
    }
    distribution_fields = {
        "tension_kv",
        "nombre_clients_mt",
        "nombre_clients_bt",
        "is_programme",
        "has_extension_bt",
    }

    interruption_updates = {k: v for k, v in updates.items() if k in interruption_fields}
    interruption_updates["updated_by_id"] = current_user.id
    distribution_updates = {k: v for k, v in updates.items() if k in distribution_fields}

    result = await repo.update_interruption_distribution(
        db,
        interruption_id,
        interruption_updates=interruption_updates,
        distribution_updates=distribution_updates,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )

    interruption, distribution = result
    new_values = _snapshot_interruption(interruption)

    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values=new_values,
    )

    await db.commit()
    return await _response_after_commit(db, interruption.id)


# Au-delà de cette durée, au moins un poste impacté est obligatoire pour clôturer.
POSTES_OBLIGATOIRES_APRES_MINUTES = 5


def _as_naive(value: datetime) -> datetime:
    """DATETIME2 est naïf. Une date avec fuseau (ISO « Z ») est ramenée en UTC naïf."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        from datetime import timezone

        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# Tolérance d'horloge entre le poste de saisie et le serveur
_TOLERANCE_REMISE_FUTURE = timedelta(minutes=5)


def _ensure_remise_pas_dans_le_futur(date_remise: datetime) -> None:
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
    if _as_naive(date_remise) > maintenant + _TOLERANCE_REMISE_FUTURE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "La date de remise ne peut pas être dans le futur",
            },
        )


def _compute_duree_minutes(date_apparition: datetime, date_remise: datetime) -> int:
    delta = _as_naive(date_remise) - _as_naive(date_apparition)
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "date_remise doit être postérieure à date_apparition",
            },
        )
    return minutes


async def cloturer(
    db: AsyncSession,
    interruption_id: int,
    body: InterruptionClotureRequest,
    current_user: Utilisateur,
) -> InterruptionDistributionResponse:
    """Clôture une interruption distribution et déclenche le calcul END async."""
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)
    _ensure_can_modify(current_user, interruption)

    duree_minutes = _compute_duree_minutes(interruption.date_apparition, body.date_remise)
    _ensure_remise_pas_dans_le_futur(body.date_remise)

    if duree_minutes > POSTES_OBLIGATOIRES_APRES_MINUTES:
        postes_count = await repo.count_postes_for_interruption(db, interruption.id)
        if postes_count < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": (
                        "Pour une interruption de plus de 5 minutes, "
                        "au moins un poste impacté doit être coché"
                    ),
                },
            )

    old_values = {"statut": interruption.statut, "date_remise": None, "duree_minutes": None}

    result = await repo.update_interruption_distribution(
        db,
        interruption_id,
        interruption_updates={
            "statut": "cloture",
            "date_remise": body.date_remise,
            "duree_minutes": duree_minutes,
            "updated_by_id": current_user.id,
        },
        distribution_updates={},
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )

    interruption, distribution = result
    # Une seule date de réalimentation : l'étape « Remise » du workflow prend la date de clôture
    await workflow_repo.synchroniser_remise(db, interruption.id, body.date_remise)
    await interruption_cycle_service.enregistrer(
        db, interruption, action=ACTION_CLOTURE, ancien_statut="en_cours", user=current_user
    )

    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={
            "statut": "cloture",
            "date_remise": body.date_remise.isoformat(),
            "duree_minutes": duree_minutes,
        },
    )

    await db.commit()

    from app.workers.tasks.indicateurs import calcul_end_task

    calcul_end_task.delay(interruption.id)

    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_CLOTUREE,
        entity_type="interruption",
        entity_id=interruption.id,
        service_id=interruption.service_id,
    )

    return await _response_after_commit(db, interruption.id)


async def valider(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> InterruptionDistributionResponse:
    """Valide une interruption clôturée et déclenche le calcul SAIFI/SAIDI async."""
    _ensure_can_validate(current_user)
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_cloture(interruption)

    old_values = {
        "statut": interruption.statut,
        "validated_by_id": interruption.validated_by_id,
    }

    result = await repo.update_interruption_distribution(
        db,
        interruption_id,
        interruption_updates={
            "statut": "valide",
            "validated_by_id": current_user.id,
            "updated_by_id": current_user.id,
        },
        distribution_updates={},
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Interruption {interruption_id} introuvable",
            },
        )

    interruption, distribution = result
    await interruption_cycle_service.enregistrer(
        db, interruption, action=ACTION_VALIDATION, ancien_statut="cloture", user=current_user
    )

    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={
            "statut": "valide",
            "validated_by_id": current_user.id,
        },
    )

    await db.commit()

    if interruption.service_id is not None and interruption.date_remise is not None:
        region_id = await end_repo.get_region_id_for_service(db, interruption.service_id)
        if region_id is not None:
            invalidate_indicateurs_cache(region_id, interruption.date_remise)

    from app.workers.tasks.indicateurs import calcul_saifi_saidi_task

    calcul_saifi_saidi_task.delay(interruption.id)

    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_VALIDEE,
        entity_type="interruption",
        entity_id=interruption.id,
        service_id=interruption.service_id,
    )

    return await _response_after_commit(db, interruption.id)


# ---------------------------------------------------------------------------
# Cycle de vie : historique, renvoi en correction, dévalidation, archivage
# ---------------------------------------------------------------------------


async def historique_statuts(
    db: AsyncSession, interruption_id: int, current_user: Utilisateur
) -> list[StatutHistoriqueResponse]:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    return await interruption_cycle_service.historique(db, interruption.id)


async def renvoyer_en_correction(
    db: AsyncSession, interruption_id: int, body: MotifRequest, current_user: Utilisateur
) -> InterruptionDistributionResponse:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    await interruption_cycle_service.renvoyer_en_correction(db, interruption, body.motif, current_user)
    return await _response_after_commit(db, interruption_id)


async def devalider(
    db: AsyncSession, interruption_id: int, body: MotifRequest, current_user: Utilisateur
) -> InterruptionDistributionResponse:
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    await interruption_cycle_service.devalider(db, interruption, body.motif, current_user)
    return await _response_after_commit(db, interruption_id)


async def archiver_mois(
    db: AsyncSession, body: ArchivageRequest, current_user: Utilisateur
) -> ArchivageResponse:
    _ensure_not_transport_role(current_user)
    return await interruption_cycle_service.archiver_mois(
        db, type_direction="distribution", annee=body.annee, mois=body.mois, user=current_user
    )


async def valider_lot(
    db: AsyncSession, body: ValidationLotRequest, current_user: Utilisateur
) -> ValidationLotResponse:
    """Valide plusieurs interruptions en une requête ; chaque ligne réussit ou échoue seule."""
    _ensure_can_validate(current_user)
    validees: list[int] = []
    echecs: list[ValidationLotEchec] = []
    for interruption_id in dict.fromkeys(body.ids):  # sans doublon, ordre conservé
        try:
            await valider(db, interruption_id, current_user)
            validees.append(interruption_id)
        except HTTPException as exc:
            await db.rollback()
            detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
            echecs.append(ValidationLotEchec(id=interruption_id, erreur=str(detail.get("error"))))
    return ValidationLotResponse(validees=validees, echecs=echecs)


async def exporter_liste(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    format: str,
    filtres_libelle: str,
    **filtres: object,
) -> tuple[bytes, str, str]:
    """Liste filtrée (même périmètre que l'écran) en Excel ou PDF : (contenu, type MIME, nom)."""
    import asyncio

    from app.services import interruption_export_service as export

    page = await list_items(
        db,
        current_user,
        page=1,
        page_size=export.MAX_LIGNES_EXPORT,
        _max_page_size=export.MAX_LIGNES_EXPORT,
        **filtres,  # type: ignore[arg-type]
    )
    if page.total > export.MAX_LIGNES_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": (
                    f"{page.total} interruptions : l'export est limité à {export.MAX_LIGNES_EXPORT} lignes. "
                    "Réduisez la période ou ajoutez un filtre."
                ),
            },
        )
    horodatage = datetime.now().strftime("%Y%m%d_%H%M")
    if format == "pdf":
        contenu = await asyncio.to_thread(export.construire_pdf, page.items, filtres_libelle)
        return contenu, "application/pdf", f"interruptions_{horodatage}.pdf"
    contenu = await asyncio.to_thread(export.construire_xlsx, page.items, filtres_libelle)
    return (
        contenu,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"interruptions_{horodatage}.xlsx",
    )
