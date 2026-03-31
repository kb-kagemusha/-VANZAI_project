"""Add target_invoice_id and target_payout_id to expenses

Revision ID: 005
Revises: 004
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_expense_invoice_payout_ids'
down_revision = 'ff166af0ba6d'
branch_labels = None
depends_on = None


def upgrade():
    """Add target_invoice_id and target_payout_id to expenses table"""
    
    # SQLiteでは直接ALTER TABLEでFKを追加できないため、
    # バッチモードを使用
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_invoice_id', sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column('target_payout_id', sa.String(length=26), nullable=True))
        batch_op.create_foreign_key('fk_expenses_target_invoice_id', 'invoices', ['target_invoice_id'], ['id'])
        batch_op.create_foreign_key('fk_expenses_target_payout_id', 'payouts', ['target_payout_id'], ['id'])


def downgrade():
    """Remove target_invoice_id and target_payout_id from expenses table"""
    
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint('fk_expenses_target_invoice_id', type_='foreignkey')
        batch_op.drop_constraint('fk_expenses_target_payout_id', type_='foreignkey')
        batch_op.drop_column('target_invoice_id')
        batch_op.drop_column('target_payout_id')
