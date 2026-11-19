"""Double-header bundles: link two order request documents without changing existing rows (DEC-148)."""
from alembic import op
import sqlalchemy as sa

revision = "20261120a001"
down_revision = "20261116b001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_request_bundles",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("travel_minutes", sa.Integer(), nullable=False),
        sa.Column("gap_ack_reason", sa.Text(), nullable=True),
        sa.Column("gap_ack_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("gap_ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('formal', 'test')", name="ck_order_request_bundles_kind"),
        sa.CheckConstraint("travel_minutes >= 0 AND travel_minutes <= 720", name="ck_order_request_bundles_travel"),
    )
    op.create_table(
        "order_request_bundle_legs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("bundle_id", sa.String(26), sa.ForeignKey("order_request_bundles.id"), nullable=False),
        sa.Column("leg_no", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(26), sa.ForeignKey("order_request_documents.id"), nullable=False, unique=True),
        sa.Column("series_id", sa.String(26), sa.ForeignKey("order_request_series.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bundle_id", "leg_no", name="uq_order_request_bundle_leg_no"),
        sa.CheckConstraint("leg_no IN (1, 2)", name="ck_order_request_bundle_leg_no"),
    )
    op.create_table(
        "order_request_bundle_deliveries",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("bundle_id", sa.String(26), sa.ForeignKey("order_request_bundles.id"), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("first_delivery_id", sa.String(26), nullable=False, unique=True),
        sa.Column("second_delivery_id", sa.String(26), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bundle_id", "worker_id", name="uq_order_request_bundle_delivery_worker"),
        sa.CheckConstraint("first_delivery_id <> second_delivery_id", name="ck_order_request_bundle_delivery_pair"),
        sa.ForeignKeyConstraint(["first_delivery_id", "worker_id"], ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
                                name="fk_order_request_bundle_delivery_first"),
        sa.ForeignKeyConstraint(["second_delivery_id", "worker_id"], ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
                                name="fk_order_request_bundle_delivery_second"),
    )
    op.create_table(
        "order_request_bundle_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_travel_minutes", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_order_request_bundle_settings_singleton"),
        sa.CheckConstraint("default_travel_minutes >= 0 AND default_travel_minutes <= 720", name="ck_order_request_bundle_settings_travel"),
    )


def downgrade():
    raise RuntimeError("Keep double-header history; use a forward migration")
