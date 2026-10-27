"""Expiring test notification switch and isolated test history (DEC-128)."""
from alembic import op
import sqlalchemy as sa

revision = "20261027c001"
down_revision = "20261027b001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("wake_test_notification_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_wake_test_setting_singleton"),
        sa.CheckConstraint("(enabled_from IS NULL AND enabled_until IS NULL) OR (enabled_from IS NOT NULL AND enabled_until IS NOT NULL AND enabled_until > enabled_from)", name="ck_wake_test_setting_window"))
    op.execute(sa.text("INSERT INTO wake_test_notification_settings (id, revision) VALUES (1, 0)"))
    for table in ("wake_monitor_sends", "wake_contact_logs"):
        op.add_column(table, sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
        # Preserve the original rows; annotate only provably test-only worker days.
        day_column = "work_date" if table == "wake_monitor_sends" else "contact_date"
        op.execute(sa.text(f"""UPDATE {table} SET is_test = true
            WHERE EXISTS (SELECT 1 FROM worker_schedule_entries e WHERE e.worker_id = {table}.worker_id AND e.work_date = {table}.{day_column} AND e.is_test = true)
            AND NOT EXISTS (SELECT 1 FROM worker_schedule_entries e WHERE e.worker_id = {table}.worker_id AND e.work_date = {table}.{day_column} AND e.is_test = false)"""))
    with op.batch_alter_table("wake_monitor_sends") as batch:
        batch.drop_constraint("uq_wake_monitor_sends_key", type_="unique")
        batch.create_unique_constraint("uq_wake_monitor_sends_key", ["worker_id", "work_date", "kind", "round", "recipient", "is_test"])


def downgrade():
    # Removing the context would merge formal/test keys and discard audit meaning.
    raise RuntimeError("Keep notification history; use a forward migration to roll back.")
