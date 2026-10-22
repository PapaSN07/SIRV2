"""Service métier — interruptions réseau transport (Sprint 4)."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.interruptions import Interruption, InterruptionTransport
from app.models.utilisateurs import Utilisateur
from app.repositories import interruption_transport_repository as repo
from app.repositories import referentiel_repository as ref_repo
from app.repositories import reseau_transport_repository as reseau_repo
from app.repositories import end_repository as end_repo
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_distribution import (
    EnergieNdSummaryResponse,
    InterruptionClotureRequest,
    UtilisateurSummaryResponse,
)
from app.schemas.interruption_transport import (
    CREATE_ROLES,
    READ_ROLES,
    VALIDATE_ROLES,
    InterruptionTransportCreate,
    InterruptionTransportDetailResponse,
    InterruptionTransportResponse,
    InterruptionTransportUpdate,
)
from app.services.indicateurs_cache_service import invalidate_indicateurs_cache
from app.utils.audit import ACTION_CREATE, ACTION_UPDATE, log_audit

_TRANSPORT_TYPE_RESEAU = frozenset({"transport", "commun"})
_DISTRIBUTION_ROLES = frozenset({"BCC", "BRC", "ADMIN_SCR", "SUPERVISEUR"})


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _ensure_not_distribution_role(user: Utilisateur) -> None:
    """Blocage explicite des rôles distribution sur le transport HTB."""
    if is_superadmin(user):
        return
    if _user_role_names(user).intersection(_DISTRIBUTION_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès interruptions transport non autorisé pour ce rôle",
            },
        )


def _ensure_can_create(user: Utilisateur) -> None:
    _ensure_not_distribution_role(user)
    if not _user_role_names(user).intersection(CREATE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Création interruption transport non autorisée pour ce rôle",
            },
        )


def _ensure_can_read(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    _ensure_not_distribution_role(user)
    if not _user_role_names(user).intersection(READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès lecture interruptions transport non autorisé",
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


async def _validate_referentiel_transport(
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
    if cause.type_reseau not in _TRANSPORT_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "La cause doit être de type transport ou commun",
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
    if siege.type_reseau not in _TRANSPORT_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Le siège doit être de type transport ou commun",
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
    if signalisation.type_reseau not in _TRANSPORT_TYPE_RESEAU:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "La signalisation doit être de type transport ou commun",
            },
        )


async def _validate_equipement_and_poste_ligne(
    db: AsyncSession,
    *,
    equipement_transport_id: int,
    poste_ligne_id: int | None,
    source_transport_id: int | None,
) -> None:
    equipement = await reseau_repo.get_equipement(db, equipement_transport_id)
    if equipement is None or not equipement.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Équipement transport {equipement_transport_id} introuvable ou inactif",
            },
        )

    if source_transport_id is not None:
        source = await reseau_repo.get_source(db, source_transport_id)
        if source is None or not source.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Source transport {source_transport_id} introuvable ou inactive",
                },
            )

    if poste_ligne_id is not None:
        poste_ligne = await reseau_repo.get_poste_ligne(db, poste_ligne_id)
        if poste_ligne is None or not poste_ligne.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Poste ligne {poste_ligne_id} introuvable ou inactif",
                },
            )
        if poste_ligne.equipement_transport_id != equipement_transport_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "poste_ligne_id incohérent avec equipement_transport_id",
                },
            )


def _to_response(
    interruption: Interruption,
    transport: InterruptionTransport,
) -> InterruptionTransportResponse:
    return InterruptionTransportResponse(
        id=interruption.id,
        numero_interruption=interruption.numero_interruption,
        type_direction=interruption.type_direction,  # type: ignore[arg-type]
        statut=interruption.statut,  # type: ignore[arg-type]
        service_id=interruption.service_id,
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
        tension_kv=float(transport.tension_kv) if transport.tension_kv is not None else None,
        equipement_transport_id=transport.equipement_transport_id,
        source_transport_id=transport.source_transport_id,
        puissance_transit_mw=float(transport.puissance_transit_mw)
        if transport.puissance_transit_mw is not None
        else None,
        energie_non_fournie_mwh=float(transport.energie_non_fournie_mwh)
        if transport.energie_non_fournie_mwh is not None
        else None,
        created_by_id=interruption.created_by_id,
        created_at=interruption.created_at,
        updated_at=interruption.updated_at,
    )


def _to_detail_response(
    interruption: Interruption,
    transport: InterruptionTransport,
) -> InterruptionTransportDetailResponse:
    base = _to_response(interruption, transport)
    energie_non_fournie = base.energie_non_fournie_mwh
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
        energie_non_fournie = float(nd.valeur_mwh)
    elif energie_non_fournie is None and transport.energie_non_fournie_mwh is not None:
        energie_non_fournie = float(transport.energie_non_fournie_mwh)

    detail_data = base.model_dump()
    detail_data["energie_non_fournie_mwh"] = energie_non_fournie

    equipement = transport.equipement_transport
    source = transport.source_transport

    return InterruptionTransportDetailResponse(
        **detail_data,
        equipement_libelle=equipement.libelle if equipement else None,
        source_libelle=source.libelle if source else None,
        cause_libelle=interruption.cause.libelle if interruption.cause else None,
        nature_libelle=interruption.nature.libelle if interruption.nature else None,
        siege_libelle=interruption.siege.libelle if interruption.siege else None,
        signalisation_libelle=interruption.signalisation.libelle
        if interruption.signalisation
        else None,
        energie_nd=energie_nd_summary,
        created_by=_user_summary(interruption.created_by),
        validated_by=_user_summary(interruption.validated_by),
        validated_by_id=interruption.validated_by_id,
    )


async def create(
    db: AsyncSession,
    body: InterruptionTransportCreate,
    current_user: Utilisateur,
) -> InterruptionTransportResponse:
    """Crée une interruption transport ou OMVG (statut initial en_cours)."""
    _ensure_can_create(current_user)

    await _validate_equipement_and_poste_ligne(
        db,
        equipement_transport_id=body.equipement_transport_id,
        poste_ligne_id=body.poste_ligne_id,
        source_transport_id=body.source_transport_id,
    )

    await _validate_referentiel_transport(
        db,
        cause_id=body.cause_id,
        nature_id=body.nature_id,
        siege_id=body.siege_id,
        signalisation_id=body.signalisation_id,
    )

    year = body.date_apparition.year
    numero = await repo.next_numero_interruption(
        db,
        year=year,
        type_direction=body.type_direction,
    )

    interruption_values = {
        "numero_interruption": numero,
        "type_direction": body.type_direction,
        "statut": "en_cours",
        "service_id": None,
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

    transport_values = {
        "equipement_transport_id": body.equipement_transport_id,
        "source_transport_id": body.source_transport_id,
        "tension_kv": body.tension_kv,
        "puissance_transit_mw": body.puissance_transit_mw,
    }

    interruption, transport = await repo.create_interruption_transport(
        db,
        interruption_values=interruption_values,
        transport_values=transport_values,
    )

    await log_audit(
        db,
        table_name="interruptions",
        record_id=interruption.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={
            "numero_interruption": numero,
            "type_direction": body.type_direction,
            "statut": "en_cours",
            "equipement_transport_id": body.equipement_transport_id,
        },
    )

    await db.commit()

    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.INTERRUPTION_CREEE,
        entity_type="interruption",
        entity_id=interruption.id,
        service_id=interruption.service_id,
    )

    return _to_response(interruption, transport)


async def list_items(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    page: int = 1,
    page_size: int = 20,
    type_direction: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    equipement_transport_id: int | None = None,
    source_transport_id: int | None = None,
) -> PaginatedResponse[InterruptionTransportResponse]:
    """Liste paginée des interruptions transport/OMVG (périmètre national)."""
    _ensure_can_read(current_user)

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
        type_direction=type_direction,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        equipement_transport_id=equipement_transport_id,
        source_transport_id=source_transport_id,
    )

    items: list[InterruptionTransportResponse] = []
    for interruption in result.items:
        transport = interruption.interruption_transport
        if transport is None:
            continue
        items.append(_to_response(interruption, transport))

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
) -> InterruptionTransportDetailResponse:
    """Détail complet d'une interruption transport ou OMVG."""
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

    transport = interruption.interruption_transport
    if transport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Détails transport absents pour interruption {interruption_id}",
            },
        )

    return _to_detail_response(interruption, transport)


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
    return interruption


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
    """Validation réservée Admin Dispatching et Admin SAQS."""
    if is_superadmin(user):
        return
    _ensure_not_distribution_role(user)
    if not _user_role_names(user).intersection(VALIDATE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Validation réservée à Admin Dispatching et Admin SAQS",
            },
        )


