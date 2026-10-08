"""Add OCR public upload links, sessions, attempts, and related columns."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260706a001"
down_revision: Union[str, None] = "20260702a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ocr_upload_links",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_suffix", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("public_memo", sa.Text(), nullable=True),
        sa.Column("internal_memo", sa.Text(), nullable=True),
        sa.Column("default_source_type", sa.String(length=30), nullable=False, server_default="required"),
        sa.Column("period_key", sa.String(length=6), nullable=True),
        sa.Column("max_upload_count", sa.Integer(), nullable=True),
        sa.Column("upload_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upload_count_paygate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upload_count_receipt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_upload_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_ocr_upload_links_token_hash"),
    )
    op.create_index("ix_ocr_upload_links_status", "ocr_upload_links", ["status"])
    op.create_index("ix_ocr_upload_links_expires_at", "ocr_upload_links", ["expires_at"])

    op.create_table(
        "ocr_upload_sessions",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("upload_link_id", sa.String(length=26), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["upload_link_id"], ["ocr_upload_links.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash", name="uq_ocr_upload_sessions_token_hash"),
    )
    op.create_index("ix_ocr_upload_sessions_link_id", "ocr_upload_sessions", ["upload_link_id"])

    op.create_table(
        "ocr_upload_rate_limits",
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("scope", "window_start"),
    )

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    image_cols = {c["name"] for c in inspector.get_columns("ocr_source_images")}

    def add_image_col(name: str, column: sa.Column) -> None:
        if name not in image_cols:
            op.add_column("ocr_source_images", column)

    add_image_col("upload_link_id", sa.Column("upload_link_id", sa.String(length=26), nullable=True))
    add_image_col("upload_origin", sa.Column("upload_origin", sa.String(length=20), nullable=True))
    add_image_col("public_uploader_name", sa.Column("public_uploader_name", sa.String(length=100), nullable=True))
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("ocr_source_images")}
    if "fk_ocr_source_images_upload_link_id" not in existing_fks and "upload_link_id" in (
        {c["name"] for c in inspector.get_columns("ocr_source_images")}
    ):
        op.create_foreign_key(
            "fk_ocr_source_images_upload_link_id",
            "ocr_source_images",
            "ocr_upload_links",
            ["upload_link_id"],
            ["id"],
        )

    job_cols = {c["name"] for c in inspector.get_columns("ocr_parse_jobs")}

    def add_job_col(name: str, column: sa.Column) -> None:
        if name not in job_cols:
            op.add_column("ocr_parse_jobs", column)

    add_job_col("source_channel", sa.Column("source_channel", sa.String(length=30), nullable=True))
    add_job_col("upload_attempt_id", sa.Column("upload_attempt_id", sa.String(length=26), nullable=True))
    add_job_col("image_ids_json", sa.Column("image_ids_json", sa.JSON(), nullable=True))
    add_job_col("claimed_at", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    add_job_col("claim_token", sa.Column("claim_token", sa.String(length=64), nullable=True))
    add_job_col("priority", sa.Column("priority", sa.Integer(), nullable=False, server_default="10"))

    op.create_table(
        "ocr_upload_attempts",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("upload_link_id", sa.String(length=26), nullable=False),
        sa.Column("source_image_id", sa.String(length=26), nullable=True),
        sa.Column("reused_existing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("public_uploader_name", sa.String(length=100), nullable=True),
        sa.Column("parse_job_id", sa.String(length=26), nullable=True),
        sa.Column("attempt_status", sa.String(length=40), nullable=False),
        sa.Column("client_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("quarantine_storage_key", sa.String(length=500), nullable=True),
        sa.Column("gate_skipped_reason", sa.String(length=30), nullable=True),
        sa.Column("gate_payment_method_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["upload_link_id"], ["ocr_upload_links.id"]),
        sa.ForeignKeyConstraint(["source_image_id"], ["ocr_source_images.id"]),
        sa.ForeignKeyConstraint(["parse_job_id"], ["ocr_parse_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_upload_attempts_link_id", "ocr_upload_attempts", ["upload_link_id"])
    op.create_index("ix_ocr_upload_attempts_status", "ocr_upload_attempts", ["attempt_status"])


def downgrade() -> None:
    op.drop_index("ix_ocr_upload_attempts_status", table_name="ocr_upload_attempts")
    op.drop_index("ix_ocr_upload_attempts_link_id", table_name="ocr_upload_attempts")
    op.drop_table("ocr_upload_attempts")

    for col in ("priority", "claim_token", "claimed_at", "image_ids_json", "upload_attempt_id", "source_channel"):
        try:
            op.drop_column("ocr_parse_jobs", col)
        except Exception:
            pass

    try:
        op.drop_constraint("fk_ocr_source_images_upload_link_id", "ocr_source_images", type_="foreignkey")
    except Exception:
        pass
    for col in ("public_uploader_name", "upload_origin", "upload_link_id"):
        try:
            op.drop_column("ocr_source_images", col)
        except Exception:
            pass

    op.drop_table("ocr_upload_rate_limits")
    op.drop_index("ix_ocr_upload_sessions_link_id", table_name="ocr_upload_sessions")
    op.drop_table("ocr_upload_sessions")
    op.drop_index("ix_ocr_upload_links_expires_at", table_name="ocr_upload_links")
    op.drop_index("ix_ocr_upload_links_status", table_name="ocr_upload_links")
    op.drop_table("ocr_upload_links")
