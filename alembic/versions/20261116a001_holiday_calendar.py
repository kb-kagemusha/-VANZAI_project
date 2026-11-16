"""Create the shared holiday calendar without changing existing order snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20261116a001"
down_revision = "20261028a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "holiday_calendar_days",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("is_holiday", sa.Boolean(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_holiday_calendar_revision"),
    )


def downgrade():
    raise RuntimeError("Keep the shared holiday history; use a forward migration")
