"""Retain started participation independently of current application (③-B)."""
from alembic import op
import sqlalchemy as sa
revision = "20261024c001"
down_revision = "20261024b001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("order_request_application_ends",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("application_id", sa.String(26), sa.ForeignKey("order_request_worker_applications.id"), nullable=False),
        sa.Column("series_id", sa.String(26), nullable=False), sa.Column("worker_id", sa.String(26), nullable=False),
        sa.Column("source_delivery_id", sa.String(26), nullable=False), sa.Column("source_version_id", sa.String(26), nullable=False),
        sa.Column("source_state_id", sa.String(26), nullable=True),
        sa.Column("accepted_dates", sa.JSON(), nullable=False), sa.Column("retained_dates", sa.JSON(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_reason", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["source_delivery_id","worker_id"], ["order_request_deliveries.id","order_request_deliveries.worker_id"]),
        sa.ForeignKeyConstraint(["source_delivery_id","source_version_id"], ["order_request_deliveries.id","order_request_deliveries.version_id"]),
        sa.ForeignKeyConstraint(["source_version_id","series_id"], ["order_request_versions.id","order_request_versions.series_id"]),
        sa.ForeignKeyConstraint(["source_state_id","source_delivery_id"], ["delivery_participation_states.id","delivery_participation_states.delivery_id"]),
        sa.CheckConstraint("ended_reason IN ('document_ended','removed_from_recipients','declined_new_version')", name="ck_order_application_end_reason"))
    op.create_index("ix_order_application_ends_worker_series", "order_request_application_ends", ["series_id","worker_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM order_request_application_ends")).scalar():
        raise RuntimeError("終了履歴があるため削除できません")
    op.drop_table("order_request_application_ends")
