from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    # Alembic's ini (`alembic.ini`) may include a [logging] section pointing
    # to the real logging config file (for example `alembic/logging.ini`).
    # Passing `alembic.ini` directly to logging.config.fileConfig raises a
    # KeyError: 'formatters' because `alembic.ini` doesn't contain logging
    # formatter definitions. Read the `config_file` option and load that file
    # instead when present.
    import configparser
    import os

    try:
        parser = configparser.ConfigParser()
        parser.read(config.config_file_name)
        if parser.has_section("logging") and parser.has_option("logging", "config_file"):
            logging_path = parser.get("logging", "config_file")
            # Resolve relative path relative to the alembic.ini location
            base_dir = os.path.dirname(config.config_file_name)
            if not os.path.isabs(logging_path):
                logging_path = os.path.join(base_dir, logging_path)
            fileConfig(logging_path)
        else:
            # Fallback: load the alembic.ini itself (backwards compatibility)
            fileConfig(config.config_file_name)
    except Exception:
        # If anything goes wrong loading the separate logging config,
        # fallback to loading the alembic.ini to preserve previous behavior.
        fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url(),
    )

    async def run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
