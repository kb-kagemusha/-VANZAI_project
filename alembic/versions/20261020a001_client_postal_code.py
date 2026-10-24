"""Client postal code, preserving existing addresses (DEC-051)."""
from alembic import op
import sqlalchemy as sa

revision = "20261020a001"
down_revision = "20261015a001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("postal_code", sa.String(7), nullable=True))


def downgrade():
    op.drop_column("clients", "postal_code")
