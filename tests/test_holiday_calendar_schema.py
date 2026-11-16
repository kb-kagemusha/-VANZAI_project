"""The calendar schema must migrate without touching existing order data."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_calendar_migration_keeps_existing_data_and_rejects_duplicate_days(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(26) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE existing_orders (id INTEGER PRIMARY KEY, value TEXT)"))
        connection.execute(text("INSERT INTO existing_orders VALUES (1, 'unchanged')"))
        path = Path(__file__).parents[1] / "alembic/versions/20261116a001_holiday_calendar.py"
        spec = importlib.util.spec_from_file_location("holiday_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert "holiday_calendar_days" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT value FROM existing_orders")).scalar_one() == "unchanged"
        connection.execute(text("INSERT INTO holiday_calendar_days VALUES ('2027-01-01', 1, '元日', 'manual', 1, 'actor', '2026-11-16')"))
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO holiday_calendar_days VALUES ('2027-01-01', 0, '', 'manual', 2, 'actor', '2026-11-16')"))
