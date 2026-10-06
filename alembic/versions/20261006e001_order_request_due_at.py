"""add the clock time for an order-request reminder

Revision ID: 20261006e001
Revises: 20261006d001
Create Date: 2026-10-06 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261006e001"
down_revision: Union[str, None] = "20261006d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_request_versions",
        sa.Column("follow_up_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE order_request_versions
        SET follow_up_due_at = (follow_up_due_on + time '21:00') AT TIME ZONE 'Asia/Tokyo'
        WHERE follow_up_due_on IS NOT NULL
          AND follow_up_due_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("order_request_versions", "follow_up_due_at")
