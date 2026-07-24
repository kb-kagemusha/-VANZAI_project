"""phase1 revision B registration requests

Revision ID: 20260408b001
Revises: 20260408a001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408b001"
down_revision: Union[str, None] = "20260408a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registration_requests",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("public_token_hash", sa.String(length=255), nullable=True),
        sa.Column("access_pin_hash", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("approved_target_type", sa.String(length=50), nullable=True),
        sa.Column("approved_target_id", sa.String(length=26), nullable=True),
        sa.Column("superseded_by_request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=True),
        sa.Column("submitted_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registration_requests_status", "registration_requests", ["status"], unique=False)
    op.create_index("ix_registration_requests_request_type", "registration_requests", ["request_type"], unique=False)
    op.create_index("ix_registration_requests_source_type", "registration_requests", ["source_type"], unique=False)
    op.create_index("ix_registration_requests_expires_at", "registration_requests", ["expires_at"], unique=False)
    op.create_index("uq_registration_requests_public_token_hash", "registration_requests", ["public_token_hash"], unique=True)

    op.create_table(
        "worker_registration_request_details",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name_furigana", sa.String(length=100), nullable=True),
        sa.Column("first_name_furigana", sa.String(length=100), nullable=True),
        sa.Column("sole_proprietor_name", sa.String(length=200), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("route_group", sa.String(length=100), nullable=True),
        sa.Column("introducer_supplier_name_raw", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("zipcode", sa.String(length=20), nullable=True),
        sa.Column("prefecture", sa.String(length=50), nullable=True),
        sa.Column("city_address", sa.Text(), nullable=True),
        sa.Column("building_address", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name_kana", sa.String(length=200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_branch", sa.String(length=100), nullable=True),
        sa.Column("bank_branch_number", sa.String(length=10), nullable=True),
        sa.Column("bank_account_type", sa.String(length=20), nullable=True),
        sa.Column("bank_account_number", sa.String(length=20), nullable=True),
        sa.Column("bank_account_holder", sa.String(length=200), nullable=True),
        sa.Column("invoice_registration_status", sa.String(length=30), nullable=True),
        sa.Column("invoice_registration_number", sa.String(length=20), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_worker_registration_request_details_request_id"),
    )

    op.create_table(
        "supplier_individual_request_details",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=False),
        sa.Column("supplier_type", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("name_furigana", sa.String(length=100), nullable=True),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("zipcode", sa.String(length=20), nullable=True),
        sa.Column("prefecture", sa.String(length=50), nullable=True),
        sa.Column("city_address", sa.Text(), nullable=True),
        sa.Column("building_address", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_branch", sa.String(length=100), nullable=True),
        sa.Column("bank_branch_number", sa.String(length=10), nullable=True),
        sa.Column("bank_account_type", sa.String(length=20), nullable=True),
        sa.Column("bank_account_number", sa.String(length=20), nullable=True),
        sa.Column("bank_account_holder_kana", sa.String(length=200), nullable=True),
        sa.Column("invoice_registration_status", sa.String(length=30), nullable=True),
        sa.Column("invoice_registration_number", sa.String(length=20), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_supplier_individual_request_details_request_id"),
    )

    op.create_table(
        "supplier_corporation_request_details",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=False),
        sa.Column("supplier_type", sa.String(length=20), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("company_name_furigana", sa.String(length=200), nullable=True),
        sa.Column("representative_name", sa.String(length=100), nullable=True),
        sa.Column("representative_name_furigana", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("zipcode", sa.String(length=20), nullable=True),
        sa.Column("prefecture", sa.String(length=50), nullable=True),
        sa.Column("city_address", sa.Text(), nullable=True),
        sa.Column("building_address", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_branch", sa.String(length=100), nullable=True),
        sa.Column("bank_branch_number", sa.String(length=10), nullable=True),
        sa.Column("bank_account_type", sa.String(length=20), nullable=True),
        sa.Column("bank_account_number", sa.String(length=20), nullable=True),
        sa.Column("bank_account_holder_kana", sa.String(length=200), nullable=True),
        sa.Column("invoice_registration_status", sa.String(length=30), nullable=True),
        sa.Column("invoice_registration_number", sa.String(length=20), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_supplier_corporation_request_details_request_id"),
    )

    op.create_table(
        "introducer_identity_request_details",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=False),
        sa.Column("related_worker_request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=True),
        sa.Column("related_supplier_request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=True),
        sa.Column("subject_name", sa.String(length=100), nullable=True),
        sa.Column("subject_name_furigana", sa.String(length=100), nullable=True),
        sa.Column("submission_reason", sa.Text(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_introducer_identity_request_details_request_id"),
    )

    op.create_table(
        "registration_request_files",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("request_id", sa.String(length=26), sa.ForeignKey("registration_requests.id"), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("document_part", sa.String(length=20), nullable=False, server_default="single"),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("scan_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registration_request_files_request_id", "registration_request_files", ["request_id"], unique=False)
    op.create_index("ix_registration_request_files_document_type", "registration_request_files", ["document_type"], unique=False)
    op.create_index("ix_registration_request_files_delete_after", "registration_request_files", ["delete_after"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_registration_request_files_delete_after", table_name="registration_request_files")
    op.drop_index("ix_registration_request_files_document_type", table_name="registration_request_files")
    op.drop_index("ix_registration_request_files_request_id", table_name="registration_request_files")
    op.drop_table("registration_request_files")
    op.drop_table("introducer_identity_request_details")
    op.drop_table("supplier_corporation_request_details")
    op.drop_table("supplier_individual_request_details")
    op.drop_table("worker_registration_request_details")
    op.drop_index("uq_registration_requests_public_token_hash", table_name="registration_requests")
    op.drop_index("ix_registration_requests_expires_at", table_name="registration_requests")
    op.drop_index("ix_registration_requests_source_type", table_name="registration_requests")
    op.drop_index("ix_registration_requests_request_type", table_name="registration_requests")
    op.drop_index("ix_registration_requests_status", table_name="registration_requests")
    op.drop_table("registration_requests")