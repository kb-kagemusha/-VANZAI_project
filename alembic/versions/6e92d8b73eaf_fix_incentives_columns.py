"""fix_incentives_columns

Revision ID: 6e92d8b73eaf
Revises: 094c172c0943
Create Date: 2026-01-28 13:53:00.128722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e92d8b73eaf'
down_revision: Union[str, None] = '094c172c0943'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # incentivesテーブル修正
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        # reasonカラム追加（rejection_reasonからコピー）
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
        # notesカラム追加
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
    
    # データコピー
    op.execute("UPDATE incentives SET reason = rejection_reason")
    
    # 旧rejection_reasonカラム削除
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        batch_op.drop_column('rejection_reason')


def downgrade() -> None:
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
        batch_op.drop_column('notes')
    
    op.execute("UPDATE incentives SET rejection_reason = reason")
    
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        batch_op.drop_column('reason')
