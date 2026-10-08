"""add order request documents, versions, deliveries, notes

Revision ID: 20261002a001
Revises: 20260706a001
Create Date: 2026-10-02 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261002a001"
down_revision: Union[str, None] = "20260706a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_request_documents",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("document_number", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('formal', 'test')", name="ck_order_request_documents_kind"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number"),
    )
    op.create_index("ix_order_request_documents_kind", "order_request_documents", ["kind"])

    op.create_table(
        "order_request_versions",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision_of_version_id", sa.String(length=26), nullable=True),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("work_date_label", sa.String(length=200), nullable=False),
        sa.Column("site_id", sa.String(length=26), nullable=True),
        sa.Column("site_name", sa.String(length=200), nullable=False),
        sa.Column("site_address", sa.Text(), nullable=True),
        sa.Column("request_conditions", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.String(length=100), nullable=False),
        sa.Column("contact_desk", sa.String(length=200), nullable=False),
        sa.Column("counterparty_note", sa.Text(), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("pdf_object_key", sa.String(length=500), nullable=True),
        sa.Column("draft_worker_ids", sa.JSON(), nullable=True),
        sa.Column("phone_first", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("phone_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_note", sa.Text(), nullable=True),
        sa.Column("tracker_user_id", sa.String(length=26), nullable=True),
        sa.Column("follow_up_due_on", sa.Date(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("dispatch_stopped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')",
            name="ck_order_request_versions_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["order_request_documents.id"]),
        sa.ForeignKeyConstraint(["revision_of_version_id"], ["order_request_versions.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["tracker_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_no", name="uq_order_request_versions_doc_no"),
    )
    op.create_index("ix_order_request_versions_document", "order_request_versions", ["document_id"])
    op.create_index("ix_order_request_versions_status", "order_request_versions", ["status"])

    op.create_table(
        "order_request_deliveries",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("version_id", sa.String(length=26), nullable=False),
        sa.Column("worker_id", sa.String(length=26), nullable=False),
        sa.Column("worker_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("send_status", sa.String(length=20), nullable=False),
        sa.Column("ack_status", sa.String(length=20), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "send_status IN ('unsent', 'processing', 'accepted', 'failed', 'unknown')",
            name="ck_order_request_deliveries_send",
        ),
        sa.CheckConstraint(
            "ack_status IN ('unacked', 'acked')",
            name="ck_order_request_deliveries_ack",
        ),
        sa.ForeignKeyConstraint(["version_id"], ["order_request_versions.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "worker_id", name="uq_order_request_deliveries_version_worker"),
    )
    op.create_index("ix_order_request_deliveries_version", "order_request_deliveries", ["version_id"])
    op.create_index("ix_order_request_deliveries_send", "order_request_deliveries", ["send_status"])

    op.create_table(
        "order_request_notes",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("version_id", sa.String(length=26), nullable=False),
        sa.Column("author_user_id", sa.String(length=26), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["order_request_versions.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_request_notes_version", "order_request_notes", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_order_request_notes_version", table_name="order_request_notes")
    op.drop_table("order_request_notes")
    op.drop_index("ix_order_request_deliveries_send", table_name="order_request_deliveries")
    op.drop_index("ix_order_request_deliveries_version", table_name="order_request_deliveries")
    op.drop_table("order_request_deliveries")
    op.drop_index("ix_order_request_versions_status", table_name="order_request_versions")
    op.drop_index("ix_order_request_versions_document", table_name="order_request_versions")
    op.drop_table("order_request_versions")
    op.drop_index("ix_order_request_documents_kind", table_name="order_request_documents")
    op.drop_table("order_request_documents")
