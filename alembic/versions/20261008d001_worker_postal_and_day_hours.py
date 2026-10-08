"""稼働者の郵便番号と曜日ごとの稼働時間

Revision ID: 20261008d001
Revises: 20261008c001
Create Date: 2026-10-08 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008d001"
down_revision: Union[str, None] = "20261008c001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("postal_code", sa.String(length=8), nullable=True))
    op.add_column("workers", sa.Column("available_day_hours", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("workers", "available_day_hours")
    op.drop_column("workers", "postal_code")
