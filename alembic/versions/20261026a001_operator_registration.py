"""Operator registration details for invitation and approval."""
from alembic import op
import sqlalchemy as sa
revision = "20261026a001"
down_revision = "20261024c001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("operator_registration_details",
        sa.Column("request_id", sa.String(26), sa.ForeignKey("registration_requests.id"), primary_key=True),
        sa.Column("name", sa.String(100), nullable=True), sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("line_user_id", sa.String(64), nullable=True), sa.Column("line_display_name", sa.String(200), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("uq_operator_registration_open_line", "operator_registration_details", ["line_user_id"], unique=True,
        sqlite_where=sa.text("is_open = 1 AND line_user_id IS NOT NULL"), postgresql_where=sa.text("is_open AND line_user_id IS NOT NULL"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM operator_registration_details")).scalar():
        raise RuntimeError("運営スタッフの招待・申請履歴があるため削除できません")
    op.drop_table("operator_registration_details")
