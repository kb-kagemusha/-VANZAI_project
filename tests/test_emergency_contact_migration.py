"""New contact columns preserve legacy phone/kana and old request requirements."""
import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_preserves_legacy_fields():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261012b001_emergency_contact.py"
    spec = importlib.util.spec_from_file_location("emergency_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("workers", "worker_registration_request_details"):
            connection.execute(text(f"CREATE TABLE {table} (id VARCHAR(26) PRIMARY KEY, emergency_contact_phone VARCHAR(20), emergency_contact_name_kana VARCHAR(200))"))
            connection.execute(text(f"INSERT INTO {table} VALUES ('old', '09000002222', 'ヤマダハナコ')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        for table in ("workers", "worker_registration_request_details"):
            row = connection.execute(text(f"SELECT emergency_contact_phone, emergency_contact_name_kana, emergency_contact_name, emergency_contact_relationship FROM {table}")).one()
            assert tuple(row) == ("09000002222", "ヤマダハナコ", None, None)
        assert connection.execute(text("SELECT line_registration_form_version FROM worker_registration_request_details")).scalar_one() is None
    engine.dispose()
