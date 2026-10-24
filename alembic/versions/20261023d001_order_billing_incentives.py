"""Append incentive components without rewriting historical amounts/PDFs (DEC-075)."""
from alembic import op
import sqlalchemy as sa

revision = "20261023d001"
down_revision = "20261023c001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("order_billing_amounts") as batch:
        batch.add_column(sa.Column("incentive_amount", sa.Numeric(15, 2), nullable=True))
        batch.create_check_constraint("ck_order_billing_incentive_amount", "incentive_amount IS NULL OR incentive_amount >= 0")
    with op.batch_alter_table("order_billing_invoice_lines") as batch:
        batch.add_column(sa.Column("incentive_amount", sa.Numeric(15, 2), nullable=True))
        batch.add_column(sa.Column("incentive_note", sa.Text(), nullable=True))
        batch.create_check_constraint("ck_order_billing_line_incentive", "incentive_amount IS NULL OR (incentive_amount >= 0 AND incentive_amount <= amount)")


def downgrade():
    with op.batch_alter_table("order_billing_invoice_lines") as batch:
        batch.drop_constraint("ck_order_billing_line_incentive", type_="check")
        batch.drop_column("incentive_note")
        batch.drop_column("incentive_amount")
    with op.batch_alter_table("order_billing_amounts") as batch:
        batch.drop_constraint("ck_order_billing_incentive_amount", type_="check")
        batch.drop_column("incentive_amount")
