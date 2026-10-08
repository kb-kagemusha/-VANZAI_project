"""新人タグが外れる日を稼働者に持たせる

Revision ID: 20261008b001
Revises: 20261008a001
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008b001"
down_revision: Union[str, None] = "20261008a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("newcomer_until", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE workers
        SET newcomer_until = ((CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date + INTERVAL '3 months')::date
        WHERE COALESCE(tags::text, '') LIKE '%"newcomer"%'
        """
    )


def downgrade() -> None:
    op.drop_column("workers", "newcomer_until")
