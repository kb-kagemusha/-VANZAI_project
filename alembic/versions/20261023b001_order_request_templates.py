"""Named reusable order request snapshots (DEC-072)."""
from alembic import op
import sqlalchemy as sa

revision = "20261023b001"
down_revision = "20261023a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_request_templates",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_version_id", sa.String(26), sa.ForeignKey("order_request_versions.id"), nullable=False),
        sa.Column("source_document_number", sa.String(40), nullable=False),
        sa.Column("created_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_order_request_templates_name"),
    )
    op.create_index("uq_order_request_templates_active_name", "order_request_templates", ["name_key"], unique=True,
                    postgresql_where=sa.text("archived_at IS NULL"), sqlite_where=sa.text("archived_at IS NULL"))
    op.create_index("ix_order_request_templates_archived", "order_request_templates", ["archived_at"])


def downgrade():
    op.drop_index("ix_order_request_templates_archived", table_name="order_request_templates")
    op.drop_index("uq_order_request_templates_active_name", table_name="order_request_templates")
    op.drop_table("order_request_templates")
