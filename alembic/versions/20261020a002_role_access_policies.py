"""Persist administrator-managed role permissions (DESIGN_SPEC section 5)."""
from alembic import op
import sqlalchemy as sa

revision = "20261020a002"
down_revision = "20261020a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "role_access_policies",
        sa.Column("role", sa.String(20), primary_key=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("role_access_policies")
