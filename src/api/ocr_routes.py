"""OCR receipt parsing API routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.schemas import (
    OcrExtractedRowItem,
    OcrExtractedRowListResponse,
    OcrExtractedRowUpdateRequest,
    OcrMonthlySummaryItem,
    OcrMonthlySummaryResponse,
    OcrParseJobRequest,
    OcrParseJobResponse,
    OcrReconciliationBatchResponse,
    OcrReconciliationResultItem,
    OcrRowLinkRequest,
    OcrRowsConfirmRequest,
    OcrRowsConfirmResponse,
    OcrSelfReportCompareResponse,
    OcrSourceImageItem,
    OcrSourceImageListResponse,
)
from src.models.master import User
from src.models.ocr import OcrExtractedRow, OcrParseJob, OcrReconciliationResult, OcrSourceImage
from src.models.enums import UserRole
from src.services.ocr.parsers.registry import VALID_SOURCE_TYPES
from src.services.ocr_service import OcrService

router = APIRouter(prefix="/api/ocr", tags=["OCR Receipt"])

_OCR_ROLES = {UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ACCOUNTING.value}


def _ensure_ocr_permission(user: User) -> None:
    if user.role not in _OCR_ROLES:
        raise HTTPException(status_code=403, detail="OCR機能へのアクセス権限がありません")


def _image_to_item(image: OcrSourceImage) -> OcrSourceImageItem:
    return OcrSourceImageItem(
        id=image.id,
        source_type=image.source_type,
        original_filename=image.original_filename,
        sha256=image.sha256,
        mime_type=image.mime_type,
        size_bytes=image.size_bytes,
        period_key=image.period_key,
        parse_status=image.parse_status,
        uploaded_by=image.uploaded_by,
        last_job_id=image.last_job_id,
        error_message=image.error_message,
        created_at=image.created_at,
    )


def _row_to_item(row: OcrExtractedRow) -> OcrExtractedRowItem:
    return OcrExtractedRowItem(
        id=row.id,
        source_image_id=row.source_image_id,
        parse_job_id=row.parse_job_id,
        source_type=row.source_type,
        period_key=row.period_key,
        record_date=row.record_date,
        record_time=row.record_time,
        amount=row.amount,
        currency=row.currency,
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
        confidence=row.confidence,
        status=row.status,
        validation_errors=row.validation_errors,
        project_id=row.project_id,
        report_date=row.report_date,
        linked_entity_type=row.linked_entity_type,
        linked_entity_id=row.linked_entity_id,
        confirmed_at=row.confirmed_at,
        confirmed_by=row.confirmed_by,
    )


@router.post("/images", response_model=OcrSourceImageItem)
async def upload_ocr_image(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    if source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type: {source_type}")

    content = await file.read()
    service = OcrService(db)
    try:
        image = service.upload_image(
            file_bytes=content,
            file_name=file.filename,
            source_type=source_type,
            uploaded_by=current_user.username,
            mime_type=file.content_type,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _image_to_item(image)


@router.get("/images", response_model=OcrSourceImageListResponse)
def list_ocr_images(
    source_type: str | None = Query(None),
    parse_status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    items, total = service.list_images(
        source_type=source_type,
        parse_status=parse_status,
        limit=limit,
        offset=offset,
    )
    return OcrSourceImageListResponse(items=[_image_to_item(i) for i in items], total=total)


@router.post("/jobs/parse", response_model=OcrParseJobResponse)
def parse_ocr_images(
    body: OcrParseJobRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    try:
        job = service.parse_images(image_ids=body.image_ids, executed_by=current_user.username)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return OcrParseJobResponse(
        id=job.id,
        status=job.status,
        image_count=job.image_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        row_count=job.row_count,
        executed_by=job.executed_by,
        completed_at=job.completed_at,
    )


@router.get("/jobs/{job_id}", response_model=OcrParseJobResponse)
def get_ocr_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    job = db.get(OcrParseJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return OcrParseJobResponse(
        id=job.id,
        status=job.status,
        image_count=job.image_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        row_count=job.row_count,
        executed_by=job.executed_by,
        completed_at=job.completed_at,
    )


@router.get("/rows", response_model=OcrExtractedRowListResponse)
def list_ocr_rows(
    period_key: str | None = Query(None),
    source_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    items, total = service.list_rows(
        period_key=period_key,
        source_type=source_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return OcrExtractedRowListResponse(items=[_row_to_item(r) for r in items], total=total)


@router.patch("/rows/{row_id}", response_model=OcrExtractedRowItem)
def update_ocr_row(
    row_id: str,
    body: OcrExtractedRowUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    try:
        row = service.update_row(
            row_id,
            body.model_dump(exclude_unset=True),
            current_user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _row_to_item(row)


@router.post("/rows/confirm", response_model=OcrRowsConfirmResponse)
def confirm_ocr_rows(
    body: OcrRowsConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    count = service.confirm_rows(body.row_ids, current_user.username)
    db.commit()
    return OcrRowsConfirmResponse(confirmed_count=count)


@router.get("/monthly-summary", response_model=OcrMonthlySummaryResponse)
def get_ocr_monthly_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    items = [
        OcrMonthlySummaryItem(**item)
        for item in service.monthly_summary()
    ]
    return OcrMonthlySummaryResponse(items=items)


@router.get("/exports/{period_key}.csv")
def download_ocr_csv(
    period_key: str,
    source_type: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    if len(period_key) != 6 or not period_key.isdigit():
        raise HTTPException(status_code=400, detail="period_key must be YYYYMM")

    service = OcrService(db)
    csv_content, _ = service.export_csv(
        period_key=period_key,
        source_type=source_type,
        actor=current_user.username,
    )
    db.commit()

    filename = f"ocr_{period_key}"
    if source_type:
        filename += f"_{source_type}"
    filename += ".csv"

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exports/all.csv")
def download_all_ocr_csv(
    source_type: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    csv_content, _ = service.export_csv(
        period_key=None,
        source_type=source_type,
        actor=current_user.username,
    )
    db.commit()
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ocr_all.csv"'},
    )


@router.post("/reconciliation", response_model=OcrReconciliationBatchResponse)
async def run_ocr_reconciliation(
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
    period_key: str | None = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    try:
        mapping = json.loads(column_mapping)
        if not isinstance(mapping, dict):
            raise ValueError("column_mapping must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid column_mapping: {exc}") from exc

    content = await file.read()
    service = OcrService(db)
    try:
        batch = service.run_reconciliation(
            file_bytes=content,
            file_name=file.filename or "hq.csv",
            column_mapping=mapping,
            period_key=period_key,
            uploaded_by=current_user.username,
        )
        results = db.execute(
            select(OcrReconciliationResult).where(OcrReconciliationResult.batch_id == batch.id)
        ).scalars().all()
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OcrReconciliationBatchResponse(
        id=batch.id,
        period_key=batch.period_key,
        file_name=batch.file_name,
        row_count=batch.row_count,
        matched_count=batch.matched_count,
        unmatched_ocr_count=batch.unmatched_ocr_count,
        unmatched_hq_count=batch.unmatched_hq_count,
        amount_diff_count=batch.amount_diff_count,
        results=[
            OcrReconciliationResultItem(
                id=r.id,
                match_status=r.match_status,
                ocr_row_id=r.ocr_row_id,
                hq_row_index=r.hq_row_index,
                hq_payload=r.hq_payload,
                amount_diff=r.amount_diff,
                notes=r.notes,
            )
            for r in results
        ],
    )


@router.post("/rows/{row_id}/link", response_model=OcrExtractedRowItem)
def link_ocr_row(
    row_id: str,
    body: OcrRowLinkRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    try:
        row = service.link_row_to_entity(
            row_id,
            linked_entity_type=body.linked_entity_type,
            linked_entity_id=body.linked_entity_id,
            project_id=body.project_id,
            actor=current_user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _row_to_item(row)


@router.get("/compare/self-report", response_model=OcrSelfReportCompareResponse)
def compare_ocr_with_self_report(
    period_key: str = Query(..., min_length=6, max_length=6),
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_ocr_permission(current_user)
    service = OcrService(db)
    result = service.compare_with_self_reports(period_key=period_key, project_id=project_id)
    return OcrSelfReportCompareResponse(**result)
