import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def test_receipt_migration_keeps_old_requests_and_does_not_queue_them():
    file = Path(__file__).resolve().parents[1] / "alembic/versions/20261013b001_line_registration_receipts.py"
    spec = importlib.util.spec_from_file_location("receipt_migration", file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE registration_requests (id VARCHAR(26) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO registration_requests (id) VALUES ('existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT id FROM registration_requests")).scalar_one() == "existing"
        assert connection.execute(text("SELECT count(*) FROM line_registration_receipts")).scalar_one() == 0
        with connection.begin_nested(), pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO line_registration_receipts (request_id,retry_key,message_text,status,attempt_count,next_attempt_at) VALUES ('existing','11111111-1111-4111-8111-111111111111','receipt','sent',0,CURRENT_TIMESTAMP)"))
    engine.dispose()
