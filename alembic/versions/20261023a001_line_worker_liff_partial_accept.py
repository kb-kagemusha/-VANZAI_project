"""Worker LIFF sessions, submit keys, and per-version partial acceptance (Roadmap ①, A1+ §3).

既存の依頼書は allow_partial_accept = false（動きは変わらない）。
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023a001"
down_revision = "20261022a002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "order_request_versions",
        sa.Column("allow_partial_accept", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "line_worker_sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("line_user_id", sa.String(64), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_line_worker_sessions_token_hash"),
    )
    op.create_index("ix_line_worker_sessions_worker", "line_worker_sessions", ["worker_id"])
    op.create_table(
        "line_worker_submit_keys",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("target_id", sa.String(26), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("worker_id", "idempotency_key", name="uq_line_worker_submit_key"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_line_worker_submit_keys_hash"),
        sa.CheckConstraint("action IN ('pick_dates')", name="ck_line_worker_submit_keys_action"),
    )


def downgrade():
    op.drop_table("line_worker_submit_keys")
    op.drop_index("ix_line_worker_sessions_worker", table_name="line_worker_sessions")
    op.drop_table("line_worker_sessions")
    op.drop_column("order_request_versions", "allow_partial_accept")
