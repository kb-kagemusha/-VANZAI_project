"""OCR receipt orchestration service."""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.ocr import (
    OcrExtractedRow,
    OcrMonthlyExport,
    OcrParseJob,
    OcrReconciliationBatch,
    OcrReconciliationResult,
    OcrSourceImage,
)
from src.services.audit import AuditService
from src.services.document_storage import ObjectStorage
from src.services.ocr.dedupe import (
    dedupe_paygate_screenshot_entries,
    paygate_row_completeness_score,
)
from src.services.ocr.duplicate_detection import find_duplicate_receipt_candidate
from src.services.ocr.image_preprocess import (
    preprocess_blue_amount_channel,
    preprocess_for_ocr,
    preprocess_upscaled_for_ocr,
)
from src.services.ocr.merge_results import merge_ocr_results
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.paddle_engine import run_ocr, run_ocr_from_text
from src.services.ocr.settlement_ocr import run_settlement_ocr
from src.services.ocr.parsers.registry import VALID_SOURCE_TYPES, get_parser
from src.services.ocr.reconciliation import parse_hq_csv, reconcile_rows, summarize_matches
from src.services.ocr.confirm_metadata import (
    OcrConfirmRejectedError,
    get_confirm_rejection_reasons,
    metadata_from_parsed_fields,
    resolve_datetime_source,
)
from src.services.ocr.export import rows_to_csv, settlement_rows_to_csv
from src.services.ocr.settlement_processing import DEFAULT_BRANCH_ID, apply_settlement_derived_fields
from src.services.ocr.parsers.settlement_terminal_id import normalize_settlement_terminal_id, normalize_settlement_terminal_short_id

from src.services.ocr.validation import is_paygate_row_saveable, validate_parsed_row

_SETTLEMENT_RECOMPUTE_TRIGGER_FIELDS = {
    "record_date",
    "record_time",
    "amount",
    "cash_sales",
    "credit_sales",
    "pos_sales",
    "other_payment",
    "transaction_count",
    "terminal_short_id",
}

OCR_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _ocr_storage() -> ObjectStorage:
    return ObjectStorage(root=Path(os.getenv("OCR_STORAGE_ROOT", "storage/ocr")))


def build_ocr_object_key(image_id: str, original_name: str | None) -> str:
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        suffix = ".jpg"
    return f"images/{image_id}{suffix}"


def _sync_metadata_from_parsed(row: OcrExtractedRow, parsed: ParsedOcrRow) -> None:
    validation_errors = parsed.validation_errors or validate_parsed_row(parsed)
    row.validation_errors = validation_errors or None
    row.amount_inferred = parsed.amount_inferred
    row.amount_source = parsed.amount_source
    row.datetime_source = parsed.datetime_source
    row.confirm_required = parsed.confirm_required
    row.manually_edited = parsed.manually_edited


def _recompute_row_metadata(
    row: OcrExtractedRow,
    *,
    amount_touched: bool = False,
    datetime_touched: bool = False,
) -> None:
    if amount_touched:
        row.amount_source = "manual"
        row.amount_inferred = False
    if datetime_touched:
        row.datetime_source = "manual"

    parsed = _extracted_row_to_parsed(row)
    validation_errors = validate_parsed_row(parsed)
    row.validation_errors = validation_errors or None

    amount_meta = {} if row.amount_source == "manual" else (row.raw_payload or {})
    if row.datetime_source == "manual":
        parsed_datetime_source = None
        datetime_override = "manual"
    else:
        parsed_datetime_source = resolve_datetime_source(
            row.record_date,
            row.record_time,
            row.datetime_source,
        )
        datetime_override = None

    meta = metadata_from_parsed_fields(
        record_date=row.record_date,
        record_time=row.record_time,
        amount=row.amount,
        transaction_no=row.transaction_no,
        receipt_no=row.receipt_no,
        amount_meta=amount_meta,
        parsed_datetime_source=parsed_datetime_source,
        validation_errors=validation_errors or None,
        manually_edited=row.manually_edited,
        amount_source_override=row.amount_source if row.amount_source == "manual" else None,
        amount_inferred_override=False if row.amount_source == "manual" else None,
        datetime_source_override=datetime_override,
    )
    row.amount_inferred = meta.amount_inferred
    row.amount_source = meta.amount_source
    row.datetime_source = meta.datetime_source
    row.confirm_required = meta.confirm_required


