"""Repository — workflow opérationnel interruptions distribution."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.interruption_workflow import InterruptionWorkflowStep
from app.models.interruptions import PosteInterruption


async def get_workflow_step(
    db: AsyncSession,
    interruption_id: int,
) -> InterruptionWorkflowStep | None:
    result = await db.execute(
        select(InterruptionWorkflowStep)
        .options(
            joinedload(InterruptionWorkflowStep.troncon),
            joinedload(InterruptionWorkflowStep.troncon_sig),
        )
        .where(InterruptionWorkflowStep.interruption_id == interruption_id)
    )
    return result.scalar_one_or_none()


async def upsert_workflow_step(
    db: AsyncSession,
    interruption_id: int,
    values: dict,
) -> InterruptionWorkflowStep:
    existing = await get_workflow_step(db, interruption_id)
    if existing is None:
        step = InterruptionWorkflowStep(interruption_id=interruption_id, **values)
        db.add(step)
        await db.flush()
        await db.refresh(step, attribute_names=["troncon", "troncon_sig"])
        return step

    for key, value in values.items():
        setattr(existing, key, value)
    await db.flush()
    await db.refresh(existing, attribute_names=["troncon", "troncon_sig"])
    return existing


async def count_clients_workflow(
    db: AsyncSession,
    interruption_id: int,
) -> tuple[int, int | None]:
    """Retourne (nombre_postes, somme_clients_touches)."""
    result = await db.execute(
        select(
            func.count(PosteInterruption.id),
            func.coalesce(func.sum(PosteInterruption.nombre_clients_touches), 0),
        ).where(PosteInterruption.interruption_id == interruption_id)
    )
    row = result.one()
    postes = int(row[0])
    clients_sum = int(row[1]) if row[1] is not None else None
    return postes, clients_sum if postes > 0 else None
