"""Daily operator staffing decisions and durable result messages."""
from alembic import op
import sqlalchemy as sa

revision = "20261027d001"
down_revision = "20261027c001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("order_request_versions", sa.Column("requires_operator_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("worker_schedule_entries") as batch:
        batch.drop_constraint("ck_worker_schedule_entry_status", type_="check")
        batch.create_check_constraint("ck_worker_schedule_entry_status", "status IN ('active','changing','pending','superseded','cancelled')")
    op.create_table("order_staffing_rounds",
        sa.Column("version_id", sa.String(26), sa.ForeignKey("order_request_versions.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("order_staffing_limits",
        sa.Column("version_id", sa.String(26), sa.ForeignKey("order_staffing_rounds.version_id"), primary_key=True),
        sa.Column("work_date", sa.Date(), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="ck_staffing_capacity"))
    op.create_table("order_staffing_decisions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("version_id", sa.String(26), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.String(100), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id", "work_date"], ["order_staffing_limits.version_id", "order_staffing_limits.work_date"]),
        sa.UniqueConstraint("version_id", "worker_id", "work_date", name="uq_staffing_worker_day"),
        sa.CheckConstraint("status IN ('confirmed','not_selected','vacant')", name="ck_staffing_decision_status"))
    op.create_table("order_staffing_notices",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("version_id", sa.String(26), sa.ForeignKey("order_staffing_rounds.version_id"), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("version_id", "worker_id", "work_date", "kind", name="uq_staffing_notice"),
        sa.CheckConstraint("kind IN ('confirmed','closed')", name="ck_staffing_notice_kind"),
        sa.CheckConstraint("status IN ('pending','sent','failed','cancelled','skipped')", name="ck_staffing_notice_status"))


def downgrade():
    raise RuntimeError("Preserve operator decisions and send history; use a forward migration")
