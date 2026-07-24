"""phase1 revision D payout recipients

Revision ID: 20260408d001
Revises: 20260408c001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408d001"
down_revision: Union[str, None] = "20260408c001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payouts", sa.Column("recipient_type", sa.String(length=20), nullable=True))
    op.add_column("payouts", sa.Column("recipient_id", sa.String(length=26), nullable=True))
    op.add_column("payouts", sa.Column("payee_name_snapshot", sa.String(length=200), nullable=True))
    op.add_column("payouts", sa.Column("bank_account_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("payouts", sa.Column("tax_treatment_snapshot_json", sa.JSON(), nullable=True))

    op.create_index("ix_payouts_recipient_period", "payouts", ["recipient_type", "recipient_id", "period_key"], unique=False)

    bind = op.get_bind()

    payouts = sa.table(
        "payouts",
        sa.column("id", sa.String(length=26)),
        sa.column("worker_id", sa.String(length=26)),
        sa.column("supplier_id", sa.String(length=26)),
        sa.column("recipient_type", sa.String(length=20)),
        sa.column("recipient_id", sa.String(length=26)),
        sa.column("payee_name_snapshot", sa.String(length=200)),
    )
    workers = sa.table(
        "workers",
        sa.column("id", sa.String(length=26)),
        sa.column("name", sa.String(length=100)),
    )
    suppliers = sa.table(
        "suppliers",
        sa.column("id", sa.String(length=26)),
        sa.column("name", sa.String(length=100)),
    )

    worker_rows = bind.execute(sa.select(workers.c.id, workers.c.name)).mappings().all()
    supplier_rows = bind.execute(sa.select(suppliers.c.id, suppliers.c.name)).mappings().all()
    worker_names = {row["id"]: row["name"] for row in worker_rows}
    supplier_names = {row["id"]: row["name"] for row in supplier_rows}

    existing_payouts = bind.execute(
        sa.select(payouts.c.id, payouts.c.worker_id, payouts.c.supplier_id)
    ).mappings().all()

    for row in existing_payouts:
        values: dict[str, str | None] = {
            "recipient_type": None,
            "recipient_id": None,
            "payee_name_snapshot": None,
        }
        if row["worker_id"]:
            values["recipient_type"] = "worker"
            values["recipient_id"] = row["worker_id"]
            values["payee_name_snapshot"] = worker_names.get(row["worker_id"])
        elif row["supplier_id"]:
            values["recipient_type"] = "supplier"
            values["recipient_id"] = row["supplier_id"]
            values["payee_name_snapshot"] = supplier_names.get(row["supplier_id"])

        bind.execute(
            sa.update(payouts)
            .where(payouts.c.id == row["id"])
            .values(**values)
        )


def downgrade() -> None:
    op.drop_index("ix_payouts_recipient_period", table_name="payouts")
    op.drop_column("payouts", "tax_treatment_snapshot_json")
    op.drop_column("payouts", "bank_account_snapshot_json")
    op.drop_column("payouts", "payee_name_snapshot")
    op.drop_column("payouts", "recipient_id")
    op.drop_column("payouts", "recipient_type")