def _parsed_to_db_row(
    parsed: ParsedOcrRow,
    *,
    source_image_id: str,
    parse_job_id: str,
) -> OcrExtractedRow:
    validation_errors = parsed.validation_errors or validate_parsed_row(parsed)
    if parsed.amount_source is None:
        meta = metadata_from_parsed_fields(
            record_date=parsed.record_date,
            record_time=parsed.record_time,
            amount=parsed.amount,
            transaction_no=parsed.transaction_no,
            receipt_no=parsed.receipt_no,
            amount_meta=parsed.raw_payload,
            parsed_datetime_source=parsed.datetime_source,
            validation_errors=validation_errors or None,
            manually_edited=parsed.manually_edited,
        )
        parsed.amount_inferred = meta.amount_inferred
        parsed.amount_source = meta.amount_source
        parsed.datetime_source = meta.datetime_source
        parsed.confirm_required = meta.confirm_required

    row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=source_image_id,
        parse_job_id=parse_job_id,
        source_type=parsed.source_type,
        period_key=parsed.period_key,
        record_date=parsed.record_date,
        record_time=parsed.record_time,
        amount=parsed.amount,
        transaction_no=parsed.transaction_no,
        receipt_no=parsed.receipt_no,
        payment_method=parsed.payment_method,
        terminal_id=normalize_settlement_terminal_id(parsed.terminal_id),
        cash_sales=parsed.cash_sales,
        credit_sales=parsed.credit_sales,
        transaction_count=parsed.transaction_count,
        tax_included=parsed.tax_included,
        subtotal=parsed.subtotal,
        store_name=parsed.store_name,
        confidence=Decimal(str(round(parsed.confidence, 4))),
        amount_inferred=parsed.amount_inferred,
        amount_source=parsed.amount_source,
        datetime_source=parsed.datetime_source,
        confirm_required=parsed.confirm_required,
        manually_edited=parsed.manually_edited,
        status="pending_review",
        validation_errors=validation_errors or None,
        raw_payload=parsed.raw_payload,
        report_date=parsed.record_date,
    )

    if parsed.source_type == "paygate_settlement":
        row.terminal_short_id = normalize_settlement_terminal_short_id(
            parsed.terminal_short_id,
            from_ocr=True,
        )
        row.pos_sales = parsed.pos_sales
        row.other_payment = parsed.other_payment
        row.cash_unit_count = parsed.cash_unit_count
        row.pos_unit_count = parsed.pos_unit_count
        row.work_date = parsed.work_date
        row.unit_breakdown_status = parsed.unit_breakdown_status
        row.unit_breakdown_json = parsed.unit_breakdown_json
        row.amount_ones_digit_ok = parsed.amount_ones_digit_ok
        row.blocking_errors = parsed.blocking_errors
        row.warnings = parsed.warnings
        row.branch_id = parsed.branch_id or DEFAULT_BRANCH_ID
        row.staff_id = parsed.staff_id
        row.reconciliation_eligible = True

    return row


def _extracted_row_to_parsed(row: OcrExtractedRow) -> ParsedOcrRow:
    return ParsedOcrRow(
        source_type=row.source_type,
        record_date=row.record_date,
        record_time=row.record_time,
        amount=row.amount,
        transaction_no=row.transaction_no,
        receipt_no=row.receipt_no,
        payment_method=row.payment_method,
        terminal_id=row.terminal_id,
        cash_sales=row.cash_sales,
        credit_sales=row.credit_sales,
        transaction_count=row.transaction_count,
        tax_included=row.tax_included,
        subtotal=row.subtotal,
        store_name=row.store_name,
        confidence=float(row.confidence or 0),
        amount_inferred=row.amount_inferred,
        amount_source=row.amount_source,
        datetime_source=row.datetime_source,
        confirm_required=row.confirm_required,
        manually_edited=row.manually_edited,
        raw_payload=row.raw_payload or {},
        terminal_short_id=getattr(row, "terminal_short_id", None),
        pos_sales=getattr(row, "pos_sales", None),
        other_payment=getattr(row, "other_payment", None),
        branch_id=getattr(row, "branch_id", None),
        staff_id=getattr(row, "staff_id", None),
    )


def _recompute_settlement_row_metadata(session: Session, row: OcrExtractedRow) -> None:
    """paygate_settlement 行の派生項目(work_date/unit_breakdown/blocking/warnings/
    confirm_required/重複候補)を再計算する。update_row からの手動編集後、および
    パース直後の重複検知に使用する。
    """
    if not row.branch_id:
        row.branch_id = DEFAULT_BRANCH_ID
    duplicate_id = find_duplicate_receipt_candidate(
        session,
        terminal_short_id=row.terminal_short_id,
        record_date=row.record_date,
        record_time=row.record_time,
        amount=row.amount,
        transaction_count=row.transaction_count,
        exclude_row_id=row.id,
    )
    row.duplicate_receipt_candidate = duplicate_id is not None
    apply_settlement_derived_fields(row)

    # The pre-existing row that this one duplicates also needs to be flagged, since
    # duplicate_receipt_candidate is a symmetric relationship (both receipts are
    # candidates for manual review), not just the newly-parsed one.
    if duplicate_id is not None:
        other_row = session.get(OcrExtractedRow, duplicate_id)
        if other_row is not None and not other_row.duplicate_receipt_candidate:
            other_row.duplicate_receipt_candidate = True
            apply_settlement_derived_fields(other_row)


def _apply_parsed_to_extracted_row(row: OcrExtractedRow, parsed: ParsedOcrRow, *, parse_job_id: str) -> None:
    row.parse_job_id = parse_job_id
    row.period_key = parsed.period_key
    row.record_date = parsed.record_date
    row.record_time = parsed.record_time
    row.amount = parsed.amount
    row.transaction_no = parsed.transaction_no
    row.receipt_no = parsed.receipt_no
    row.payment_method = parsed.payment_method
    row.confidence = Decimal(str(round(parsed.confidence, 4)))
    row.raw_payload = parsed.raw_payload
    row.report_date = parsed.record_date
    _sync_metadata_from_parsed(row, parsed)


