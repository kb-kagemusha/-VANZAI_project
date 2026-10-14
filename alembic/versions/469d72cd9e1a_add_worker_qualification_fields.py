"""add_worker_qualification_fields

Revision ID: 469d72cd9e1a
Revises: b1c2d3e4f5a6
Create Date: 2026-04-02 20:20:17.022162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '469d72cd9e1a'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workers', sa.Column('smoking_area_ok', sa.Boolean(), nullable=True))
    op.add_column('workers', sa.Column('has_p_shirt', sa.Boolean(), nullable=True))
    op.add_column('workers', sa.Column('has_best', sa.Boolean(), nullable=True))
    op.add_column('workers', sa.Column('stores_training_done', sa.Boolean(), nullable=True))
    op.add_column('workers', sa.Column('pioneer_training_done', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('workers', 'pioneer_training_done')
    op.drop_column('workers', 'stores_training_done')
    op.drop_column('workers', 'has_best')
    op.drop_column('workers', 'has_p_shirt')
    op.drop_column('workers', 'smoking_area_ok')
