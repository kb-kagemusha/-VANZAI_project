"""Record Cabinet Office holiday CSV imports without changing issued order snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20261116b001"
down_revision = "20261116a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "holiday_csv_imports",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("coverage_start", sa.Date(), nullable=False),
        sa.Column("coverage_end", sa.Date(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("added_days", sa.JSON(), nullable=False),
        sa.Column("removed_days", sa.JSON(), nullable=False),
        sa.Column("renamed_days", sa.JSON(), nullable=False),
        sa.Column("official_days", sa.JSON(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Keep holiday CSV import history; use a forward migration")
