"""add_user_display_name

Revision ID: 6a7ac0000bee
Revises: 469d72cd9e1a
Create Date: 2026-04-02 21:00:50.819746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a7ac0000bee'
down_revision: Union[str, None] = '469d72cd9e1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'display_name')
