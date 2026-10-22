"""Per-recipient absence dates on order request drafts (DEC-065, A0)."""
from alembic import op
import sqlalchemy as sa

revision = "20261022a001"
down_revision = "20261020a003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("order_request_versions", sa.Column("draft_recipient_absences", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("order_request_versions", "draft_recipient_absences")
