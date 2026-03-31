"""add_incentive_rule_notes

Revision ID: b7d3c2a1f1e9
Revises: 6e92d8b73eaf
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3c2a1f1e9'
down_revision: Union[str, None] = '6e92d8b73eaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incentive_rules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('incentive_rules', schema=None) as batch_op:
        batch_op.drop_column('notes')
