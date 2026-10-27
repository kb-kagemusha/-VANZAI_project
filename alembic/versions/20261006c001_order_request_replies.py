"""order request accept, decline reason, and one reminder

Revision ID: 20261006c001
Revises: 20261006b001
Create Date: 2026-10-06 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261006c001"
down_revision: Union[str, None] = "20261006b001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order_request_deliveries", sa.Column("decline_reason", sa.Text(), nullable=True))
    op.add_column(
        "order_request_deliveries",
        sa.Column("ack_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("ck_order_request_deliveries_ack", "order_request_deliveries", type_="check")
    op.create_check_constraint(
        "ck_order_request_deliveries_ack",
        "order_request_deliveries",
        "ack_status IN ('unacked', 'acked', 'decline_pending', 'declined')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE order_request_deliveries SET ack_status = 'unacked' "
        "WHERE ack_status IN ('decline_pending', 'declined')"
    )
    op.drop_constraint("ck_order_request_deliveries_ack", "order_request_deliveries", type_="check")
    op.create_check_constraint(
        "ck_order_request_deliveries_ack",
        "order_request_deliveries",
        "ack_status IN ('unacked', 'acked')",
    )
    op.drop_column("order_request_deliveries", "ack_reminded_at")
    op.drop_column("order_request_deliveries", "decline_reason")
