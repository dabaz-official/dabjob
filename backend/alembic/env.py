"""Alembic environment.

The URL comes from ``Settings`` unless a caller sets it explicitly, which is
what the schema test does to migrate a throwaway database.

``render_as_batch`` is on because SQLite cannot ``ALTER TABLE``; without it
every future column change becomes a hand-written table rebuild.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from dabjob.config import Settings
from dabjob.migration_support import include_object
from dabjob.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    return configured if configured else Settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
