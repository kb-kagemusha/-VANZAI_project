"""add linked worker to vanzai staff

Revision ID: 20260408f001
Revises: 20260408e001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408f001"
down_revision: Union[str, None] = "20260408e001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("vanzai_staff", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("linked_worker_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_vanzai_staff_linked_worker_id_workers",
            "workers",
            ["linked_worker_id"],
            ["id"],
        )
        batch_op.create_index("ix_vanzai_staff_linked_worker_id", ["linked_worker_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("vanzai_staff", recreate="auto") as batch_op:
        batch_op.drop_index("ix_vanzai_staff_linked_worker_id")
        batch_op.drop_constraint("fk_vanzai_staff_linked_worker_id_workers", type_="foreignkey")
        batch_op.drop_column("linked_worker_id")