def _find_settlement_rows_for_image(session: Session, image_id: str) -> list[OcrExtractedRow]:
    return list(
        session.execute(
            select(OcrExtractedRow)
            .where(
                OcrExtractedRow.source_image_id == image_id,
                OcrExtractedRow.source_type == "paygate_settlement",
                OcrExtractedRow.deleted_at.is_(None),
            )
            .order_by(OcrExtractedRow.created_at.desc())
        )
        .scalars()
        .all()
    )


def _apply_settlement_parsed_to_extracted_row(
    row: OcrExtractedRow,
    parsed: ParsedOcrRow,
    *,
    parse_job_id: str,
    session: Session,
) -> None:
    row.parse_job_id = parse_job_id
    row.period_key = parsed.period_key
    row.record_date = parsed.record_date
    row.record_time = parsed.record_time
    row.amount = parsed.amount
    row.transaction_no = parsed.transaction_no
    row.receipt_no = parsed.receipt_no
    row.payment_method = parsed.payment_method
    row.terminal_id = normalize_settlement_terminal_id(parsed.terminal_id)
    row.cash_sales = parsed.cash_sales
    row.credit_sales = parsed.credit_sales
    row.pos_sales = parsed.pos_sales
    row.other_payment = parsed.other_payment
    row.transaction_count = parsed.transaction_count
    row.tax_included = parsed.tax_included
    row.subtotal = parsed.subtotal
    row.store_name = parsed.store_name
    row.confidence = Decimal(str(round(parsed.confidence, 4)))
    row.raw_payload = parsed.raw_payload
    row.report_date = parsed.record_date
    row.terminal_short_id = normalize_settlement_terminal_short_id(
        parsed.terminal_short_id,
        from_ocr=True,
    )
    row.cash_unit_count = parsed.cash_unit_count
    row.pos_unit_count = parsed.pos_unit_count
    row.work_date = parsed.work_date
    row.unit_breakdown_status = parsed.unit_breakdown_status
    row.unit_breakdown_json = parsed.unit_breakdown_json
    row.amount_ones_digit_ok = parsed.amount_ones_digit_ok
    row.blocking_errors = parsed.blocking_errors
    row.warnings = parsed.warnings
    if not row.branch_id:
        row.branch_id = DEFAULT_BRANCH_ID
    row.manually_edited = False
    row.validation_errors = parsed.validation_errors or validate_parsed_row(parsed) or None
    _sync_metadata_from_parsed(row, parsed)
    _recompute_settlement_row_metadata(session, row)


def _find_existing_paygate_row(
    session: Session,
    *,
    transaction_no: str | None,
    receipt_no: str | None,
) -> OcrExtractedRow | None:
    conditions = []
    if receipt_no:
        conditions.append(OcrExtractedRow.receipt_no == receipt_no)
    if transaction_no:
        conditions.append(OcrExtractedRow.transaction_no == transaction_no)
    if not conditions:
        return None
    return session.execute(
        select(OcrExtractedRow).where(
            OcrExtractedRow.deleted_at.is_(None),
            OcrExtractedRow.source_type == "paygate_screenshot",
            or_(*conditions),
        )
    ).scalar_one_or_none()


