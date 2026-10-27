"""Daily customer pricing and frozen daily lines, without changing old amounts or invoices."""
from alembic import op
import sqlalchemy as sa
revision="20261027f001"
down_revision="20261027e001"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("order_billing_rate_settings",
        sa.Column("version_id",sa.String(26),sa.ForeignKey("order_request_versions.id"),primary_key=True),
        sa.Column("project_id",sa.String(26),sa.ForeignKey("projects.id"),nullable=False),
        sa.Column("base_rate",sa.Numeric(15,2),nullable=False),
        sa.Column("weekday_rates",sa.JSON(),nullable=False),
        sa.Column("revision",sa.Integer(),nullable=False),
        sa.Column("updated_by",sa.String(26),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("base_rate >= 0 AND revision > 0",name="ck_order_billing_daily_rate"))
    op.create_table("order_billing_daily_lines",
        sa.Column("amount_id",sa.String(26),sa.ForeignKey("order_billing_amounts.id"),primary_key=True),
        sa.Column("work_date",sa.Date(),primary_key=True),
        sa.Column("quantity",sa.Integer(),nullable=False),
        sa.Column("unit_price",sa.Numeric(15,2),nullable=False),
        sa.Column("adjustment",sa.Numeric(15,2),nullable=False),
        sa.Column("adjustment_reason",sa.Text(),nullable=False),
        sa.Column("subtotal",sa.Numeric(18,2),nullable=False),
        sa.Column("source_snapshot",sa.JSON(),nullable=False),
        sa.CheckConstraint("quantity >= 0 AND unit_price >= 0 AND subtotal >= 0",name="ck_order_billing_daily_values"),
        sa.CheckConstraint("round(subtotal,2) = round(quantity * unit_price + adjustment,2)",name="ck_order_billing_daily_total"))
    op.create_table("order_billing_actual_claims",
        sa.Column("project_id",sa.String(26),sa.ForeignKey("projects.id"),primary_key=True),
        sa.Column("work_date",sa.Date(),primary_key=True),
        sa.Column("series_id",sa.String(26),sa.ForeignKey("order_request_series.id"),nullable=False),
        sa.Column("active",sa.Boolean(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.add_column("order_billing_invoice_lines",sa.Column("pricing_snapshot",sa.JSON(),nullable=True))


def downgrade():
    raise RuntimeError("Keep billing snapshots and claims; use a forward migration")
