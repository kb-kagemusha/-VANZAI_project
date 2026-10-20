"""Add administrator-defined login role names (DESIGN_SPEC section 5)."""
from alembic import op
import sqlalchemy as sa

revision = "20261020a003"
down_revision = "20261020a002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("role_access_policies", sa.Column("display_name", sa.String(100), nullable=True))
    op.create_index("uq_role_access_policy_display_name", "role_access_policies", ["display_name"], unique=True)


def downgrade():
    op.drop_index("uq_role_access_policy_display_name", table_name="role_access_policies")
    op.drop_column("role_access_policies", "display_name")
