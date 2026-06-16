"""Service métier — interruptions réseau distribution (Sprint 3)."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_service_scope
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.reseau import Poste
from app.models.utilisateurs import Utilisateur
from app.repositories import interruption_distribution_repository as repo
from app.repositories import end_repository as end_repo
from app.repositories import referentiel_repository as ref_repo
from app.repositories import reseau_distribution_repository as reseau_repo
from app.repositories.reseau_distribution_repository import ScopeFilter
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_distribution import (
    EnergieNdSummaryResponse,
    InterruptionDistributionCreate,
    InterruptionDistributionDetailResponse,
    InterruptionDistributionResponse,
    InterruptionClotureRequest,
    InterruptionDistributionUpdate,
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
    """Scope repository : BCC/Superviseur → service · BRC → région · Admin → national."""
    roles = _user_role_names(user)
    if roles.intersection({"ADMIN_SCR", "ADMIN_SAQS"}):
        return None
    if "BCC" in roles or "SUPERVISEUR" in roles:
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
    if "BRC" in roles:
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
    return None


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

    postes = [
        PosteImpacteResponse(
            poste_id=pi.poste_id,
            poste_code=pi.poste.code if pi.poste else None,
            poste_libelle=pi.poste.libelle if pi.poste else None,
            nombre_clients_touches=pi.nombre_clients_touches,
        )
        for pi in interruption.postes_interrompus
    ]

    detail_data = base.model_dump()
    detail_data["end_mwh"] = end_mwh

    return InterruptionDistributionDetailResponse(
        **detail_data,
        feeder_libelle=interruption.feeder.libelle if interruption.feeder else None,
        cause_libelle=interruption.cause.libelle if interruption.cause else None,
        nature_libelle=interruption.nature.libelle if interruption.nature else None,
        siege_libelle=interruption.siege.libelle if interruption.siege else None,
        signalisation_libelle=interruption.signalisation.libelle
        if interruption.signalisation
        else None,
        service_code=interruption.service.code if interruption.service else None,
        service_libelle=interruption.service.libelle if interruption.service else None,
        postes_impactes=postes,
        energie_nd=energie_nd_summary,
        created_by=_user_summary(interruption.created_by),
        validated_by=_user_summary(interruption.validated_by),
        validated_by_id=interruption.validated_by_id,
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
        statut=interruption.statut,  # type: ignore[arg-type]
        service_id=interruption.service_id,
        feeder_id=interruption.feeder_id,
        poste_source_id=interruption.poste_source_id,
        date_apparition=interruption.date_apparition,
        date_remise=interruption.date_remise,
        duree_minutes=interruption.duree_minutes,
        cause_id=interruption.cause_id,
        nature_id=interruption.nature_id,
        siege_id=interruption.siege_id,
        signalisation_id=interruption.signalisation_id,
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
        created_at=interruption.created_at,
        updated_at=interruption.updated_at,
        cause_libelle=interruption.cause.libelle if interruption.cause else None,
        region_libelle=_region_libelle(interruption),
    )


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

    check_service_scope(current_user, feeder.service_id)

    await _validate_referentiel_distribution(
        db,
        cause_id=body.cause_id,
        nature_id=body.nature_id,
        siege_id=body.siege_id,
        signalisation_id=body.signalisation_id,
    )

    year = body.date_apparition.year
    numero = await repo.next_numero_interruption(db, year=year)

    interruption_values = {
        "numero_interruption": numero,
        "type_direction": "distribution",
        "statut": "en_cours",
        "service_id": feeder.service_id,
        "feeder_id": feeder.id,
        "poste_source_id": feeder.poste_source_id,
        "date_apparition": body.date_apparition,
        "cause_id": body.cause_id,
        "nature_id": body.nature_id,
        "siege_id": body.siege_id,
        "signalisation_id": body.signalisation_id,
        "puissance_coupee_mw": body.puissance_coupee_mw,
        "localisation": body.localisation,
        "observations": body.observations,
        "is_force_majeure": body.is_force_majeure,
        "is_fugitive": body.is_fugitive,
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

    await db.commit()

    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_CREEE,
        entity_type="interruption",
        entity_id=interruption.id,
        service_id=feeder.service_id,
    )

    return _to_response(interruption, distribution)


async def list_items(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    page: int = 1,
    page_size: int = 20,
    region_id: int | None = None,
    feeder_id: int | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse[InterruptionDistributionResponse]:
    """Liste paginée des interruptions distribution avec scope RBAC automatique."""
    _ensure_can_read(current_user)
    scope = _read_scope(current_user)

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
        feeder_id=feeder_id,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )

    items: list[InterruptionDistributionResponse] = []
    for interruption in result.items:
        distribution = interruption.interruption_distribution
        if distribution is None:
            continue
        items.append(_to_response(interruption, distribution))

    return PaginatedResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
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
    )


def _poste_in_perimeter(poste: Poste, interruption: Interruption) -> bool:
    if interruption.service_id is not None and poste.service_id == interruption.service_id:
        return True
    if interruption.feeder_id is not None and poste.feeder_id == interruption.feeder_id:
        return True
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

    if not _poste_in_perimeter(poste, interruption):
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

    link = await repo.add_poste_interruption(
        db,
        interruption_id=interruption.id,
        poste_id=body.poste_id,
        nombre_clients_touches=body.nombre_clients_touches,
    )
    link.poste = poste

    await log_audit(
        db,
        table_name="poste_interruptions",
        record_id=link.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={"interruption_id": interruption.id, "poste_id": body.poste_id},
    )

    await db.commit()
    return _poste_to_response(link)


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
    """Seul le créateur ou Admin SCR peut modifier une interruption."""
    if "ADMIN_SCR" in _user_role_names(user):
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

    interruption_fields = {
        "date_apparition",
        "cause_id",
        "nature_id",
        "siege_id",
        "signalisation_id",
        "puissance_coupee_mw",
        "localisation",
        "observations",
        "is_force_majeure",
        "is_fugitive",
    }
    distribution_fields = {
        "tension_kv",
        "nombre_clients_mt",
        "nombre_clients_bt",
        "is_programme",
        "has_extension_bt",
    }

    interruption_updates = {k: v for k, v in updates.items() if k in interruption_fields}
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
    return _to_response(interruption, distribution)


def _compute_duree_minutes(date_apparition: datetime, date_remise: datetime) -> int:
    delta = date_remise - date_apparition
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

    postes_count = await repo.count_postes_for_interruption(db, interruption.id)
    if postes_count < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Au moins un poste impacté est requis avant clôture",
            },
        )

    duree_minutes = _compute_duree_minutes(interruption.date_apparition, body.date_remise)

    old_values = {"statut": interruption.statut, "date_remise": None, "duree_minutes": None}

    result = await repo.update_interruption_distribution(
        db,
        interruption_id,
        interruption_updates={
            "statut": "cloture",
            "date_remise": body.date_remise,
            "duree_minutes": duree_minutes,
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

    return _to_response(interruption, distribution)


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

    return _to_response(interruption, distribution)
