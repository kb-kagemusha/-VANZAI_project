"""LINE稼働者登録の3表と申請詳細の生年月日。

DEC-033。審査値の複製表は作らない。本番への適用と入口の有効化はこのファイル追加では行わない。

Revision ID: 20261011a001
Revises: 20261008d001
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261011a001"
down_revision: Union[str, None] = "20261008d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "worker_registration_request_details",
        sa.Column("birth_date", sa.Date(), nullable=True),
    )

    op.create_table(
        "line_registration_sessions",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("line_user_id", sa.String(length=64), nullable=False),
        sa.Column("line_worker_link_id", sa.String(length=26), nullable=True),
        sa.Column("worker_id", sa.String(length=26), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_line_registration_sessions_token_hash"),
        sa.CheckConstraint("length(line_user_id) > 0", name="ck_line_registration_sessions_subject"),
        sa.ForeignKeyConstraint(["line_worker_link_id"], ["line_worker_links.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_line_registration_sessions_token_hash"),
    )
    op.create_index(
        "ix_line_registration_sessions_expires_at",
        "line_registration_sessions",
        ["expires_at"],
    )

    op.create_table(
        "line_registration_contexts",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), nullable=False),
        sa.Column("line_user_id", sa.String(length=64), nullable=False),
        sa.Column("line_worker_link_id", sa.String(length=26), nullable=True),
        sa.Column("worker_id", sa.String(length=26), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(line_user_id) > 0", name="ck_line_registration_contexts_subject"),
        sa.ForeignKeyConstraint(["line_worker_link_id"], ["line_worker_links.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["registration_requests.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_line_registration_contexts_request_id"),
    )
    op.create_index(
        "uq_line_registration_contexts_open_subject",
        "line_registration_contexts",
        ["line_user_id"],
        unique=True,
        postgresql_where=sa.text("is_open"),
    )

    op.create_table(
        "line_registration_submit_keys",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("line_user_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=26), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(line_user_id) > 0", name="ck_line_registration_submit_keys_subject"),
        sa.CheckConstraint("length(idempotency_key) > 0", name="ck_line_registration_submit_keys_idempotency"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_line_registration_submit_keys_content_hash"),
        sa.ForeignKeyConstraint(["request_id"], ["registration_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "line_user_id",
            "idempotency_key",
            name="uq_line_registration_submit_keys_subject_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("line_registration_submit_keys")
    op.drop_index(
        "uq_line_registration_contexts_open_subject",
        table_name="line_registration_contexts",
    )
    op.drop_table("line_registration_contexts")
    op.drop_index(
        "ix_line_registration_sessions_expires_at",
        table_name="line_registration_sessions",
    )
    op.drop_table("line_registration_sessions")
    op.drop_column("worker_registration_request_details", "birth_date")
