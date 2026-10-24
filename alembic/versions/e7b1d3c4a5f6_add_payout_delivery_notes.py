"""add payout delivery notes

Revision ID: e7b1d3c4a5f6
Revises: c4a8d0b9e12f
Create Date: 2026-04-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b1d3c4a5f6'
down_revision: Union[str, None] = 'c4a8d0b9e12f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payout_deliveries', sa.Column('delivery_note', sa.Text(), nullable=True))
    op.add_column('payout_deliveries', sa.Column('internal_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('payout_deliveries', 'internal_note')
    op.drop_column('payout_deliveries', 'delivery_note')