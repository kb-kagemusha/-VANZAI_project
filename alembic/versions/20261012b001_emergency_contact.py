"""Emergency contact name and relationship; preserve legacy request requirements."""
from alembic import op
import sqlalchemy as sa

revision = "20261012b001"
down_revision = "20261012a001"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("workers", "worker_registration_request_details"):
        op.add_column(table, sa.Column("emergency_contact_name", sa.String(200), nullable=True))
        op.add_column(table, sa.Column("emergency_contact_relationship", sa.String(50), nullable=True))
    op.add_column("worker_registration_request_details", sa.Column("line_registration_form_version", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("worker_registration_request_details", "line_registration_form_version")
    for table in ("worker_registration_request_details", "workers"):
        op.drop_column(table, "emergency_contact_relationship")
        op.drop_column(table, "emergency_contact_name")
