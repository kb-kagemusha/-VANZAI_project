"""add_performance_indexes

Revision ID: ff166af0ba6d
Revises: 004_add_expense_incentive
Create Date: 2026-01-27

パフォーマンス最適化のためのインデックス追加
推奨タスク: DBインデックス追加
仕様参照: AGENTS.md「破綻を防ぐ必須ガード」

追加するインデックス:
1. actuals(period_key, status) - 請求書/支払明細生成時の高速検索
2. assignments(worker_id, status) - 稼働者別集計の高速化
3. audit_logs(action, created_at) - 監査ログ検索API高速化
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff166af0ba6d'
down_revision: Union[str, None] = '004_add_expense_incentive'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """インデックス追加"""
    # actuals テーブル: period_key + status の複合インデックス
    # 用途: generate_invoice/generate_payout での高速フィルタ
    op.create_index(
        'ix_actuals_period_key_status',
        'actuals',
        ['period_key', 'status'],
        unique=False
    )
    
    # assignments テーブル: worker_id + status の複合インデックス
    # 用途: 稼働者別集計、支払明細生成時の高速検索
    op.create_index(
        'ix_assignments_worker_id_status',
        'assignments',
        ['worker_id', 'status'],
        unique=False
    )
    
    # audit_logs テーブル: action + created_at の複合インデックス
    # 用途: search_audit_logs() での高速フィルタ
    op.create_index(
        'ix_audit_logs_action_created_at',
        'audit_logs',
        ['action', 'created_at'],
        unique=False
    )
    
    # audit_logs テーブル: actor 単独インデックス
    # 用途: 実行者別の監査ログ検索
    op.create_index(
        'ix_audit_logs_actor',
        'audit_logs',
        ['actor'],
        unique=False
    )


def downgrade() -> None:
    """インデックス削除（ロールバック）"""
    op.drop_index('ix_audit_logs_actor', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_created_at', table_name='audit_logs')
    op.drop_index('ix_assignments_worker_id_status', table_name='assignments')
    op.drop_index('ix_actuals_period_key_status', table_name='actuals')
