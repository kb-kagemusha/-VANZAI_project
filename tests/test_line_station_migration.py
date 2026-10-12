"""The added nullable fields preserve rows and enforce the walking range."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import IntegrityError
import pytest


def test_station_upgrade_preserves_old_rows_and_checks_new_values():
    file = Path(__file__).resolve().parents[1] / "alembic/versions/20261012a001_line_station_fields.py"
    spec = importlib.util.spec_from_file_location("station_migration", file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE worker_registration_request_details (id VARCHAR(26) PRIMARY KEY, request_id VARCHAR(26))"))
        connection.execute(text("INSERT INTO worker_registration_request_details (id, request_id) VALUES ('old-row', 'old-request')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        old = connection.execute(text("SELECT nearest_station, station_walk_minutes FROM worker_registration_request_details WHERE id='old-row'")).one()
        assert tuple(old) == (None, None)
        connection.execute(text("UPDATE worker_registration_request_details SET nearest_station='test-station', station_walk_minutes=0 WHERE id='old-row'"))
        with connection.begin_nested():
            with pytest.raises(IntegrityError):
                connection.execute(text("UPDATE worker_registration_request_details SET station_walk_minutes=301 WHERE id='old-row'"))
        assert connection.execute(text("SELECT request_id FROM worker_registration_request_details WHERE id='old-row'")).scalar_one() == "old-request"
    engine.dispose()
