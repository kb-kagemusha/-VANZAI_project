"""add payout pdf object key

Revision ID: 8b71d2f4c6a9
Revises: 1f4b8c9d2e3a
Create Date: 2026-03-31 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b71d2f4c6a9'
down_revision: Union[str, None] = '1f4b8c9d2e3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payouts', sa.Column('pdf_object_key', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('payouts', 'pdf_object_key')
