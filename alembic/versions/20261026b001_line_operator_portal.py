"""Operator LINE portal sessions and personal menu lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "20261026b001"
down_revision = "20261026a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("line_operator_sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("link_id", sa.String(26), sa.ForeignKey("line_staff_links.id"), nullable=False),
        sa.Column("staff_id", sa.String(26), sa.ForeignKey("vanzai_staff.id"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_operator_session_hash"))
    op.create_table("line_operator_menu_releases",
        sa.Column("id", sa.String(26), primary_key=True), sa.Column("menus", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False))
    op.create_table("line_operator_menu_states",
        sa.Column("line_user_id", sa.String(64), primary_key=True),
        sa.Column("applied_menu_id", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','applied','failed')", name="ck_operator_menu_status"))


def downgrade():
    for table in ("line_operator_sessions", "line_operator_menu_releases", "line_operator_menu_states"):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError("LINE運営の利用・公開履歴があるため削除できません")
    for table in ("line_operator_sessions", "line_operator_menu_releases", "line_operator_menu_states"):
        op.drop_table(table)
