import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

_ALEMBIC_DIR = Path(__file__).resolve().parent
if str(_ALEMBIC_DIR) not in sys.path:
    sys.path.insert(0, str(_ALEMBIC_DIR))
from dbo_patch import patch_alembic_operations  # noqa: E402
from schema_config import DB_SCHEMA  # noqa: E402
from app.core.config import settings
from app.core.database import Base

# Import all models so Alembic detects them
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
patch_alembic_operations(DB_SCHEMA)


def _configure_context(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        version_table_schema=DB_SCHEMA,
        include_schemas=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    _configure_context(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _configure_context(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
