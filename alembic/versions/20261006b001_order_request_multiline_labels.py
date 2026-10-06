"""allow multiline site and work-date labels on order requests

Revision ID: 20261006b001
Revises: 20261006a001
Create Date: 2026-10-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261006b001"
down_revision: Union[str, None] = "20261006a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("order_request_versions") as batch_op:
        batch_op.alter_column(
            "work_date_label",
            existing_type=sa.String(length=200),
            type_=sa.Text(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "site_name",
            existing_type=sa.String(length=200),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("order_request_versions") as batch_op:
        batch_op.alter_column(
            "work_date_label",
            existing_type=sa.Text(),
            type_=sa.String(length=200),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "site_name",
            existing_type=sa.Text(),
            type_=sa.String(length=200),
            existing_nullable=False,
        )
