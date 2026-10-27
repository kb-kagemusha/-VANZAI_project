"""Preserve test history and link one new formal draft, without answers or deliveries."""
from alembic import op
import sqlalchemy as sa
revision="20261028a001"
down_revision="20261027f001"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("order_formalizations",
        sa.Column("source_document_id",sa.String(26),sa.ForeignKey("order_request_documents.id"),primary_key=True),
        sa.Column("source_version_id",sa.String(26),sa.ForeignKey("order_request_versions.id"),nullable=False),
        sa.Column("formal_document_id",sa.String(26),sa.ForeignKey("order_request_documents.id"),nullable=False,unique=True),
        sa.Column("capacity_snapshot",sa.JSON(),nullable=False),
        sa.Column("rate_reference",sa.JSON(),nullable=True),
        sa.Column("created_by",sa.String(26),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    raise RuntimeError("Keep formalization history; use a forward migration")
