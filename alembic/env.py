"""Alembic migration environment."""
import os
from logging.config import fileConfig

from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, engine_from_config, pool

from alembic import context
from alembic.ddl.impl import DefaultImpl

from src.alembic_support import widen_existing_version_num

# Import models for autogenerate
from src.models.base import Base
from src.models import master, transaction  # noqa: F401
import src.models.order_request  # noqa: F401
import src.models.order_billing  # noqa: F401
import src.models.line_order  # noqa: F401
import src.models.line_daily  # noqa: F401
import src.models.staffing_replacement
import src.models.order_staffing  # noqa: F401
import src.models.closing_approval
import src.models.line_registration  # noqa: F401
import src.models.operator_registration  # noqa: F401
import src.models.line_operator  # noqa: F401

config = context.config

database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _wide_version_table(self, *, version_table, version_table_schema, version_table_pk, **kw):
    """改訂IDが32文字を超えるため、版管理表は128文字で作る。"""
    version_table_impl = Table(
        version_table,
        MetaData(),
        Column("version_num", String(128), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        version_table_impl.append_constraint(
            PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
        )
    return version_table_impl


DefaultImpl.version_table_impl = _wide_version_table


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        widen_existing_version_num(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
