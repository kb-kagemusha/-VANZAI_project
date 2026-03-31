"""make_incentives_calcjson_nullable

Revision ID: c2d8f4b9a7a1
Revises: b7d3c2a1f1e9
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d8f4b9a7a1'
down_revision: Union[str, None] = 'b7d3c2a1f1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        batch_op.alter_column(
            'calculation_json',
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('incentives', schema=None) as batch_op:
        batch_op.alter_column(
            'calculation_json',
            existing_type=sa.Text(),
            nullable=False,
        )
