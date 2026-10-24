"""Allow directly authored templates without a synthetic order (DEC-077)."""
from alembic import op
import sqlalchemy as sa

revision = "20261023e001"
down_revision = "20261023d001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("order_request_templates") as batch:
        batch.alter_column("source_version_id", existing_type=sa.String(26), nullable=True)


def downgrade():
    # Refuse to destroy or fabricate provenance for directly authored templates.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM order_request_templates WHERE source_version_id IS NULL")).scalar():
        raise RuntimeError("直接作成したテンプレートがあるため、安全に旧制約へ戻せません")
    with op.batch_alter_table("order_request_templates") as batch:
        batch.alter_column("source_version_id", existing_type=sa.String(26), nullable=False)
