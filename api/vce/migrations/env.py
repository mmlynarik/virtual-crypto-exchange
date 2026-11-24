import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from vce.orm import mapper_registry
from vce.settings import BACKEND_DB_URL

config = context.config

# Logging config comes from alembic.ini when the alembic CLI is used; vce-migrate sets up its own
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing vce.orm imports every domain's tables, so this MetaData holds the whole schema
target_metadata = mapper_registry.metadata


def get_url() -> str:
    # sqlalchemy.url is left empty in alembic.ini; the app's settings are the single source of truth.
    # It can still be overridden, e.g. `alembic -x ...` setups or tests calling config.set_main_option.
    return config.get_main_option("sqlalchemy.url") or BACKEND_DB_URL


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
