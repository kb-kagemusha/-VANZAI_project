"""add notice response to staff_notice_reads

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03

staff_notice_reads テーブルに response カラムと responded_at カラムを追加する。
- response: "ok" | "ng" | NULL（未回答）
- responded_at: 回答日時

スタッフが通知に対して「OK、わかりました」「NGです」と返答できるようにする。
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "staff_notice_reads",
        sa.Column("response", sa.String(10), nullable=True),
    )
    op.add_column(
        "staff_notice_reads",
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("staff_notice_reads", "responded_at")
    op.drop_column("staff_notice_reads", "response")
