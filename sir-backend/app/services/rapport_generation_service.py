"""Service — génération asynchrone de rapports CRSE (Sprint 6.6)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import check_region_scope
from app.models.rapports import RapportGenere
from app.models.utilisateurs import Utilisateur
from app.repositories import rapport_repository as repo
from app.schemas.rapports import (
    RapportEnqueueResponse,
    RapportJournalierRequest,
    RapportStatusResponse,
)
from app.services.rapport_export_service import (
    export_annuel,
    export_journalier,
    export_mensuel_distribution,
    export_mensuel_transport,
    generate_placeholder_file,
)
from app.services import (
    rapport_annuel_service,
    rapport_journalier_service,
    rapport_mensuel_service,
    rapport_mensuel_transport_service,
)
from app.repositories import utilisateur_repository

logger = logging.getLogger(__name__)

_NATIONAL_ROLES = frozenset({"ADMIN_SCR", "ADMIN_SAQS", "ADMIN_DISPATCHING", "DISPATCHER"})
_REGION_ROLES = frozenset({"BRC"})
_SERVICE_ROLES = frozenset({"BCC", "SUPERVISEUR"})
_NATIONAL_VIEW_ROLES = _NATIONAL_ROLES
_TRANSPORT_RAPPORT_ROLES = frozenset({"DISPATCHER", "ADMIN_DISPATCHING", "ADMIN_SAQS"})
_DISTRIBUTION_RAPPORT_ROLES = frozenset({"ADMIN_SAQS", "ADMIN_SCR", "BRC", "BCC", "SUPERVISEUR"})
_CONSOLIDE_RAPPORT_ROLES = frozenset({"ADMIN_SAQS"})
_ANNUEL_DIRECTIONS = frozenset({"distribution", "transport", "consolide"})


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _resolve_region_id(user: Utilisateur, region_id: int | None) -> int | None:
    roles = _user_role_names(user)

    if roles.intersection(_NATIONAL_ROLES):
        return region_id

    if roles.intersection(_REGION_ROLES):
        user_region_id = user.user_roles[0].scope_service_id
        if user_region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre régional non configuré pour ce compte",
                },
            )
        if region_id is not None and region_id != user_region_id:
            check_region_scope(user, region_id)
        return user_region_id

    if roles.intersection(_SERVICE_ROLES):
        if region_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Hors périmètre : filtre region_id non autorisé pour votre rôle",
                },
            )
        return None

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Rôle non autorisé pour la génération de rapports",
        },
    )


def _assert_distribution_rapport_role(user: Utilisateur) -> None:
    if not _user_role_names(user).intersection(_DISTRIBUTION_RAPPORT_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Rôle non autorisé pour les rapports distribution",
            },
        )


def _assert_transport_rapport_role(user: Utilisateur) -> None:
    if not _user_role_names(user).intersection(_TRANSPORT_RAPPORT_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Rôle non autorisé pour les rapports transport",
            },
        )


def _assert_annuel_direction(user: Utilisateur, direction: str) -> None:
    if direction not in _ANNUEL_DIRECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"direction invalide : '{direction}'",
            },
        )
    if direction == "consolide":
        if not _user_role_names(user).intersection(_CONSOLIDE_RAPPORT_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Rôle non autorisé pour les rapports consolidés",
                },
            )
        return
    if direction == "transport":
        _assert_transport_rapport_role(user)
        return
    _assert_distribution_rapport_role(user)


def _ensure_storage_dir() -> Path:
    storage_path = Path(settings.rapports_storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


def _expires_at() -> datetime:
    return datetime.now() + timedelta(hours=settings.rapports_file_ttl_hours)


def _to_status_response(record: RapportGenere) -> RapportStatusResponse:
    return RapportStatusResponse(
        task_id=record.task_id,
        type_rapport=record.type_rapport,
        format=record.format,
        statut=record.statut,
        error_message=record.error_message,
        file_name=record.file_name,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


def _assert_can_access(user: Utilisateur, record: RapportGenere) -> None:
    if _user_role_names(user).intersection(_NATIONAL_VIEW_ROLES):
        return
    if record.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès refusé à ce rapport",
            },
        )


def _assert_not_expired(record: RapportGenere) -> None:
    if record.expires_at is not None and datetime.now() > record.expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "status": "error",
                "data": None,
                "error": "Fichier expiré — relancez la génération",
            },
        )


async def _notify_rapport_ready(record: RapportGenere) -> None:
    from app.services import notification_dispatch_service
    from app.schemas.notifications import NotificationEventType

    notification_dispatch_service.schedule_event(
        event_type=NotificationEventType.RAPPORT_PRET,
        entity_type="rapport",
        entity_id=record.id,
        service_id=record.region_id,
        extra={
            "user_id": record.user_id,
            "task_id": record.task_id,
            "file_name": record.file_name,
        },
    )


async def enqueue_journalier(
    db: AsyncSession,
    user: Utilisateur,
    body: RapportJournalierRequest,
) -> RapportEnqueueResponse:
    from app.workers.tasks.rapports import generer_rapport_task

    _assert_distribution_rapport_role(user)
    report_date = body.report_date or date.today()
    region_id = _resolve_region_id(user, body.region_id)
    roles = _user_role_names(user)
    service_id: int | None = None
    if roles.intersection(_SERVICE_ROLES):
        service_id = user.user_roles[0].scope_service_id
    include_transport = "ADMIN_SAQS" in roles and region_id is None
    task_id = str(uuid.uuid4())
    params_json = json.dumps(
        {
            "date": report_date.isoformat(),
            "region_id": region_id,
            "service_id": service_id,
            "include_transport": include_transport,
        }
    )

    record = await repo.create_rapport(
        db,
        task_id=task_id,
        type_rapport="journalier",
        format=body.output_format,
        user_id=user.id,
        region_id=region_id,
        params_json=params_json,
        expires_at=_expires_at(),
    )
    await db.commit()

    generer_rapport_task.delay(record.id)

    return RapportEnqueueResponse(
        task_id=task_id,
        type_rapport=record.type_rapport,
        statut=record.statut,
        format=record.format,
    )


async def enqueue_mensuel_distribution(
    db: AsyncSession,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None,
    output_format: str,
    top_feeders_limit: int = 10,
) -> RapportEnqueueResponse:
    from app.workers.tasks.rapports import generer_rapport_task

    _assert_distribution_rapport_role(user)
    resolved_region_id = _resolve_region_id(user, region_id)
    clamped_limit = max(1, min(top_feeders_limit, 50))
    task_id = str(uuid.uuid4())
    params_json = json.dumps(
        {
            "annee": annee,
            "mois": mois,
            "region_id": resolved_region_id,
            "top_feeders_limit": clamped_limit,
        }
    )

    record = await repo.create_rapport(
        db,
        task_id=task_id,
        type_rapport="mensuel_distribution",
        format=output_format,
        user_id=user.id,
        region_id=resolved_region_id,
        params_json=params_json,
        expires_at=_expires_at(),
    )
    await db.commit()

    generer_rapport_task.delay(record.id)

    return RapportEnqueueResponse(
        task_id=task_id,
        type_rapport=record.type_rapport,
        statut=record.statut,
        format=record.format,
    )


async def enqueue_mensuel_transport(
    db: AsyncSession,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    output_format: str,
    top_equipements_limit: int = 10,
) -> RapportEnqueueResponse:
    from app.workers.tasks.rapports import generer_rapport_task

    _assert_transport_rapport_role(user)
    clamped_limit = max(1, min(top_equipements_limit, 50))
    task_id = str(uuid.uuid4())
    params_json = json.dumps(
        {
            "annee": annee,
            "mois": mois,
            "top_equipements_limit": clamped_limit,
        }
    )

    record = await repo.create_rapport(
        db,
        task_id=task_id,
        type_rapport="mensuel_transport",
        format=output_format,
        user_id=user.id,
        region_id=None,
        params_json=params_json,
        expires_at=_expires_at(),
    )
    await db.commit()

    generer_rapport_task.delay(record.id)

    return RapportEnqueueResponse(
        task_id=task_id,
        type_rapport=record.type_rapport,
        statut=record.statut,
        format=record.format,
    )


async def enqueue_annuel(
    db: AsyncSession,
    user: Utilisateur,
    *,
    annee: int,
    direction: str,
    region_id: int | None,
    output_format: str,
    top_limit: int = 10,
) -> RapportEnqueueResponse:
    from app.workers.tasks.rapports import generer_rapport_task

    _assert_annuel_direction(user, direction)
    resolved_region_id = None
    if direction in {"distribution", "consolide"}:
        resolved_region_id = _resolve_region_id(user, region_id)
    clamped_limit = max(1, min(top_limit, 50))
    task_id = str(uuid.uuid4())
    params_json = json.dumps(
        {
            "annee": annee,
            "direction": direction,
            "region_id": resolved_region_id,
            "top_limit": clamped_limit,
        }
    )

    record = await repo.create_rapport(
        db,
        task_id=task_id,
        type_rapport="annuel",
        format=output_format,
        user_id=user.id,
        region_id=resolved_region_id,
        params_json=params_json,
        expires_at=_expires_at(),
    )
    await db.commit()

    generer_rapport_task.delay(record.id)

    return RapportEnqueueResponse(
        task_id=task_id,
        type_rapport=record.type_rapport,
        statut=record.statut,
        format=record.format,
    )


async def get_status(
    db: AsyncSession,
    user: Utilisateur,
    task_id: str,
) -> RapportStatusResponse:
    record = await repo.get_by_task_id(db, task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Rapport introuvable",
            },
        )
    _assert_can_access(user, record)
    return _to_status_response(record)


async def resolve_download(
    db: AsyncSession,
    user: Utilisateur,
    task_id: str,
) -> tuple[Path, str, str]:
    record = await repo.get_by_task_id(db, task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Rapport introuvable",
            },
        )
    _assert_can_access(user, record)

    if record.statut != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "error",
                "data": None,
                "error": f"Rapport non disponible (statut={record.statut})",
            },
        )

    _assert_not_expired(record)

    if not record.file_path or not record.file_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Fichier introuvable",
            },
        )

    path = Path(record.file_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Fichier introuvable sur le disque",
            },
        )

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if record.format == "xlsx"
        else "application/pdf"
    )
    return path, record.file_name, media_type


async def execute_generation(db: AsyncSession, rapport_id: int) -> dict[str, str]:
    from redis.asyncio import from_url

    record = await repo.get_by_id(db, rapport_id)
    if record is None:
        raise ValueError(f"Rapport introuvable: id={rapport_id}")

    await repo.update_statut(db, record, statut="started")

    redis = from_url(settings.redis_url, decode_responses=True)
    try:
        params = json.loads(record.params_json or "{}")
        report_date = date.fromisoformat(params["date"]) if params.get("date") else None

        storage_dir = _ensure_storage_dir()
        extension = "xlsx" if record.format == "xlsx" else "pdf"
        file_name = f"{record.type_rapport}_{record.task_id}.{extension}"
        file_path = storage_dir / file_name

        if record.type_rapport == "journalier" and report_date is not None:
            data = await rapport_journalier_service.collect_journalier_data(
                db,
                report_date=report_date,
                region_id=params.get("region_id"),
                service_id=params.get("service_id"),
                include_transport=bool(params.get("include_transport")),
            )
            export_journalier(file_path, format=record.format, data=data)
        elif record.type_rapport == "mensuel_distribution":
            user = await utilisateur_repository.get_by_id(db, record.user_id)
            if user is None:
                raise ValueError(f"Utilisateur introuvable: id={record.user_id}")
            data = await rapport_mensuel_service.collect_mensuel_distribution_data(
                db,
                redis,
                user,
                annee=int(params["annee"]),
                mois=int(params["mois"]),
                region_id=params.get("region_id"),
                top_feeders_limit=int(params.get("top_feeders_limit", 10)),
            )
            export_mensuel_distribution(file_path, format=record.format, data=data)
        elif record.type_rapport == "mensuel_transport":
            data = await rapport_mensuel_transport_service.collect_mensuel_transport_data(
                db,
                annee=int(params["annee"]),
                mois=int(params["mois"]),
                top_equipements_limit=int(params.get("top_equipements_limit", 10)),
            )
            export_mensuel_transport(file_path, format=record.format, data=data)
        elif record.type_rapport == "annuel":
            user = await utilisateur_repository.get_by_id(db, record.user_id)
            if user is None:
                raise ValueError(f"Utilisateur introuvable: id={record.user_id}")
            data = await rapport_annuel_service.collect_annuel_data(
                db,
                redis,
                user,
                annee=int(params["annee"]),
                direction=str(params["direction"]),
                region_id=params.get("region_id"),
                top_limit=int(params.get("top_limit", 10)),
            )
            export_annuel(file_path, format=record.format, data=data)
        else:
            generate_placeholder_file(
                file_path,
                format=record.format,
                type_rapport=record.type_rapport,
                report_date=report_date,
            )

        await repo.update_statut(
            db,
            record,
            statut="success",
            file_path=str(file_path),
            file_name=file_name,
        )
        await _notify_rapport_ready(record)
        return {"task_id": record.task_id, "statut": "success"}
    except Exception as exc:
        await repo.update_statut(
            db,
            record,
            statut="failure",
            error_message=str(exc)[:2000],
        )
        raise
    finally:
        await redis.aclose()
