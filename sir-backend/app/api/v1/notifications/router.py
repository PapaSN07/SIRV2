from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.core.database import get_db
from app.core.deps import require_permission
from app.core.redis import get_redis
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.notifications import (
    DestinataireCreate,
    DestinataireResponse,
    DestinataireUpdate,
    EmailEnvoyeResponse,
    GroupeEnvoiResponse,
    ManualSmsSendRequest,
    ManualSmsSendResponse,
    SmsEnvoyeResponse,
)
from app.services import (
    auth_service,
    destinataire_service,
    manual_sms_service,
    notification_stream_service,
    notification_trace_service,
)

router = APIRouter()

_NATIONAL_ROLES = frozenset({"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS", "DISPATCHER"})


@router.get(
    "/destinataires",
    response_model=ApiResponse[PaginatedResponse[DestinataireResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée des destinataires notifications",
)
async def list_destinataires(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service_id: int | None = Query(None, ge=1),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[PaginatedResponse[DestinataireResponse]]:
    result = await destinataire_service.list_destinataires(
        db,
        current_user,
        page=page,
        page_size=page_size,
        service_id=service_id,
        is_active=is_active,
    )
    return ApiResponse.success(result)


@router.get(
    "/groupes-envoi",
    response_model=ApiResponse[list[GroupeEnvoiResponse]],
    status_code=status.HTTP_200_OK,
    summary="Groupes d'envoi SMS (Répertoire SIR v1) avec le nombre de destinataires joignables",
)
async def list_groupes_envoi(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[list[GroupeEnvoiResponse]]:
    result = await destinataire_service.list_groupes_envoi(db, current_user)
    return ApiResponse.success(result)


@router.post(
    "/destinataires",
    response_model=ApiResponse[DestinataireResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un destinataire",
)
async def create_destinataire(
    body: DestinataireCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "admin")),
) -> ApiResponse[DestinataireResponse]:
    result = await destinataire_service.create_destinataire(db, current_user, body)
    return ApiResponse.success(result)


@router.get(
    "/destinataires/{destinataire_id}",
    response_model=ApiResponse[DestinataireResponse],
    status_code=status.HTTP_200_OK,
)
async def get_destinataire(
    destinataire_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[DestinataireResponse]:
    result = await destinataire_service.get_destinataire(db, current_user, destinataire_id)
    return ApiResponse.success(result)


@router.patch(
    "/destinataires/{destinataire_id}",
    response_model=ApiResponse[DestinataireResponse],
    status_code=status.HTTP_200_OK,
)
async def update_destinataire(
    destinataire_id: int,
    body: DestinataireUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "admin")),
) -> ApiResponse[DestinataireResponse]:
    result = await destinataire_service.update_destinataire(
        db, current_user, destinataire_id, body
    )
    return ApiResponse.success(result)


@router.delete(
    "/destinataires/{destinataire_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un destinataire (soft delete)",
)
async def delete_destinataire(
    destinataire_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "admin")),
) -> None:
    await destinataire_service.delete_destinataire(db, current_user, destinataire_id)


@router.get(
    "/emails",
    response_model=ApiResponse[PaginatedResponse[EmailEnvoyeResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = Query(None),
    statut: str | None = Query(None),
    date_debut: datetime | None = Query(None),
    date_fin: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[PaginatedResponse[EmailEnvoyeResponse]]:
    result = await notification_trace_service.list_emails(
        db,
        current_user,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.get(
    "/emails/{email_id}",
    response_model=ApiResponse[EmailEnvoyeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_email(
    email_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[EmailEnvoyeResponse]:
    result = await notification_trace_service.get_email(db, current_user, email_id)
    return ApiResponse.success(result)


@router.get(
    "/sms",
    response_model=ApiResponse[PaginatedResponse[SmsEnvoyeResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_sms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = Query(None),
    statut: str | None = Query(None),
    date_debut: datetime | None = Query(None),
    date_fin: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[PaginatedResponse[SmsEnvoyeResponse]]:
    result = await notification_trace_service.list_sms(
        db,
        current_user,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.post(
    "/sms/send",
    response_model=ApiResponse[ManualSmsSendResponse],
    status_code=status.HTTP_200_OK,
    summary="Envoyer un SMS manuel à des destinataires ou utilisateurs",
)
async def send_manual_sms(
    body: ManualSmsSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "admin")),
) -> ApiResponse[ManualSmsSendResponse]:
    result = await manual_sms_service.send_manual_sms(
        db,
        current_user,
        message=body.message,
        destinataire_ids=body.destinataire_ids,
        utilisateur_ids=body.utilisateur_ids,
    )
    return ApiResponse.success(result)


@router.get(
    "/sms/{sms_id}",
    response_model=ApiResponse[SmsEnvoyeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_sms(
    sms_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("notifications", "read")),
) -> ApiResponse[SmsEnvoyeResponse]:
    result = await notification_trace_service.get_sms(db, current_user, sms_id)
    return ApiResponse.success(result)


@router.get(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Flux SSE notifications temps réel (token en query param)",
)
async def notification_stream(
    token: str = Query(..., description="JWT access token (EventSource ne supporte pas les headers)"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    user = await auth_service.get_current_user(db, redis, token)
    role_names = {ur.role.nom for ur in user.user_roles}
    is_national = is_superadmin(user) or bool(role_names.intersection(_NATIONAL_ROLES))
    scope_id = user.user_roles[0].scope_service_id if user.user_roles else None
    # Convention user_roles : BCC/BRC → scope = region_id ; Superviseur → scope = service_id
    is_regional = bool(role_names.intersection({"BCC", "BRC"}))
    channels = notification_stream_service.subscribe_channels_for_user(
        is_national=is_national,
        region_id=scope_id if is_regional else None,
        service_id=scope_id if not is_regional and "SUPERVISEUR" in role_names else None,
    )

    async def is_still_authorized() -> bool:
        try:
            await auth_service.validate_access_token(redis, token)
        except HTTPException:
            return False
        return True

    async def event_generator():
        async for chunk in notification_stream_service.iter_sse_events(
            redis, channels, is_still_authorized=is_still_authorized
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
