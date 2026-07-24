"""Add OCR row confirm metadata columns."""
from __future__ import annotations

import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260616a001"
down_revision: Union[str, None] = "20260411a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def _coerce_json(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value) if value else default
    return default


def _backfill_row(raw_payload_json, record_date, record_time, amount, transaction_no, receipt_no, validation_errors_json):
    from src.services.ocr.confirm_metadata import metadata_from_parsed_fields, resolve_amount_from_parser_meta
    from src.services.ocr.validation import validate_parsed_row
    from src.services.ocr.models import ParsedOcrRow

    raw_payload = _coerce_json(raw_payload_json, {})
    amount_inferred, amount_source = resolve_amount_from_parser_meta(raw_payload)

    parsed_dt_source = None
    if raw_payload.get("datetime_inferred") == "fuzzy_or_missing":
        parsed_dt_source = "fuzzy"
    elif record_date and record_time:
        parsed_dt_source = "ocr_strict"

    validation_errors = _coerce_json(validation_errors_json, [])
    if not validation_errors:
        parsed = ParsedOcrRow(
            source_type="paygate_screenshot",
            record_date=record_date,
            record_time=record_time,
            amount=amount,
            transaction_no=transaction_no,
            receipt_no=receipt_no,
        )
        validation_errors = validate_parsed_row(parsed)

    meta = metadata_from_parsed_fields(
        record_date=record_date,
        record_time=record_time,
        amount=amount,
        transaction_no=transaction_no,
        receipt_no=receipt_no,
        amount_meta=raw_payload,
        parsed_datetime_source=parsed_dt_source,
        validation_errors=validation_errors or None,
    )
    return meta


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = {column["name"] for column in inspector.get_columns("ocr_extracted_rows")}

    if "amount_inferred" not in existing:
        op.add_column(
            "ocr_extracted_rows",
            sa.Column("amount_inferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "amount_source" not in existing:
        op.add_column("ocr_extracted_rows", sa.Column("amount_source", sa.String(length=30), nullable=True))
    if "datetime_source" not in existing:
        op.add_column("ocr_extracted_rows", sa.Column("datetime_source", sa.String(length=30), nullable=True))
    if "confirm_required" not in existing:
        op.add_column(
            "ocr_extracted_rows",
            sa.Column("confirm_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "manually_edited" not in existing:
        op.add_column(
            "ocr_extracted_rows",
            sa.Column("manually_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    rows = connection.execute(
        sa.text(
            """
            SELECT id, record_date, record_time, amount, transaction_no, receipt_no,
                   validation_errors, raw_payload, status
            FROM ocr_extracted_rows
            """
        )
    ).fetchall()

    for row in rows:
        meta = _backfill_row(
            row.raw_payload,
            row.record_date,
            row.record_time,
            row.amount,
            row.transaction_no,
            row.receipt_no,
            row.validation_errors,
        )
        connection.execute(
            sa.text(
                """
                UPDATE ocr_extracted_rows
                SET amount_inferred = :amount_inferred,
                    amount_source = :amount_source,
                    datetime_source = :datetime_source,
                    confirm_required = :confirm_required,
                    manually_edited = :manually_edited
                WHERE id = :id
                """
            ),
            {
                "id": row.id,
                "amount_inferred": meta.amount_inferred,
                "amount_source": meta.amount_source,
                "datetime_source": meta.datetime_source,
                "confirm_required": meta.confirm_required,
                "manually_edited": meta.manually_edited,
            },
        )

    confirmed_requiring = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM ocr_extracted_rows
            WHERE status = 'confirmed' AND confirm_required = true AND deleted_at IS NULL
            """
        )
    ).scalar_one()
    logger.info(
        "OCR metadata backfill complete: %s confirmed rows now have confirm_required=true",
        confirmed_requiring,
    )


def downgrade() -> None:
    op.drop_column("ocr_extracted_rows", "manually_edited")
    op.drop_column("ocr_extracted_rows", "confirm_required")
    op.drop_column("ocr_extracted_rows", "datetime_source")
    op.drop_column("ocr_extracted_rows", "amount_source")
    op.drop_column("ocr_extracted_rows", "amount_inferred")
