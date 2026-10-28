from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.db_url import url_sql_server

# Schéma SQL Server explicite — évite la création dans le schéma par défaut du login
metadata = MetaData(schema="dbo")

engine = create_async_engine(
    url_sql_server(settings.database_url),
    echo=settings.environment == "development",
    pool_pre_ping=True,
    # Le serveur SQL distant / pare-feu coupe les connexions inactives (TCP 10054)
    pool_recycle=280,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    metadata = metadata


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
