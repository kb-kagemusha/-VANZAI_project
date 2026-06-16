"""OCR receipt orchestration service."""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, or_, select
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
from src.services.ocr.image_preprocess import preprocess_for_ocr
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.paddle_engine import run_ocr, run_ocr_from_text
from src.services.ocr.parsers.registry import VALID_SOURCE_TYPES, get_parser
from src.services.ocr.reconciliation import parse_hq_csv, reconcile_rows, summarize_matches
from src.services.ocr.export import rows_to_csv

from src.services.ocr.validation import validate_parsed_row

OCR_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _ocr_storage() -> ObjectStorage:
    return ObjectStorage(root=Path(os.getenv("OCR_STORAGE_ROOT", "storage/ocr")))


def build_ocr_object_key(image_id: str, original_name: str | None) -> str:
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        suffix = ".jpg"
    return f"images/{image_id}{suffix}"


def _parsed_to_db_row(
    parsed: ParsedOcrRow,
    *,
    source_image_id: str,
    parse_job_id: str,
) -> OcrExtractedRow:
    validation_errors = validate_parsed_row(parsed)
    return OcrExtractedRow(
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
        terminal_id=parsed.terminal_id,
        cash_sales=parsed.cash_sales,
        credit_sales=parsed.credit_sales,
        transaction_count=parsed.transaction_count,
        tax_included=parsed.tax_included,
        subtotal=parsed.subtotal,
        store_name=parsed.store_name,
        confidence=Decimal(str(round(parsed.confidence, 4))),
        status="pending_review",
        validation_errors=validation_errors or None,
        raw_payload=parsed.raw_payload,
        report_date=parsed.record_date,
    )


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
        raw_payload=row.raw_payload or {},
    )


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
    row.validation_errors = validate_parsed_row(parsed) or None
    row.raw_payload = parsed.raw_payload
    row.report_date = parsed.record_date


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
    ) -> OcrSourceImage:
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type: {source_type}")
        if not file_bytes:
            raise ValueError("Empty file")
        if len(file_bytes) > OCR_UPLOAD_MAX_BYTES:
            raise ValueError("File too large")

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        existing = self.session.execute(
            select(OcrSourceImage).where(
                OcrSourceImage.sha256 == sha256,
                OcrSourceImage.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing:
            return existing

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
        return image

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

    def parse_images(
        self,
        *,
        image_ids: list[str],
        executed_by: str,
        ocr_text_override: dict[str, str] | None = None,
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
                    array = preprocess_for_ocr(image_bytes)
                    ocr_result = run_ocr(array)

                parser = get_parser(image.source_type)
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
                        paygate_entries.append((image.id, parsed))
                else:
                    for parsed in parsed_rows:
                        db_row = _parsed_to_db_row(
                            parsed,
                            source_image_id=image.id,
                            parse_job_id=job.id,
                        )
                        self.session.add(db_row)
                        row_count += 1

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
        decimal_fields = {"amount", "cash_sales", "credit_sales", "tax_included", "subtotal"}
        int_fields = {"transaction_count"}

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

        parsed = ParsedOcrRow(
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
        )
        row.validation_errors = validate_parsed_row(parsed) or None

        self.audit.log(
            "ocr_row_updated",
            target_type="ocr_extracted_row",
            target_id=row.id,
            actor=actor,
            before_value=before,
            after_value=updates,
        )
        return row

    def confirm_rows(self, row_ids: list[str], actor: str) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for row_id in row_ids:
            row = self.session.get(OcrExtractedRow, row_id)
            if row is None or row.deleted_at is not None:
                continue
            row.status = "confirmed"
            row.confirmed_at = now
            row.confirmed_by = actor
            count += 1

        if count:
            self.audit.log(
                "ocr_rows_confirmed",
                target_type="ocr_extracted_row",
                target_id=row_ids[0] if row_ids else None,
                actor=actor,
                after_value={"count": count, "row_ids": row_ids},
            )
        return count

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
