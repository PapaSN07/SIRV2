from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.schemas.common import PaginatedResponse

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def clamp_page_size(page_size: int) -> int:
    """Clamp page_size to [1, MAX_PAGE_SIZE]."""
    return max(1, min(page_size, MAX_PAGE_SIZE))


async def paginate(
    db: AsyncSession,
    query: Select[Any],
    page: int,
    page_size: int,
    *,
    scalar_type: type[T],
    max_page_size: int = MAX_PAGE_SIZE,
) -> PaginatedResponse[T]:
    """Execute a paginated query and return a PaginatedResponse.

    Args:
        db: Active async database session.
        query: Base SELECT statement (no offset/limit/order applied yet).
        page: 1-based page number.
        page_size: Number of items per page (capped at max_page_size).
        max_page_size: Upper bound for this query (defaults to MAX_PAGE_SIZE).
        scalar_type: The SQLAlchemy model or Pydantic type used for type narrowing.

    Returns:
        PaginatedResponse with items, total, page, and page_size.

    Example:
        result = await paginate(
            db,
            select(Interruption).where(Interruption.statut == "en_cours"),
            page=1,
            page_size=20,
            scalar_type=Interruption,
        )
    """
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    offset = (page - 1) * page_size

    # Count total rows using the same base query
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total: int = total_result.scalar_one()

    # Fetch the page
    paginated_query = query.offset(offset).limit(page_size)
    rows_result = await db.execute(paginated_query)
    items: list[T] = list(rows_result.scalars().all())

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