class OcrService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)
        self.storage = _ocr_storage()

    def upload_image(
        self,
        *,
        file_bytes: bytes,
        file_name: str | None,
        source_type: str,
        uploaded_by: str,
        mime_type: str | None = None,
    ) -> tuple[OcrSourceImage, bool]:
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type: {source_type}")
        if not file_bytes:
            raise ValueError("Empty file")
        if len(file_bytes) > OCR_UPLOAD_MAX_BYTES:
            raise ValueError("File too large")

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        existing = self.session.execute(
            select(OcrSourceImage).where(OcrSourceImage.sha256 == sha256)
        ).scalar_one_or_none()
        if existing:
            if existing.deleted_at is not None:
                existing.deleted_at = None
                existing.original_filename = file_name
                existing.source_type = source_type
                existing.mime_type = mime_type
                existing.size_bytes = len(file_bytes)
                existing.parse_status = "pending"
                existing.error_message = None
                existing.uploaded_by = uploaded_by
                existing.period_key = None
                existing.last_job_id = None
                self.session.flush()
                self.audit.log(
                    "ocr_image_uploaded",
                    target_type="ocr_source_image",
                    target_id=existing.id,
                    actor=uploaded_by,
                    after_value={"source_type": source_type, "sha256": sha256, "restored": True},
                )
            return existing, True

        image_id = generate_ulid()
        storage_key = build_ocr_object_key(image_id, file_name)
        self.storage.save_bytes(storage_key, file_bytes)

        image = OcrSourceImage(
            id=image_id,
            source_type=source_type,
            original_filename=file_name,
            storage_key=storage_key,
            sha256=sha256,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
            parse_status="pending",
            uploaded_by=uploaded_by,
        )
        self.session.add(image)
        self.session.flush()

        self.audit.log(
            "ocr_image_uploaded",
            target_type="ocr_source_image",
            target_id=image.id,
            actor=uploaded_by,
            after_value={"source_type": source_type, "sha256": sha256},
        )
        return image, False

    def list_images(
        self,
        *,
        source_type: str | None = None,
        parse_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[OcrSourceImage], int]:
        query = select(OcrSourceImage).where(OcrSourceImage.deleted_at.is_(None))
        if source_type:
            query = query.where(OcrSourceImage.source_type == source_type)
        if parse_status:
            query = query.where(OcrSourceImage.parse_status == parse_status)
        total = self.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        items = self.session.execute(
            query.order_by(OcrSourceImage.created_at.desc()).offset(offset).limit(limit)
        ).scalars().all()
        return list(items), total

    def filename_duplicate_flags(self, items: list[OcrSourceImage]) -> dict[str, bool]:
        from collections import Counter

        names = Counter(
            image.original_filename
            for image in items
            if image.original_filename
        )
        return {
            image.id: bool(image.original_filename and names[image.original_filename] > 1)
            for image in items
        }

    def get_image(self, image_id: str) -> OcrSourceImage | None:
        image = self.session.get(OcrSourceImage, image_id)
        if image is None or image.deleted_at is not None:
            return None
        return image

    def get_image_filenames(self, image_ids: set[str]) -> dict[str, str | None]:
        if not image_ids:
            return {}
        rows = self.session.execute(
            select(OcrSourceImage.id, OcrSourceImage.original_filename).where(
                OcrSourceImage.id.in_(image_ids),
                OcrSourceImage.deleted_at.is_(None),
            )
        ).all()
        return {image_id: filename for image_id, filename in rows}

    def update_image_filename(
        self,
        image_id: str,
        *,
        original_filename: str,
        actor: str,
    ) -> OcrSourceImage:
        image = self.get_image(image_id)
        if image is None:
            raise ValueError("Image not found")

        name = original_filename.strip()
        if not name:
            raise ValueError("Filename is required")

        before = image.original_filename
        image.original_filename = name
        self.audit.log(
            "ocr_image_renamed",
            target_type="ocr_source_image",
            target_id=image.id,
            actor=actor,
            before_value={"original_filename": before},
            after_value={"original_filename": name},
        )
        return image

    def read_image_bytes(self, image: OcrSourceImage) -> bytes:
        return self.storage.read_bytes(image.storage_key)

    def delete_images(self, image_ids: list[str], *, actor: str) -> int:
        if not image_ids:
            raise ValueError("image_ids is required")

        now = datetime.now(timezone.utc)
        deleted = 0
        cascaded_row_ids: list[str] = []
        for image_id in image_ids:
            image = self.session.get(OcrSourceImage, image_id)
            if image is None or image.deleted_at is not None:
                continue
            image.deleted_at = now
            deleted += 1
            self.audit.log(
                "ocr_image_deleted",
                target_type="ocr_source_image",
                target_id=image.id,
                actor=actor,
                before_value={"parse_status": image.parse_status, "sha256": image.sha256},
            )
            related_rows = self.session.execute(
                select(OcrExtractedRow).where(
                    OcrExtractedRow.source_image_id == image.id,
                    OcrExtractedRow.deleted_at.is_(None),
                )
            ).scalars().all()
            for row in related_rows:
                row.deleted_at = now
                cascaded_row_ids.append(row.id)
                self.audit.log(
                    "ocr_row_deleted",
                    target_type="ocr_extracted_row",
                    target_id=row.id,
                    actor=actor,
                    before_value={
                        "status": row.status,
                        "period_key": row.period_key,
                        "cascade_from_image_id": image.id,
                    },
                )

        if cascaded_row_ids:
            self.audit.log(
                "ocr_rows_deleted",
                target_type="ocr_extracted_row",
                target_id=cascaded_row_ids[0],
                actor=actor,
                after_value={
                    "count": len(cascaded_row_ids),
                    "row_ids": cascaded_row_ids,
                    "cascade_from_image_ids": image_ids,
                },
            )
        return deleted

    def reparse_settlement_row(self, *, row_id: str, executed_by: str) -> OcrParseJob:
        row = self.session.get(OcrExtractedRow, row_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Row not found")
        if row.source_type != "paygate_settlement":
            raise ValueError("Only settlement rows support reparse")
        if row.status == "confirmed":
            raise ValueError("Confirmed rows cannot be reparsed")
        return self.parse_images(
            image_ids=[row.source_image_id],
            executed_by=executed_by,
            settlement_target_row_ids={row.source_image_id: row_id},
        )

    def parse_images(
        self,
        *,
        image_ids: list[str],
        executed_by: str,
        ocr_text_override: dict[str, str] | None = None,
        settlement_target_row_ids: dict[str, str] | None = None,
    ) -> OcrParseJob:
        if not image_ids:
            raise ValueError("image_ids is required")

        job = OcrParseJob(
            id=generate_ulid(),
            status="processing",
            image_count=len(image_ids),
            executed_by=executed_by,
        )
        self.session.add(job)
        self.session.flush()

        success_count = 0
        failed_count = 0
        row_count = 0
        dedupe_skipped = 0
        raw_payload: dict[str, object] = {}
        paygate_entries: list[tuple[str, ParsedOcrRow]] = []

        for image_id in image_ids:
            image = self.session.get(OcrSourceImage, image_id)
            if image is None or image.deleted_at is not None:
                failed_count += 1
                continue

            try:
                if ocr_text_override and image_id in ocr_text_override:
                    ocr_result = run_ocr_from_text(ocr_text_override[image_id])
                else:
                    image_bytes = self.storage.read_bytes(image.storage_key)
                    if image.source_type == "paygate_settlement":
                        ocr_result = run_settlement_ocr(image_bytes)
                    else:
                        ocr_result = run_ocr(preprocess_for_ocr(image_bytes))
                    if image.source_type == "paygate_screenshot":
                        ocr_result = merge_ocr_results(
                            ocr_result,
                            run_ocr(preprocess_blue_amount_channel(image_bytes)),
                            run_ocr(preprocess_upscaled_for_ocr(image_bytes)),
                        )

                parser = get_parser(image.source_type)
                parsed_rows = parser.parse(ocr_result)
                if (
                    not parsed_rows
                    and image.source_type == "paygate_screenshot"
                    and not ocr_text_override
                ):
                    ocr_result = merge_ocr_results(
                        ocr_result,
                        run_ocr(preprocess_upscaled_for_ocr(image_bytes)),
                    )
                    parsed_rows = parser.parse(ocr_result)
                if not parsed_rows:
                    image.parse_status = "failed"
                    image.error_message = "No structured rows extracted"
                    image.last_job_id = job.id
                    failed_count += 1
                    continue

                period_keys = {parsed.period_key for parsed in parsed_rows if parsed.period_key}
                if image.source_type == "paygate_screenshot":
                    for parsed in parsed_rows:
                        if not is_paygate_row_saveable(parsed):
                            continue
                        paygate_entries.append((image.id, parsed))
                else:
                    now = datetime.now(timezone.utc)
                    for parsed in parsed_rows:
                        target_row_id = (settlement_target_row_ids or {}).get(image.id)
                        if target_row_id:
                            target = self.session.get(OcrExtractedRow, target_row_id)
                            if (
                                target is None
                                or target.deleted_at is not None
                                or target.source_image_id != image.id
                                or target.source_type != "paygate_settlement"
                                or target.status == "confirmed"
                            ):
                                raise ValueError("Reparse target row is not available")
                            _apply_settlement_parsed_to_extracted_row(
                                target,
                                parsed,
                                parse_job_id=job.id,
                                session=self.session,
                            )
                            row_count += 1
                            continue

                        existing_rows = _find_settlement_rows_for_image(self.session, image.id)
                        pending_rows = [row for row in existing_rows if row.status != "confirmed"]
                        if pending_rows:
                            target = pending_rows[0]
                            _apply_settlement_parsed_to_extracted_row(
                                target,
                                parsed,
                                parse_job_id=job.id,
                                session=self.session,
                            )
                            for duplicate in pending_rows[1:]:
                                duplicate.deleted_at = now
                            row_count += 1
                        elif not existing_rows:
                            db_row = _parsed_to_db_row(
                                parsed,
                                source_image_id=image.id,
                                parse_job_id=job.id,
                            )
                            self.session.add(db_row)
                            self.session.flush()
                            _recompute_settlement_row_metadata(self.session, db_row)
                            row_count += 1
                        else:
                            dedupe_skipped += 1

                image.parse_status = "completed"
                image.error_message = None
                image.last_job_id = job.id
                if period_keys:
                    image.period_key = sorted(period_keys)[-1]
                success_count += 1
                raw_payload[image_id] = {
                    "line_count": len(ocr_result.lines),
                    "row_count": len(parsed_rows),
                }
            except Exception as exc:
                image.parse_status = "failed"
                image.error_message = str(exc)
                image.last_job_id = job.id
                failed_count += 1

        if paygate_entries:
            deduped_entries, intra_job_skipped = dedupe_paygate_screenshot_entries(paygate_entries)
            dedupe_skipped += intra_job_skipped
            for image_id, parsed in deduped_entries:
                existing = _find_existing_paygate_row(
                    self.session,
                    transaction_no=parsed.transaction_no,
                    receipt_no=parsed.receipt_no,
                )
                if existing:
                    if existing.status != "confirmed":
                        new_score = paygate_row_completeness_score(parsed)
                        old_score = paygate_row_completeness_score(_extracted_row_to_parsed(existing))
                        if new_score > old_score:
                            _apply_parsed_to_extracted_row(existing, parsed, parse_job_id=job.id)
                            existing.source_image_id = image_id
                    dedupe_skipped += 1
                    continue

                db_row = _parsed_to_db_row(
                    parsed,
                    source_image_id=image_id,
                    parse_job_id=job.id,
                )
                self.session.add(db_row)
                row_count += 1

        if dedupe_skipped:
            raw_payload["paygate_dedupe_skipped"] = dedupe_skipped

        job.success_count = success_count
        job.failed_count = failed_count
        job.row_count = row_count
        job.raw_ocr_payload = raw_payload
        job.status = "completed" if failed_count == 0 else ("partial_error" if success_count else "failed")
        job.completed_at = datetime.now(timezone.utc)

        self.audit.log(
            "ocr_parse_completed",
            target_type="ocr_parse_job",
            target_id=job.id,
            actor=executed_by,
            after_value={
                "image_count": job.image_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "row_count": row_count,
            },
        )
        return job

    def list_rows(
        self,
        *,
        period_key: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[OcrExtractedRow], int]:
        query = select(OcrExtractedRow).where(OcrExtractedRow.deleted_at.is_(None))
        if period_key:
            query = query.where(OcrExtractedRow.period_key == period_key)
        if source_type:
            query = query.where(OcrExtractedRow.source_type == source_type)
        if status:
            query = query.where(OcrExtractedRow.status == status)
        total = self.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        items = self.session.execute(
            query.order_by(OcrExtractedRow.record_date.desc(), OcrExtractedRow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
        return list(items), total

    def update_row(self, row_id: str, updates: dict, actor: str) -> OcrExtractedRow:
        row = self.session.get(OcrExtractedRow, row_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Row not found")

        before = {
            "amount": str(row.amount) if row.amount is not None else None,
            "transaction_no": row.transaction_no,
            "receipt_no": row.receipt_no,
            "status": row.status,
        }

        date_fields = {"record_date", "report_date"}
        decimal_fields = {"amount", "cash_sales", "credit_sales", "tax_included", "subtotal", "pos_sales", "other_payment"}
        int_fields = {"transaction_count"}
        amount_touched = "amount" in updates
        datetime_touched = "record_date" in updates or "record_time" in updates
        settlement_recompute_needed = bool(_SETTLEMENT_RECOMPUTE_TRIGGER_FIELDS & set(updates.keys()))

        for key, value in updates.items():
            if not hasattr(row, key):
                continue
            if key in date_fields and value:
                setattr(row, key, date.fromisoformat(value) if isinstance(value, str) else value)
            elif key in decimal_fields and value is not None and value != "":
                setattr(row, key, Decimal(str(value)))
            elif key in int_fields and value is not None and value != "":
                setattr(row, key, int(value))
            else:
                setattr(row, key, value)

        if row.record_date:
            row.period_key = row.record_date.strftime("%Y%m")
            if not row.report_date:
                row.report_date = row.record_date

        row.manually_edited = True

        if row.source_type == "paygate_settlement":
            if "terminal_id" in updates:
                row.terminal_id = normalize_settlement_terminal_id(row.terminal_id)
            if "terminal_short_id" in updates:
                raw_short_id = updates.get("terminal_short_id")
                if raw_short_id in (None, ""):
                    row.terminal_short_id = None
                else:
                    normalized_short_id = normalize_settlement_terminal_short_id(raw_short_id)
                    if normalized_short_id is None:
                        raise ValueError("terminal_short_id must be exactly 4 hexadecimal characters")
                    row.terminal_short_id = normalized_short_id
            if amount_touched:
                row.amount_source = "manual"
                row.amount_inferred = False
            if datetime_touched:
                row.datetime_source = "manual"
            if settlement_recompute_needed:
                _recompute_settlement_row_metadata(self.session, row)
        else:
            _recompute_row_metadata(row, amount_touched=amount_touched, datetime_touched=datetime_touched)

        self.audit.log(
            "ocr_row_updated",
            target_type="ocr_extracted_row",
            target_id=row.id,
            actor=actor,
            before_value=before,
            after_value={
                key: (
                    value.isoformat()
                    if isinstance(value, date)
                    else str(value)
                    if isinstance(value, Decimal)
                    else value
                )
                for key, value in updates.items()
            },
        )
        return row

    def confirm_rows(self, row_ids: list[str], actor: str) -> int:
        if not row_ids:
            raise ValueError("row_ids is required")

        rejection_reasons: dict[str, list[str]] = {}
        rows_to_confirm: list[OcrExtractedRow] = []

        for row_id in row_ids:
            row = self.session.get(OcrExtractedRow, row_id)
            if row is None:
                rejection_reasons[row_id] = ["not_found"]
                continue
            reasons = get_confirm_rejection_reasons(row)
            if reasons:
                rejection_reasons[row_id] = reasons
            else:
                rows_to_confirm.append(row)

        if rejection_reasons:
            raise OcrConfirmRejectedError(rejection_reasons)

        now = datetime.now(timezone.utc)
        for row in rows_to_confirm:
            row.status = "confirmed"
            row.confirmed_at = now
            row.confirmed_by = actor

        if rows_to_confirm:
            self.audit.log(
                "ocr_rows_confirmed",
                target_type="ocr_extracted_row",
                target_id=row_ids[0],
                actor=actor,
                after_value={"count": len(rows_to_confirm), "row_ids": row_ids},
            )
        return len(rows_to_confirm)

    def void_row(self, row_id: str, *, reason: str, actor: str) -> OcrExtractedRow:
        """OCR確定済みの精算行を無効化する（誤アップロード・誤確定・途中精算等）。

        voided ≠ excluded: voidedはOCR行そのものを無効とし、削除はしないが在庫照合
        からも除外される。excluded_reasonはOCRとしては正しいが在庫照合対象から
        外す場合に使う（set_reconciliation_eligible参照）。
        """
        row = self.session.get(OcrExtractedRow, row_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Row not found")
        if not reason or not reason.strip():
            raise ValueError("void_reason is required")

        before_status = row.status
        row.voided_at = datetime.now(timezone.utc)
        row.voided_by = actor
        row.void_reason = reason.strip()
        row.reconciliation_eligible = False

        self.audit.log(
            "ocr_row_voided",
            target_type="ocr_extracted_row",
            target_id=row.id,
            actor=actor,
            before_value={"status": before_status},
            after_value={"void_reason": row.void_reason},
        )
        return row

    def set_reconciliation_eligible(
        self,
        row_id: str,
        *,
        eligible: bool,
        excluded_reason: str | None,
        actor: str,
    ) -> OcrExtractedRow:
        """在庫照合対象としての採用/除外を切り替える(opt-out方式。既定はTrue)。

        DB側の部分ユニーク制約(uq_ocr_settlement_reconciliation_target)が同一
        branch_id x terminal_short_id x work_date で複数行がeligible=trueになる
        事故を防ぐ最終防衛線。IntegrityErrorはValueErrorとして呼び出し元に伝える。
        """
        row = self.session.get(OcrExtractedRow, row_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Row not found")
        if row.source_type != "paygate_settlement":
            raise ValueError("reconciliation_eligible is only applicable to paygate_settlement rows")
        if not eligible and not (excluded_reason and excluded_reason.strip()):
            raise ValueError("excluded_reason is required when eligible=False")

        before = {"reconciliation_eligible": row.reconciliation_eligible}
        row.reconciliation_eligible = eligible
        row.excluded_reason = excluded_reason.strip() if (excluded_reason and not eligible) else None

        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError(
                "同一の支社・端末識別番号・稼働日で既に在庫照合対象の行が存在します。"
                "先に既存行を除外(または無効化)してください。"
            ) from exc

        self.audit.log(
            "ocr_row_reconciliation_eligibility_changed",
            target_type="ocr_extracted_row",
            target_id=row.id,
            actor=actor,
            before_value=before,
            after_value={"reconciliation_eligible": eligible, "excluded_reason": row.excluded_reason},
        )
        return row

    def delete_rows(self, row_ids: list[str], *, actor: str) -> int:
        if not row_ids:
            raise ValueError("row_ids is required")

        now = datetime.now(timezone.utc)
        deleted = 0
        for row_id in row_ids:
            row = self.session.get(OcrExtractedRow, row_id)
            if row is None or row.deleted_at is not None:
                continue
            row.deleted_at = now
            deleted += 1
            self.audit.log(
                "ocr_row_deleted",
                target_type="ocr_extracted_row",
                target_id=row.id,
                actor=actor,
                before_value={"status": row.status, "period_key": row.period_key},
            )

        if deleted:
            self.audit.log(
                "ocr_rows_deleted",
                target_type="ocr_extracted_row",
                target_id=row_ids[0],
                actor=actor,
                after_value={"count": deleted, "row_ids": row_ids},
            )
        return deleted

    def monthly_summary(self) -> list[dict]:
        rows = self.session.execute(
            select(
                OcrExtractedRow.period_key,
                OcrExtractedRow.source_type,
                func.count(OcrExtractedRow.id),
                func.coalesce(func.sum(OcrExtractedRow.amount), 0),
            )
            .where(
                OcrExtractedRow.deleted_at.is_(None),
                OcrExtractedRow.period_key.is_not(None),
            )
            .group_by(OcrExtractedRow.period_key, OcrExtractedRow.source_type)
            .order_by(OcrExtractedRow.period_key.desc())
        ).all()

        return [
            {
                "period_key": period_key,
                "source_type": source_type,
                "row_count": row_count,
                "total_amount": str(total_amount),
            }
            for period_key, source_type, row_count, total_amount in rows
        ]

    def export_csv(
        self,
        *,
        period_key: str | None,
        source_type: str | None,
        actor: str,
    ) -> tuple[str, OcrMonthlyExport | None]:
        query = select(OcrExtractedRow).where(OcrExtractedRow.deleted_at.is_(None))
        if period_key:
            query = query.where(OcrExtractedRow.period_key == period_key)
        if source_type:
            query = query.where(OcrExtractedRow.source_type == source_type)
        rows = self.session.execute(
            query.order_by(OcrExtractedRow.record_date, OcrExtractedRow.record_time)
        ).scalars().all()

        csv_content = rows_to_csv(list(rows))
        export_record = None
        if period_key:
            total = sum((row.amount or Decimal(0)) for row in rows)
            export_type = source_type or "all"
            storage_key = f"exports/{period_key}/{export_type}_{generate_ulid()}.csv"
            self.storage.save_bytes(storage_key, csv_content.encode("utf-8-sig"))
            export_record = OcrMonthlyExport(
                id=generate_ulid(),
                period_key=period_key,
                export_type=export_type,
                storage_key=storage_key,
                row_count=len(rows),
                total_amount=total,
                generated_by=actor,
            )
            self.session.add(export_record)

        self.audit.log(
            "ocr_csv_exported",
            target_type="ocr_monthly_export",
            target_id=export_record.id if export_record else None,
            actor=actor,
            after_value={
                "period_key": period_key,
                "source_type": source_type,
                "row_count": len(rows),
            },
        )
        return csv_content, export_record

    def export_settlement_csv(
        self,
        *,
        period_key: str | None,
        actor: str,
    ) -> str:
        """paygate_settlement 専用の拡張CSV出力（既存25列CSVとは独立。計画書 v4 §2.7）。"""
        query = select(OcrExtractedRow).where(
            OcrExtractedRow.deleted_at.is_(None),
            OcrExtractedRow.source_type == "paygate_settlement",
        )
        if period_key:
            query = query.where(OcrExtractedRow.period_key == period_key)
        rows = self.session.execute(
            query.order_by(OcrExtractedRow.work_date, OcrExtractedRow.record_time)
        ).scalars().all()

        csv_content = settlement_rows_to_csv(list(rows))
        self.audit.log(
            "ocr_settlement_csv_exported",
            target_type="ocr_monthly_export",
            target_id=None,
            actor=actor,
            after_value={"period_key": period_key, "row_count": len(rows)},
        )
        return csv_content

    def run_reconciliation(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        column_mapping: dict[str, str],
        period_key: str | None,
        uploaded_by: str,
    ) -> OcrReconciliationBatch:
        hq_rows = parse_hq_csv(file_bytes)
        query = select(OcrExtractedRow).where(OcrExtractedRow.deleted_at.is_(None))
        if period_key:
            query = query.where(OcrExtractedRow.period_key == period_key)
        ocr_rows = list(self.session.execute(query).scalars().all())

        matches = reconcile_rows(ocr_rows, hq_rows, column_mapping)
        summary = summarize_matches(matches)

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        batch = OcrReconciliationBatch(
            id=generate_ulid(),
            period_key=period_key,
            file_name=file_name,
            file_hash=file_hash,
            column_mapping=column_mapping,
            storage_key=f"reconciliation/{generate_ulid()}.csv",
            status="completed",
            uploaded_by=uploaded_by,
            row_count=len(hq_rows),
            matched_count=summary.get("matched", 0),
            unmatched_ocr_count=summary.get("ocr_only", 0),
            unmatched_hq_count=summary.get("hq_only", 0),
            amount_diff_count=summary.get("amount_diff", 0),
        )
        self.storage.save_bytes(batch.storage_key, file_bytes)
        self.session.add(batch)
        self.session.flush()

        for match in matches:
            self.session.add(
                OcrReconciliationResult(
                    id=generate_ulid(),
                    batch_id=batch.id,
                    match_status=match.match_status,
                    ocr_row_id=match.ocr_row_id,
                    hq_row_index=match.hq_row_index,
                    hq_payload=match.hq_payload,
                    amount_diff=match.amount_diff,
                    notes=match.notes,
                )
            )

        self.audit.log(
            "ocr_reconciliation_completed",
            target_type="ocr_reconciliation_batch",
            target_id=batch.id,
            actor=uploaded_by,
            after_value=summary,
        )
        return batch

    def link_row_to_entity(
        self,
        row_id: str,
        *,
        linked_entity_type: str,
        linked_entity_id: str,
        project_id: str | None,
        actor: str,
    ) -> OcrExtractedRow:
        row = self.session.get(OcrExtractedRow, row_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Row not found")
        row.linked_entity_type = linked_entity_type
        row.linked_entity_id = linked_entity_id
        if project_id:
            row.project_id = project_id
        self.audit.log(
            "ocr_row_linked",
            target_type="ocr_extracted_row",
            target_id=row.id,
            actor=actor,
            after_value={
                "linked_entity_type": linked_entity_type,
                "linked_entity_id": linked_entity_id,
                "project_id": project_id,
            },
        )
        return row

    def compare_with_self_reports(self, *, period_key: str, project_id: str | None = None) -> dict:
        """Phase 3 placeholder: sales_reports ORM/API 未整備のため OCR 集計のみ返す。"""
        query = select(OcrExtractedRow).where(
            OcrExtractedRow.deleted_at.is_(None),
            OcrExtractedRow.period_key == period_key,
            OcrExtractedRow.status == "confirmed",
        )
        if project_id:
            query = query.where(OcrExtractedRow.project_id == project_id)
        ocr_rows = list(self.session.execute(query).scalars().all())
        ocr_total = sum((row.amount or Decimal(0)) for row in ocr_rows)
        linked_count = sum(1 for row in ocr_rows if row.linked_entity_id)

        return {
            "period_key": period_key,
            "project_id": project_id,
            "ocr_row_count": len(ocr_rows),
            "ocr_total_amount": str(ocr_total),
            "linked_count": linked_count,
            "self_report_available": False,
            "message": "sales_reports API は未実装のため、OCR 集計のみ表示しています。",
        }
