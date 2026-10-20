"""Extend existing operator master and add separate verified LINE identities."""
from alembic import op
import sqlalchemy as sa

revision = "20261013c001"
down_revision = "20261013b001"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("can_drive", sa.Boolean()), ("smoking_area_ok", sa.Boolean()),
        ("emergency_contact_name", sa.String(200)), ("emergency_contact_phone", sa.String(20)),
        ("emergency_contact_relationship", sa.String(50)), ("management_roles", sa.JSON()),
    ):
        op.add_column("vanzai_staff", sa.Column(name, kind, nullable=True))
    op.add_column("vanzai_staff", sa.Column("profile_revision", sa.Integer(), server_default="1", nullable=False))
    op.create_check_constraint("ck_vanzai_staff_profile_revision", "vanzai_staff", "profile_revision > 0")
    op.create_table(
        "line_staff_links",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("staff_id", sa.String(26), sa.ForeignKey("vanzai_staff.id"), nullable=False),
        sa.Column("line_user_id", sa.String(64), nullable=False),
        sa.Column("line_display_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_line_staff_links_status"),
    )
    for name, column in (("uq_line_staff_active_staff", "staff_id"), ("uq_line_staff_active_line_user", "line_user_id")):
        op.create_index(name, "line_staff_links", [column], unique=True, postgresql_where=sa.text("status = 'active'"), sqlite_where=sa.text("status = 'active'"))
    op.create_table(
        "line_staff_link_codes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("staff_id", sa.String(26), sa.ForeignKey("vanzai_staff.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_line_staff_codes_staff", "line_staff_link_codes", ["staff_id"])


def downgrade():
    op.drop_table("line_staff_link_codes")
    op.drop_table("line_staff_links")
    op.drop_constraint("ck_vanzai_staff_profile_revision", "vanzai_staff", type_="check")
    for name in ("profile_revision", "management_roles", "emergency_contact_relationship", "emergency_contact_phone", "emergency_contact_name", "smoking_area_ok", "can_drive"):
        op.drop_column("vanzai_staff", name)
