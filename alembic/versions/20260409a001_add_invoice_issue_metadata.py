"""add invoice issuance metadata

Revision ID: 20260409a001
Revises: 20260408g001
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260409a001"
down_revision: Union[str, None] = "20260408g001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("invoices", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("document_type", sa.String(length=20), nullable=False, server_default="invoice"))
        batch_op.add_column(sa.Column("invoice_subject", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("addressee_company_name", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("addressee_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("addressee_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("addressee_address", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fixed_office_fee_amount", sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("invoices", recreate="auto") as batch_op:
        batch_op.drop_column("fixed_office_fee_amount")
        batch_op.drop_column("addressee_address")
        batch_op.drop_column("addressee_email")
        batch_op.drop_column("addressee_name")
        batch_op.drop_column("addressee_company_name")
        batch_op.drop_column("invoice_subject")
        batch_op.drop_column("document_type")