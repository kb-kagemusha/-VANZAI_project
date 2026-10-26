"""Additive schema migration keeps existing rows and refuses destructive rollback."""
import importlib.util
from pathlib import Path
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from src.models.base import Base


def test_operator_migration_preserves_existing_tables_and_guards_history():
    path = Path("alembic/versions/20261026b001_line_operator_portal.py")
    spec = importlib.util.spec_from_file_location("operator_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    names = {"line_operator_sessions", "line_operator_menu_releases", "line_operator_menu_states"}
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name not in names])
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE migration_sentinel (value INTEGER)"))
        connection.execute(text("INSERT INTO migration_sentinel VALUES (42)"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert names <= set(inspect(connection).get_table_names())
            assert connection.execute(text("SELECT value FROM migration_sentinel")).scalar() == 42
            module.downgrade()
            assert not names & set(inspect(connection).get_table_names())
            module.upgrade()
            connection.execute(text("INSERT INTO line_operator_menu_releases (id,menus,active,created_at,created_by) VALUES ('test','{}',0,'2026-10-26','test')"))
            with pytest.raises(RuntimeError): module.downgrade()
            assert connection.execute(text("SELECT value FROM migration_sentinel")).scalar() == 42
