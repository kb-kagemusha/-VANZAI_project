"""add_worker_p_shirt_count_license_type

Revision ID: 0d6b395ae7ba
Revises: 6a7ac0000bee
Create Date: 2026-04-02 22:33:21.738291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d6b395ae7ba'
down_revision: Union[str, None] = '6a7ac0000bee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workers', sa.Column('p_shirt_count', sa.Integer(), nullable=True))
    op.add_column('workers', sa.Column('license_type', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('workers', 'license_type')
    op.drop_column('workers', 'p_shirt_count')

