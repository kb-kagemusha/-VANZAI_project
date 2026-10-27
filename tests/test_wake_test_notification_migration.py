"""Exercise the upgrade against old records without erasing their contents."""
import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
import pytest


def test_upgrade_preserves_history_and_separates_context_keys():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for statement in [
            "CREATE TABLE workers (id VARCHAR(26) PRIMARY KEY)",
            "CREATE TABLE worker_schedule_entries (worker_id VARCHAR(26), work_date DATE, is_test BOOLEAN)",
            "CREATE TABLE wake_contact_logs (id VARCHAR(26) PRIMARY KEY, worker_id VARCHAR(26), contact_date DATE, note TEXT)",
            "CREATE TABLE wake_monitor_sends (id VARCHAR(26) PRIMARY KEY, worker_id VARCHAR(26), work_date DATE, kind VARCHAR(30), round INTEGER, recipient VARCHAR(64), status VARCHAR(20), created_at DATETIME, CONSTRAINT uq_wake_monitor_sends_key UNIQUE(worker_id, work_date, kind, round, recipient))",
            "INSERT INTO workers VALUES ('formal'), ('test'), ('mixed')",
            "INSERT INTO worker_schedule_entries VALUES ('formal','2026-10-27',false),('test','2026-10-27',true),('mixed','2026-10-27',true),('mixed','2026-10-27',false)",
            "INSERT INTO wake_contact_logs VALUES ('contact','test','2026-10-27','original note')",
            "INSERT INTO wake_monitor_sends VALUES ('old-test','test','2026-10-27','operator_alert',0,'Uoperator','sent','2026-10-27 00:00:00'),('old-mixed','mixed','2026-10-27','operator_alert',0,'Uoperator','sent','2026-10-27 00:00:00')",
        ]:
            connection.execute(sa.text(statement))
        spec = importlib.util.spec_from_file_location("wake_setting_upgrade", Path("alembic/versions/20261027c001_wake_test_notification_settings.py"))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert connection.execute(sa.text("SELECT enabled_from, enabled_until, revision FROM wake_test_notification_settings")).one() == (None, None, 0)
        assert connection.execute(sa.text("SELECT note,is_test FROM wake_contact_logs")).one() == ("original note", 1)
        assert dict(connection.execute(sa.text("SELECT id,is_test FROM wake_monitor_sends")).all()) == {"old-test": 1, "old-mixed": 0}
        connection.execute(sa.text("INSERT INTO wake_monitor_sends SELECT 'formal-context',worker_id,work_date,kind,round,recipient,status,created_at,false FROM wake_monitor_sends WHERE id='old-test'"))
        assert connection.execute(sa.text("SELECT COUNT(*) FROM wake_monitor_sends")).scalar() == 3
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.text("INSERT INTO wake_test_notification_settings (id,revision) VALUES (2,0)"))
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.text("INSERT INTO wake_monitor_sends SELECT 'duplicate',worker_id,work_date,kind,round,recipient,status,created_at,is_test FROM wake_monitor_sends WHERE id='old-test'"))
