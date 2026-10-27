"""Repository — workflow opérationnel interruptions distribution (étapes chaînées)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.interruption_workflow import ETAPE_TRONCONNEMENT, EtapeWorkflow, Workflow
from app.models.interruptions import PosteInterruption


async def list_etapes(db: AsyncSession) -> list[EtapeWorkflow]:
    result = await db.execute(select(EtapeWorkflow).order_by(EtapeWorkflow.ordre))
    return list(result.scalars().all())


async def get_etape(db: AsyncSession, etape_id: int) -> EtapeWorkflow | None:
    result = await db.execute(select(EtapeWorkflow).where(EtapeWorkflow.id == etape_id))
    return result.scalar_one_or_none()


async def list_workflows(db: AsyncSession, interruption_id: int) -> list[Workflow]:
    result = await db.execute(
        select(Workflow)
        .options(joinedload(Workflow.troncon), joinedload(Workflow.troncon_sig))
        .where(Workflow.interruption_id == interruption_id)
    )
    return list(result.scalars().unique().all())


async def get_workflow(
    db: AsyncSession,
    interruption_id: int,
    etape_id: int,
) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(
            Workflow.interruption_id == interruption_id,
            Workflow.etape_workflow_id == etape_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_workflow(
    db: AsyncSession,
    interruption_id: int,
    etape_id: int,
    values: dict,
) -> Workflow:
    existing = await get_workflow(db, interruption_id, etape_id)
    if existing is None:
        row = Workflow(interruption_id=interruption_id, etape_workflow_id=etape_id, **values)
        db.add(row)
        await db.flush()
        return row

    for key, value in values.items():
        setattr(existing, key, value)
    await db.flush()
    return existing


async def get_troncon_sig_id_for_interruption(
    db: AsyncSession,
    interruption_id: int,
) -> int | None:
    result = await db.execute(
        select(Workflow.troncon_sig_id)
        .join(EtapeWorkflow, EtapeWorkflow.id == Workflow.etape_workflow_id)
        .where(
            Workflow.interruption_id == interruption_id,
            EtapeWorkflow.code == ETAPE_TRONCONNEMENT,
        )
    )
    return result.scalar_one_or_none()


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


async def synchroniser_remise(db: AsyncSession, interruption_id: int, date_remise) -> None:
    """L'étape « Remise » prend la date de clôture : une seule date de réalimentation."""
    from app.models.interruption_workflow import ETAPE_REMISE

    etape = (
        await db.execute(select(EtapeWorkflow).where(EtapeWorkflow.code == ETAPE_REMISE))
    ).scalar_one_or_none()
    if etape is None:
        return
    existing = await get_workflow(db, interruption_id, etape.id)
    values = {"date_fin": date_remise}
    if existing is None or existing.date_debut is None:
        values["date_debut"] = date_remise
    await upsert_workflow(db, interruption_id, etape.id, values)
