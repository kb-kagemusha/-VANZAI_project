"""add playing manager fee config to vanzai staff

Revision ID: 20260408g001
Revises: 20260408f001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408g001"
down_revision: Union[str, None] = "20260408f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("vanzai_staff", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("playing_manager_fee_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("playing_manager_fixed_fee", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vanzai_staff", recreate="auto") as batch_op:
        batch_op.drop_column("playing_manager_fixed_fee")
        batch_op.drop_column("playing_manager_fee_type")