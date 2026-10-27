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


def test_wake_claim_migration_adds_order_read_to_saved_site_manager_policy_only():
    path = Path("alembic/versions/20261027a001_operator_wake_claims_and_files.py")
    spec = importlib.util.spec_from_file_location("operator_wake_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name != "line_operator_file_tokens"])
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO role_access_policies (role, display_name, permissions, created_at, updated_at) VALUES ('site_manager', NULL, '["project_read","wake_status_read"]', '2026-10-27', '2026-10-27')"""))
        connection.execute(text("""INSERT INTO role_access_policies (role, display_name, permissions, created_at, updated_at) VALUES ('accounting', NULL, '["invoice_read"]', '2026-10-27', '2026-10-27')"""))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "line_operator_file_tokens" in set(inspect(connection).get_table_names())
            rows = dict(connection.execute(text("SELECT role, permissions FROM role_access_policies")).all())
            import json
            assert json.loads(rows["site_manager"]) == ["order_read", "project_read", "wake_status_read"]
            assert json.loads(rows["accounting"]) == ["invoice_read"]
            module.downgrade()
            assert "line_operator_file_tokens" not in set(inspect(connection).get_table_names())


def test_wake_monitor_migration_adds_alert_permission_to_saved_operator_roles():
    path = Path("alembic/versions/20261027b001_wake_monitor_sends.py")
    spec = importlib.util.spec_from_file_location("wake_monitor_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name != "wake_monitor_sends"])
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO role_access_policies (role, display_name, permissions, created_at, updated_at) VALUES ('site_manager', NULL, '["order_read","wake_status_read"]', '2026-10-27', '2026-10-27')"""))
        connection.execute(text("""INSERT INTO role_access_policies (role, display_name, permissions, created_at, updated_at) VALUES ('accounting', NULL, '["invoice_read"]', '2026-10-27', '2026-10-27')"""))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            import json
            rows = dict(connection.execute(text("SELECT role, permissions FROM role_access_policies")).all())
            assert json.loads(rows["site_manager"]) == ["order_read", "wake_alert_receive", "wake_status_read"]
            assert json.loads(rows["accounting"]) == ["invoice_read"]
            assert "wake_monitor_sends" in set(inspect(connection).get_table_names())
            module.downgrade()
            assert "wake_monitor_sends" not in set(inspect(connection).get_table_names())
