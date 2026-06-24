"""Service métier — NAPT."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.napt import Consignation, Napt
from app.models.utilisateurs import Utilisateur
from app.repositories import napt_repository as repo
from app.schemas.common import PaginatedResponse
from app.schemas.napt import (
    ConsignationCreate,
    ConsignationResponse,
    NaptCreate,
    NaptResponse,
    NaptUpdate,
)
from app.utils.audit import ACTION_CREATE, ACTION_UPDATE, log_audit

VALIDATE_ROLES = frozenset({"SUPERVISEUR", "ADMIN_SCR", "ADMIN_SAQS"})
WRITE_ROLES = frozenset({"BCC", "ADMIN_SCR"})


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _to_consignation_response(c: Consignation) -> ConsignationResponse:
    return ConsignationResponse.model_validate(c)


def _to_response(napt: Napt) -> NaptResponse:
    return NaptResponse(
        id=napt.id,
        numero_napt=napt.numero_napt,
        service_id=napt.service_id,
        feeder_id=napt.feeder_id,
        statut=napt.statut,  # type: ignore[arg-type]
        objet_travaux=napt.objet_travaux,
        date_debut_prevue=napt.date_debut_prevue,
        date_fin_prevue=napt.date_fin_prevue,
        date_debut_reelle=napt.date_debut_reelle,
        date_fin_reelle=napt.date_fin_reelle,
        is_interruption_necessaire=napt.is_interruption_necessaire,
        observations=napt.observations,
        created_by_id=napt.created_by_id,
        approved_by_id=napt.approved_by_id,
        created_at=napt.created_at,
        updated_at=napt.updated_at,
        service_libelle=napt.service.libelle if napt.service else None,
        feeder_libelle=napt.feeder.libelle if napt.feeder else None,
        consignations=[_to_consignation_response(c) for c in napt.consignations],
    )


def _ensure_write(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if not _user_role_names(user).intersection(WRITE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Permission refusée"},
        )


def _ensure_validate(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if not _user_role_names(user).intersection(VALIDATE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Permission refusée"},
        )


async def list_items(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    page: int = 1,
    page_size: int = 20,
    service_id: int | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse[NaptResponse]:
    result = await repo.list_napt_paginated(
        db,
        page=page,
        page_size=page_size,
        service_id=service_id,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return PaginatedResponse(
        items=[_to_response(n) for n in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_item(db: AsyncSession, napt_id: int, current_user: Utilisateur) -> NaptResponse:
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    return _to_response(napt)


async def create(
    db: AsyncSession,
    body: NaptCreate,
    current_user: Utilisateur,
) -> NaptResponse:
    _ensure_write(current_user)
    service = await repo.get_service(db, body.service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "data": None, "error": "Service introuvable"},
        )
    if body.feeder_id is not None:
        feeder = await repo.get_feeder(db, body.feeder_id)
        if feeder is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"status": "error", "data": None, "error": "Feeder introuvable"},
            )

    year = body.date_debut_prevue.year
    numero = await repo.next_numero_napt(db, year)
    napt = await repo.create_napt(
        db,
        {
            "numero_napt": numero,
            "service_id": body.service_id,
            "feeder_id": body.feeder_id,
            "statut": "brouillon",
            "objet_travaux": body.objet_travaux,
            "date_debut_prevue": body.date_debut_prevue,
            "date_fin_prevue": body.date_fin_prevue,
            "is_interruption_necessaire": body.is_interruption_necessaire,
            "observations": body.observations,
            "created_by_id": current_user.id,
        },
    )
    await log_audit(
        db,
        table_name="napt",
        record_id=napt.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={"numero_napt": numero, "statut": "brouillon"},
    )
    await db.commit()
    loaded = await repo.get_napt(db, napt.id)
    assert loaded is not None
    return _to_response(loaded)


async def update(
    db: AsyncSession,
    napt_id: int,
    body: NaptUpdate,
    current_user: Utilisateur,
) -> NaptResponse:
    _ensure_write(current_user)
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    if napt.statut != "brouillon":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "data": None, "error": "Modification autorisée en brouillon uniquement"},
        )
    values = body.model_dump(exclude_unset=True)
    await repo.update_napt(db, napt, values)
    await log_audit(
        db,
        table_name="napt",
        record_id=napt.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        new_values=values,
    )
    await db.commit()
    loaded = await repo.get_napt(db, napt.id)
    assert loaded is not None
    return _to_response(loaded)


async def _transition(
    db: AsyncSession,
    napt_id: int,
    current_user: Utilisateur,
    *,
    expected: str,
    new_statut: str,
    extra: dict | None = None,
) -> NaptResponse:
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    if napt.statut != expected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"Transition impossible depuis le statut {napt.statut}",
            },
        )
    values: dict = {"statut": new_statut}
    if extra:
        values.update(extra)
    await repo.update_napt(db, napt, values)
    await log_audit(
        db,
        table_name="napt",
        record_id=napt.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        new_values=values,
    )
    await db.commit()
    loaded = await repo.get_napt(db, napt.id)
    assert loaded is not None
    return _to_response(loaded)


async def soumettre(db: AsyncSession, napt_id: int, current_user: Utilisateur) -> NaptResponse:
    _ensure_write(current_user)
    return await _transition(db, napt_id, current_user, expected="brouillon", new_statut="soumis")


async def valider(db: AsyncSession, napt_id: int, current_user: Utilisateur) -> NaptResponse:
    _ensure_validate(current_user)
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    return await _transition(
        db,
        napt_id,
        current_user,
        expected="soumis",
        new_statut="approuve",
        extra={"approved_by_id": current_user.id},
    )


async def executer(db: AsyncSession, napt_id: int, current_user: Utilisateur) -> NaptResponse:
    _ensure_write(current_user)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return await _transition(
        db,
        napt_id,
        current_user,
        expected="approuve",
        new_statut="approuve",
        extra={"date_debut_reelle": now},
    )


async def cloturer(db: AsyncSession, napt_id: int, current_user: Utilisateur) -> NaptResponse:
    _ensure_write(current_user)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    if napt.statut not in ("approuve", "soumis"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "data": None, "error": "Clôture impossible pour ce statut"},
        )
    return await _transition(
        db,
        napt_id,
        current_user,
        expected=napt.statut,
        new_statut="archive",
        extra={"date_fin_reelle": now},
    )


async def add_consignation(
    db: AsyncSession,
    napt_id: int,
    body: ConsignationCreate,
    current_user: Utilisateur,
) -> ConsignationResponse:
    _ensure_write(current_user)
    napt = await repo.get_napt(db, napt_id)
    if napt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": f"NAPT {napt_id} introuvable"},
        )
    cons = await repo.create_consignation(
        db,
        {
            "napt_id": napt_id,
            "numero_consignation": body.numero_consignation,
            "statut": "ouverte",
            "date_ouverture": body.date_ouverture,
            "agent_consignateur_id": body.agent_consignateur_id,
            "observations": body.observations,
        },
    )
    await db.commit()
    return _to_consignation_response(cons)
