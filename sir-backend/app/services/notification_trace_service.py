"""Service — consultation traces emails/SMS."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.notifications import EmailEnvoye, SmsEnvoye
from app.models.utilisateurs import Utilisateur
from app.repositories import destinataire_repository as dest_repo
from app.repositories import email_repository as email_repo
from app.repositories import sms_repository as sms_repo
from app.schemas.common import PaginatedResponse
from app.schemas.notifications import EmailEnvoyeResponse, SmsEnvoyeResponse
from app.services import destinataire_service
from app.utils.pagination import paginate

_NATIONAL_ROLES = frozenset({"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS"})


def _sms_to_response(record: SmsEnvoye) -> SmsEnvoyeResponse:
    dest = record.destinataire
    utilisateur_login = None
    if dest is not None and dest.utilisateur is not None:
        utilisateur_login = dest.utilisateur.login
    return SmsEnvoyeResponse(
        id=record.id,
        destinataire_id=record.destinataire_id,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        contenu=record.contenu,
        statut=record.statut,
        sent_at=record.sent_at,
        erreur=record.erreur,
        created_at=record.created_at,
        destinataire_nom=dest.nom if dest else None,
        destinataire_telephone=dest.telephone if dest else None,
        utilisateur_login=utilisateur_login,
    )


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


async def _destinataire_ids_in_scope(
    db: AsyncSession,
    user: Utilisateur,
) -> list[int] | None:
    if is_superadmin(user) or _user_role_names(user).intersection(_NATIONAL_ROLES):
        return None

    page = await destinataire_service.list_destinataires(
        db,
        user,
        page=1,
        page_size=500,
        service_id=None,
        is_active=None,
    )
    return [item.id for item in page.items]


async def list_emails(
    db: AsyncSession,
    user: Utilisateur,
    *,
    page: int,
    page_size: int,
    entity_type: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
) -> PaginatedResponse[EmailEnvoyeResponse]:
    destinataire_ids = await _destinataire_ids_in_scope(db, user)
    query = email_repo.build_list_query(
        entity_type=entity_type,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        destinataire_ids=destinataire_ids,
    )
    result = await paginate(db, query, page, page_size, scalar_type=EmailEnvoye)
    return PaginatedResponse(
        items=[EmailEnvoyeResponse.model_validate(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_email(
    db: AsyncSession,
    user: Utilisateur,
    email_id: int,
) -> EmailEnvoyeResponse:
    record = await email_repo.get_by_id(db, email_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Email introuvable"},
        )
    if await _destinataire_ids_in_scope(db, user) is not None:
        dest = await dest_repo.get_by_id(db, record.destinataire_id)
        if dest is None:
            raise HTTPException(status_code=404, detail={"status": "error", "data": None, "error": "Hors périmètre"})
        await destinataire_service.assert_destinataire_in_scope(db, user, dest)
    return EmailEnvoyeResponse.model_validate(record)


async def list_sms(
    db: AsyncSession,
    user: Utilisateur,
    *,
    page: int,
    page_size: int,
    entity_type: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
) -> PaginatedResponse[SmsEnvoyeResponse]:
    destinataire_ids = await _destinataire_ids_in_scope(db, user)
    query = sms_repo.build_list_query(
        entity_type=entity_type,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        destinataire_ids=destinataire_ids,
    )
    result = await paginate(db, query, page, page_size, scalar_type=SmsEnvoye)
    return PaginatedResponse(
        items=[_sms_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_sms(
    db: AsyncSession,
    user: Utilisateur,
    sms_id: int,
) -> SmsEnvoyeResponse:
    record = await sms_repo.get_by_id(db, sms_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "SMS introuvable"},
        )
    if await _destinataire_ids_in_scope(db, user) is not None:
        dest = await dest_repo.get_by_id(db, record.destinataire_id)
        if dest is None:
            raise HTTPException(status_code=404, detail={"status": "error", "data": None, "error": "Hors périmètre"})
        await destinataire_service.assert_destinataire_in_scope(db, user, dest)
    return _sms_to_response(record)
