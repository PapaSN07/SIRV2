"""Repository — audit log."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.audit import AuditLog
from app.schemas.common import PaginatedResponse
from app.utils.pagination import paginate


async def list_audit_logs(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    table_name: str | None = None,
    user_id: int | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse:
    query = (
        select(AuditLog)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
    )
    if table_name:
        query = query.where(AuditLog.table_name == table_name)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if date_debut is not None:
        query = query.where(AuditLog.created_at >= date_debut)
    if date_fin is not None:
        query = query.where(AuditLog.created_at <= date_fin)
    return await paginate(db, query, page, page_size, scalar_type=AuditLog)
