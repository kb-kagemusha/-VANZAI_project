"""Attendance notes for payment review (DEC-090)."""
from alembic import op
import sqlalchemy as sa

revision = "20261024a001"
down_revision = "20261023f001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "attendance_notes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("schedule_entry_id", sa.String(26), sa.ForeignKey("worker_schedule_entries.id"), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("series_id", sa.String(26), sa.ForeignKey("order_request_series.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("worker_name", sa.String(200), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("cause", sa.String(20), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reported_by", sa.String(200), nullable=False),
        sa.Column("actor_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('late', 'cancel')", name="ck_attendance_notes_kind"),
        sa.CheckConstraint("cause IN ('personal', 'weather', 'other')", name="ck_attendance_notes_cause"),
        sa.CheckConstraint("(kind = 'late' AND late_minutes IS NOT NULL AND late_minutes BETWEEN 1 AND 10080) OR (kind = 'cancel' AND late_minutes IS NULL)", name="ck_attendance_notes_minutes"),
        sa.CheckConstraint("length(trim(reason)) > 0 AND length(trim(reported_by)) > 0", name="ck_attendance_notes_reason"),
        sa.CheckConstraint("(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL AND length(trim(void_reason)) > 0)", name="ck_attendance_notes_void"),
    )
    op.create_index("ix_attendance_notes_worker_date", "attendance_notes", ["worker_id", "work_date"])
    op.create_index("ix_attendance_notes_series_date", "attendance_notes", ["series_id", "work_date"])
    op.create_index("uq_attendance_notes_active", "attendance_notes", ["series_id", "worker_id", "work_date", "kind"], unique=True,
                    sqlite_where=sa.text("voided_at IS NULL"), postgresql_where=sa.text("voided_at IS NULL"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM attendance_notes LIMIT 1")).first():
        raise RuntimeError("遅刻・キャンセルの記録があるため削除できません")
    op.drop_table("attendance_notes")
