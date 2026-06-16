"""Repository — suivi des rapports générés."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rapports import RapportGenere


async def create_rapport(
    db: AsyncSession,
    *,
    task_id: str,
    type_rapport: str,
    format: str,
    user_id: int,
    region_id: int | None,
    params_json: str | None,
    expires_at: datetime,
) -> RapportGenere:
    record = RapportGenere(
        task_id=task_id,
        type_rapport=type_rapport,
        format=format,
        statut="pending",
        user_id=user_id,
        region_id=region_id,
        params_json=params_json,
        expires_at=expires_at,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(record)
    await db.flush()
    return record


async def get_by_task_id(db: AsyncSession, task_id: str) -> RapportGenere | None:
    result = await db.execute(select(RapportGenere).where(RapportGenere.task_id == task_id))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, rapport_id: int) -> RapportGenere | None:
    result = await db.execute(select(RapportGenere).where(RapportGenere.id == rapport_id))
    return result.scalar_one_or_none()


async def update_statut(
    db: AsyncSession,
    record: RapportGenere,
    *,
    statut: str,
    file_path: str | None = None,
    file_name: str | None = None,
    error_message: str | None = None,
) -> RapportGenere:
    record.statut = statut
    record.updated_at = datetime.now()
    if file_path is not None:
        record.file_path = file_path
    if file_name is not None:
        record.file_name = file_name
    if error_message is not None:
        record.error_message = error_message
    await db.flush()
    return record
