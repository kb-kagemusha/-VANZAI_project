"""add_expense_incentive

Revision ID: 004
Revises: 003
Create Date: 2026-01-27 15:00:00.000000

仕様参照: 17章(経費精算), 18章(インセンティブ管理)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_expense_incentive'
down_revision: Union[str, None] = '003_add_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. incentive_rulesテーブル作成 (仕様18.2)
    op.create_table(
        'incentive_rules',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.String(length=26), nullable=True),
        sa.Column('condition_type', sa.String(length=50), nullable=False),
        sa.Column('condition_json', sa.Text(), nullable=False),
        sa.Column('incentive_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('is_for_invoice', sa.Boolean(), nullable=False),
        sa.Column('is_for_payout', sa.Boolean(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incentive_rules_project', 'incentive_rules', ['project_id'])
    op.create_index('ix_incentive_rules_valid', 'incentive_rules', ['valid_from', 'valid_until'])

    # 2. expensesテーブル作成 (仕様17.2)
    op.create_table(
        'expenses',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('project_id', sa.String(length=26), nullable=False),
        sa.Column('worker_id', sa.String(length=26), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('receipt_url', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.String(length=26), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('target_invoice', sa.Boolean(), nullable=False),
        sa.Column('target_payout', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_expenses_date', 'expenses', ['expense_date'])
    op.create_index('ix_expenses_project', 'expenses', ['project_id'])
    op.create_index('ix_expenses_status', 'expenses', ['status'])
    op.create_index('ix_expenses_worker', 'expenses', ['worker_id'])

    # 3. incentivesテーブル作成 (仕様18.3)
    op.create_table(
        'incentives',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('incentive_rule_id', sa.String(length=26), nullable=False),
        sa.Column('worker_id', sa.String(length=26), nullable=False),
        sa.Column('project_id', sa.String(length=26), nullable=True),
        sa.Column('period_key', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.String(length=26), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('target_invoice_id', sa.String(length=26), nullable=True),
        sa.Column('target_payout_id', sa.String(length=26), nullable=True),
        sa.Column('calculation_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['incentive_rule_id'], ['incentive_rules.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['target_invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['target_payout_id'], ['payouts.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incentives_period', 'incentives', ['period_key'])
    op.create_index('ix_incentives_project', 'incentives', ['project_id'])
    op.create_index('ix_incentives_status', 'incentives', ['status'])
    op.create_index('ix_incentives_worker', 'incentives', ['worker_id'])

    # 4. invoice_linesに3カラム追加 (仕様17.3, 18.4)
    # SQLiteではbatch modeを使用
    with op.batch_alter_table('invoice_lines') as batch_op:
        batch_op.add_column(sa.Column('line_type', sa.String(length=20), nullable=False, server_default='actual'))
        batch_op.add_column(sa.Column('expense_id', sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column('incentive_id', sa.String(length=26), nullable=True))
        batch_op.create_foreign_key('fk_invoice_lines_expense', 'expenses', ['expense_id'], ['id'])
        batch_op.create_foreign_key('fk_invoice_lines_incentive', 'incentives', ['incentive_id'], ['id'])
    
    # 5. payout_linesに3カラム追加 (仕様17.3, 18.4)
    with op.batch_alter_table('payout_lines') as batch_op:
        batch_op.add_column(sa.Column('line_type', sa.String(length=20), nullable=False, server_default='actual'))
        batch_op.add_column(sa.Column('expense_id', sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column('incentive_id', sa.String(length=26), nullable=True))
        batch_op.create_foreign_key('fk_payout_lines_expense', 'expenses', ['expense_id'], ['id'])
        batch_op.create_foreign_key('fk_payout_lines_incentive', 'incentives', ['incentive_id'], ['id'])


def downgrade() -> None:
    # payout_linesカラム削除（SQLite batch mode）
    with op.batch_alter_table('payout_lines') as batch_op:
        batch_op.drop_constraint('fk_payout_lines_incentive', type_='foreignkey')
        batch_op.drop_constraint('fk_payout_lines_expense', type_='foreignkey')
        batch_op.drop_column('incentive_id')
        batch_op.drop_column('expense_id')
        batch_op.drop_column('line_type')
    
    # invoice_linesカラム削除（SQLite batch mode）
    with op.batch_alter_table('invoice_lines') as batch_op:
        batch_op.drop_constraint('fk_invoice_lines_incentive', type_='foreignkey')
        batch_op.drop_constraint('fk_invoice_lines_expense', type_='foreignkey')
        batch_op.drop_column('incentive_id')
        batch_op.drop_column('expense_id')
        batch_op.drop_column('line_type')
    
    # テーブル削除
    op.drop_index('ix_incentives_worker', table_name='incentives')
    op.drop_index('ix_incentives_status', table_name='incentives')
    op.drop_index('ix_incentives_project', table_name='incentives')
    op.drop_index('ix_incentives_period', table_name='incentives')
    op.drop_table('incentives')
    
    op.drop_index('ix_expenses_worker', table_name='expenses')
    op.drop_index('ix_expenses_status', table_name='expenses')
    op.drop_index('ix_expenses_project', table_name='expenses')
    op.drop_index('ix_expenses_date', table_name='expenses')
    op.drop_table('expenses')
    
    op.drop_index('ix_incentive_rules_valid', table_name='incentive_rules')
    op.drop_index('ix_incentive_rules_project', table_name='incentive_rules')
    op.drop_table('incentive_rules')
    op.drop_index('ix_incentive_rules_project', table_name='incentive_rules')
    op.drop_table('incentive_rules')
