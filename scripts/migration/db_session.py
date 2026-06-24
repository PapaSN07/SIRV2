"""Session SQLAlchemy synchrone pour l'ETL vers dbo."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from scripts.migration.config import get_settings


def _sync_database_url(async_url: str) -> str:
    url = async_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url and "?" in url:
        url += "&TrustServerCertificate=yes"
    elif "TrustServerCertificate" not in url:
        url += "?TrustServerCertificate=yes"
    return url


@contextmanager
def get_session() -> Generator[Session, None, None]:
    settings = get_settings()
    url = _sync_database_url(settings.database_url)
    engine = create_engine(url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()
