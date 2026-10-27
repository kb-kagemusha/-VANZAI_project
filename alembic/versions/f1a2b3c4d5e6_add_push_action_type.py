"""add push_action_type to staff_notices

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-04-04

プッシュ通知のアクションボタン種別を保存するカラムを追加する。
- null / "none": アクションなし（デフォルト）
- "ok_ng": "OKです、了承します" / "NGです" ボタン
- "confirm": "確認しました" ボタン（ok として記録）
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "staff_notices",
        sa.Column("push_action_type", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staff_notices", "push_action_type")
