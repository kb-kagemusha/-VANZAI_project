"""Persist LINE registration receipt notifications without backfilling old requests."""
from alembic import op
import sqlalchemy as sa

revision = "20261013b001"
down_revision = "20261013a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "line_registration_receipts",
        sa.Column("request_id", sa.String(26), sa.ForeignKey("registration_requests.id"), primary_key=True),
        sa.Column("retry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("message_text", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_line_receipt_status"),
        sa.CheckConstraint("attempt_count >= 0 AND attempt_count <= 5", name="ck_line_receipt_attempts"),
        sa.CheckConstraint("status <> 'sent' OR sent_at IS NOT NULL", name="ck_line_receipt_sent"),
    )
    op.create_index("ix_line_receipt_due", "line_registration_receipts", ["status", "next_attempt_at"])


def downgrade():
    op.drop_index("ix_line_receipt_due", table_name="line_registration_receipts")
    op.drop_table("line_registration_receipts")
