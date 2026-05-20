import asyncio
import importlib.util
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.infra.database import Base, DATABASE_URL
from app.domain import models as _models  # noqa: F401

target_metadata = Base.metadata


def _driver_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _resolve_database_url() -> tuple[str, bool]:
    url = make_url(DATABASE_URL)

    if _driver_available("psycopg2"):
        return url.render_as_string(hide_password=False), False

    if _driver_available("asyncpg"):
        return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False), True

    raise ModuleNotFoundError(
        "No PostgreSQL driver is available for Alembic. Install psycopg2-binary or asyncpg."
    )


def _run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    database_url, use_async_engine = _resolve_database_url()
    config.set_main_option("sqlalchemy.url", database_url)

    if use_async_engine:
        asyncio.run(run_async_migrations(database_url))
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _run_migrations(connection)


async def run_async_migrations(database_url: str) -> None:
    connectable = create_async_engine(database_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
