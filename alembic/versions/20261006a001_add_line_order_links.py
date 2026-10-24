"""add LINE worker links and order request send attempts

Revision ID: 20261006a001
Revises: 20261002a001
Create Date: 2026-10-06 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261006a001"
down_revision: Union[str, None] = "20261002a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "line_worker_links",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("worker_id", sa.String(length=26), nullable=False),
        sa.Column("line_user_id", sa.String(length=64), nullable=False),
        sa.Column("line_display_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_line_worker_links_status"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_line_worker_links_worker", "line_worker_links", ["worker_id"])
    op.create_index("ix_line_worker_links_line_user", "line_worker_links", ["line_user_id"])
    op.create_index(
        "uq_line_worker_links_active_worker",
        "line_worker_links",
        ["worker_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_line_worker_links_active_line_user",
        "line_worker_links",
        ["line_user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "line_link_codes",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("worker_id", sa.String(length=26), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("ix_line_link_codes_worker", "line_link_codes", ["worker_id"])

    op.create_table(
        "line_webhook_events",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )

    op.create_table(
        "order_request_send_attempts",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("delivery_id", sa.String(length=26), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("line_request_id", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.String(length=300), nullable=True),
        sa.Column("actor_user_id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result IN ('accepted', 'failed', 'unknown')",
            name="ck_order_request_send_attempts_result",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delivery_id"], ["order_request_deliveries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_request_send_attempts_delivery",
        "order_request_send_attempts",
        ["delivery_id"],
    )

    op.create_table(
        "order_request_file_tokens",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("delivery_id", sa.String(length=26), nullable=False),
        sa.Column("token", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["delivery_id"], ["order_request_deliveries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        "ix_order_request_file_tokens_delivery",
        "order_request_file_tokens",
        ["delivery_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_request_file_tokens_delivery", table_name="order_request_file_tokens")
    op.drop_table("order_request_file_tokens")
    op.drop_index("ix_order_request_send_attempts_delivery", table_name="order_request_send_attempts")
    op.drop_table("order_request_send_attempts")
    op.drop_table("line_webhook_events")
    op.drop_index("ix_line_link_codes_worker", table_name="line_link_codes")
    op.drop_table("line_link_codes")
    op.drop_index("uq_line_worker_links_active_line_user", table_name="line_worker_links")
    op.drop_index("uq_line_worker_links_active_worker", table_name="line_worker_links")
    op.drop_index("ix_line_worker_links_line_user", table_name="line_worker_links")
    op.drop_index("ix_line_worker_links_worker", table_name="line_worker_links")
    op.drop_table("line_worker_links")
