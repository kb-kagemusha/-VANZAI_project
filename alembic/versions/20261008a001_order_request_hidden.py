"""hide order requests from the list without deleting rows

Revision ID: 20261008a001
Revises: 20261006e001
Create Date: 2026-10-08 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008a001"
down_revision: Union[str, None] = "20261006e001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_request_documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "order_request_documents",
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
    )
    op.create_index(
        "ix_order_request_documents_deleted_at",
        "order_request_documents",
        ["deleted_at"],
    )
    op.create_foreign_key(
        "fk_order_request_documents_deleted_by_user_id",
        "order_request_documents",
        "users",
        ["deleted_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_order_request_documents_deleted_by_user_id",
        "order_request_documents",
        type_="foreignkey",
    )
    op.drop_index("ix_order_request_documents_deleted_at", table_name="order_request_documents")
    op.drop_column("order_request_documents", "deleted_by_user_id")
    op.drop_column("order_request_documents", "deleted_at")
