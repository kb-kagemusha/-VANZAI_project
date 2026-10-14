"""Optional additional nearest stations, retaining the original station columns.

DEC-050 / DESIGN_SPEC_v0.3 section 6.1.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261015a001"
down_revision = "20261014a001"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("workers", "worker_registration_request_details"):
        op.add_column(table, sa.Column("additional_stations", sa.JSON(), nullable=True))


def downgrade():
    for table in ("worker_registration_request_details", "workers"):
        op.drop_column(table, "additional_stations")
