"""Inventory reconciliation API routes (PAYGATE精算 在庫照合, 計画書 v4 Phase 2)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.schemas import (
    InventoryReconciliationBatchResponse,
    InventoryReconciliationResultItem,
    InventoryReconciliationResultUpdateRequest,
    InventoryReconciliationRunRequest,
    InventorySnapshotCreateRequest,
    InventorySnapshotItem,
    InventorySnapshotListResponse,
    InventorySnapshotUpdateRequest,
)
from src.models.master import User
from src.models.enums import UserRole
from src.services.inventory_reconciliation import InventoryReconciliationService

router = APIRouter(prefix="/api/inventory", tags=["Inventory Reconciliation"])

_INVENTORY_ROLES = {UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ACCOUNTING.value}


def _ensure_inventory_permission(user: User) -> None:
    if user.role not in _INVENTORY_ROLES:
        raise HTTPException(status_code=403, detail="在庫照合機能へのアクセス権限がありません")


def _snapshot_to_item(snapshot) -> InventorySnapshotItem:
    return InventorySnapshotItem(
        id=snapshot.id,
        branch_id=snapshot.branch_id,
        terminal_short_id=snapshot.terminal_short_id,
        work_date=snapshot.work_date,
        staff_id=snapshot.staff_id,
        opening_count=snapshot.opening_count,
        closing_count=snapshot.closing_count,
        adjustment_count=snapshot.adjustment_count,
        adjustment_reason=snapshot.adjustment_reason,
        inventory_decrease=snapshot.inventory_decrease,
        entered_by=snapshot.entered_by,
        entered_at=snapshot.entered_at,
        confirmed_by=snapshot.confirmed_by,
        confirmed_at=snapshot.confirmed_at,
        note=snapshot.note,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def _result_to_item(result) -> InventoryReconciliationResultItem:
    return InventoryReconciliationResultItem(
        id=result.id,
        batch_id=result.batch_id,
        branch_id=result.branch_id,
        terminal_short_id=result.terminal_short_id,
        work_date=result.work_date,
        ocr_row_id=result.ocr_row_id,
        inventory_snapshot_id=result.inventory_snapshot_id,
        ocr_transaction_count=result.ocr_transaction_count,
        inventory_decrease=result.inventory_decrease,
        diff=result.diff,
        match_status=result.match_status,
        diff_reason_category=result.diff_reason_category,
        notes=result.notes,
    )


def _batch_to_response(batch, results: list | None = None) -> InventoryReconciliationBatchResponse:
    return InventoryReconciliationBatchResponse(
        id=batch.id,
        period_key=batch.period_key,
        date_from=batch.date_from,
        date_to=batch.date_to,
        executed_by=batch.executed_by,
        total_count=batch.total_count,
        matched_count=batch.matched_count,
        adjusted_matched_count=batch.adjusted_matched_count,
        count_mismatch_count=batch.count_mismatch_count,
        sales_only_count=batch.sales_only_count,
        inventory_only_count=batch.inventory_only_count,
        excluded_count=batch.excluded_count,
        results=[_result_to_item(r) for r in results] if results is not None else [],
    )


@router.post("/snapshots", response_model=InventorySnapshotItem)
def create_inventory_snapshot(
    body: InventorySnapshotCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    try:
        snapshot = service.create_snapshot(
            branch_id=body.branch_id,
            terminal_short_id=body.terminal_short_id,
            work_date=body.work_date,
            staff_id=body.staff_id,
            opening_count=body.opening_count,
            closing_count=body.closing_count,
            adjustment_count=body.adjustment_count,
            adjustment_reason=body.adjustment_reason,
            note=body.note,
            actor=current_user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _snapshot_to_item(snapshot)


@router.get("/snapshots", response_model=InventorySnapshotListResponse)
def list_inventory_snapshots(
    branch_id: str | None = Query(None),
    terminal_short_id: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    items, total = service.list_snapshots(
        branch_id=branch_id,
        terminal_short_id=terminal_short_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return InventorySnapshotListResponse(items=[_snapshot_to_item(item) for item in items], total=total)


@router.patch("/snapshots/{snapshot_id}", response_model=InventorySnapshotItem)
def update_inventory_snapshot(
    snapshot_id: str,
    body: InventorySnapshotUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    try:
        snapshot = service.update_snapshot(
            snapshot_id,
            body.model_dump(exclude_unset=True),
            actor=current_user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    return _snapshot_to_item(snapshot)


@router.delete("/snapshots/{snapshot_id}")
def delete_inventory_snapshot(
    snapshot_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    try:
        service.delete_snapshot(snapshot_id, actor=current_user.username)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.post("/reconciliation/run", response_model=InventoryReconciliationBatchResponse)
def run_inventory_reconciliation(
    body: InventoryReconciliationRunRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    try:
        batch = service.run_reconciliation(
            date_from=body.date_from,
            date_to=body.date_to,
            period_key=body.period_key,
            executed_by=current_user.username,
        )
        results = service.list_batch_results(batch.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _batch_to_response(batch, results)


@router.get("/reconciliation/batches/{batch_id}", response_model=InventoryReconciliationBatchResponse)
def get_inventory_reconciliation_batch(
    batch_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    batch = service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    results = service.list_batch_results(batch_id)
    return _batch_to_response(batch, results)


@router.patch("/reconciliation/results/{result_id}", response_model=InventoryReconciliationResultItem)
def update_inventory_reconciliation_result(
    result_id: str,
    body: InventoryReconciliationResultUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_inventory_permission(current_user)
    service = InventoryReconciliationService(db)
    try:
        result = service.update_result(
            result_id,
            body.model_dump(exclude_unset=True),
            actor=current_user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc)) from exc
    return _result_to_item(result)
