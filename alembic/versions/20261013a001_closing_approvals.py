"""Authenticated closing approvals."""
from alembic import op
import sqlalchemy as sa

revision = "20261013a001"
down_revision = "20261012b001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("closing_approval_requests",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("period_key", sa.String(6), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_status", sa.String(20), nullable=False),
        sa.Column("expected_release_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('hard_close','soft_release','hard_release')", name="ck_closing_approval_action"),
        sa.CheckConstraint("status IN ('pending','approved','expired','rejected')", name="ck_closing_approval_status"),
        sa.CheckConstraint("approved_by IS NULL OR approved_by <> requested_by", name="ck_closing_approval_two_people"),
        sa.CheckConstraint("status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)", name="ck_closing_approval_complete"))
    op.create_index("uq_closing_approval_pending", "closing_approval_requests", ["project_id","period_key","action"],
                    unique=True, postgresql_where=sa.text("status = 'pending'"), sqlite_where=sa.text("status = 'pending'"))


def downgrade():
    op.drop_table("closing_approval_requests")
