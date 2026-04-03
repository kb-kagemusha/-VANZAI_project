"""add push_subscriptions table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-03

Web Push (VAPID) のサブスクリプション情報を保存するテーブルを追加する。
- endpoint: ブラウザから受け取るPush URL
- p256dh / auth: 暗号化に使用するブラウザ公開鍵
- worker_id: 稼働者と紐付け（NULLは管理者等）
- user_agent_hash: 端末識別（同一ユーザーの複数端末対応）
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=True, index=True),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("p256dh", sa.Text, nullable=False),
        sa.Column("auth", sa.Text, nullable=False),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # エンドポイント+worker_id が一意（同じ端末セットが重複登録されない）
    op.create_index(
        "ix_push_subscriptions_endpoint_worker",
        "push_subscriptions",
        ["endpoint", "worker_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
