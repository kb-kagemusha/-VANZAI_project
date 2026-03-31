"""rename_receipt_url_to_receipt_file_key

Revision ID: 094c172c0943
Revises: 005_add_expense_invoice_payout_ids
Create Date: 2026-01-28 13:51:49.758909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '094c172c0943'
down_revision: Union[str, None] = '005_add_expense_invoice_payout_ids'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLiteではALTER COLUMN RENAME未対応のため、列を追加して移行
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('receipt_file_key', sa.String(length=512), nullable=True))
    
    # データコピー
    op.execute("UPDATE expenses SET receipt_file_key = receipt_url")
    
    # 旧列削除
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('receipt_url')
    
    # reject_reasonカラム名修正（rejection_reason → reject_reason）
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reject_reason', sa.Text(), nullable=True))
    
    op.execute("UPDATE expenses SET reject_reason = rejection_reason")
    
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('rejection_reason')
    
    # notesカラム追加
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('notes')
        batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
    
    op.execute("UPDATE expenses SET rejection_reason = reject_reason")
    
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('reject_reason')
        batch_op.add_column(sa.Column('receipt_url', sa.String(length=512), nullable=True))
    
    op.execute("UPDATE expenses SET receipt_url = receipt_file_key")
    
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('receipt_file_key')