def _ensure_can_modify(user: Utilisateur, interruption: Interruption) -> None:
    """Seul le créateur ou Admin Dispatching peut modifier une interruption transport."""
    if is_superadmin(user):
        return
    if "ADMIN_DISPATCHING" in _user_role_names(user):
        return
    if interruption.created_by_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Seul le créateur ou Admin Dispatching peut modifier cette interruption",
        },
    )


def _snapshot_interruption(interruption: Interruption) -> dict[str, object]:
    transport = interruption.interruption_transport
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
    if transport is not None:
        snapshot.update(
            {
                "tension_kv": float(transport.tension_kv)
                if transport.tension_kv is not None
                else None,
                "puissance_transit_mw": float(transport.puissance_transit_mw)
                if transport.puissance_transit_mw is not None
                else None,
                "source_transport_id": transport.source_transport_id,
            }
        )
    return snapshot


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


async def update(
    db: AsyncSession,
    interruption_id: int,
    body: InterruptionTransportUpdate,
    current_user: Utilisateur,
) -> InterruptionTransportResponse:
    """Met à jour une interruption transport (statut en_cours uniquement)."""
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
        await _validate_referentiel_transport(
            db,
            cause_id=cause_id,
            nature_id=nature_id,
            siege_id=siege_id,
            signalisation_id=signalisation_id,
        )

    if "source_transport_id" in updates and updates["source_transport_id"] is not None:
        source = await reseau_repo.get_source(db, updates["source_transport_id"])
        if source is None or not source.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Source transport {updates['source_transport_id']} introuvable ou inactive",
                },
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
    transport_fields = {"tension_kv", "puissance_transit_mw", "source_transport_id"}

    interruption_updates = {k: v for k, v in updates.items() if k in interruption_fields}
    interruption_updates["updated_by_id"] = current_user.id
    transport_updates = {k: v for k, v in updates.items() if k in transport_fields}

    result = await repo.update_interruption_transport(
        db,
        interruption_id,
        interruption_updates=interruption_updates,
        transport_updates=transport_updates,
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

    interruption, transport = result
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
    return _to_response(interruption, transport)


async def cloturer(
    db: AsyncSession,
    interruption_id: int,
    body: InterruptionClotureRequest,
    current_user: Utilisateur,
) -> InterruptionTransportResponse:
    """Clôture une interruption transport et déclenche le calcul END async."""
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_en_cours(interruption)
    _ensure_can_modify(current_user, interruption)

    duree_minutes = _compute_duree_minutes(interruption.date_apparition, body.date_remise)

    old_values = {"statut": interruption.statut, "date_remise": None, "duree_minutes": None}

    result = await repo.update_interruption_transport(
        db,
        interruption_id,
        interruption_updates={
            "statut": "cloture",
            "date_remise": body.date_remise,
            "duree_minutes": duree_minutes,
            "updated_by_id": current_user.id,
        },
        transport_updates={},
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

    interruption, transport = result

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

    return _to_response(interruption, transport)


async def valider(
    db: AsyncSession,
    interruption_id: int,
    current_user: Utilisateur,
) -> InterruptionTransportResponse:
    """Valide une interruption transport clôturée et déclenche le calcul SAIFI/SAIDI async."""
    _ensure_can_validate(current_user)
    interruption = await _get_interruption_accessible(db, interruption_id, current_user)
    _ensure_statut_cloture(interruption)

    old_values = {
        "statut": interruption.statut,
        "validated_by_id": interruption.validated_by_id,
    }

    result = await repo.update_interruption_transport(
        db,
        interruption_id,
        interruption_updates={
            "statut": "valide",
            "validated_by_id": current_user.id,
            "updated_by_id": current_user.id,
        },
        transport_updates={},
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

    interruption, transport = result

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

    return _to_response(interruption, transport)
