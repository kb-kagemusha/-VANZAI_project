"""Inventory reconciliation service (PAYGATE精算 在庫照合).

計画書 v4 Phase 2b。OCR確定済み・在庫照合対象(reconciliation_eligible=true)の
paygate_settlement行と、事務局が入力する実在庫記録(InventorySnapshot)を
(branch_id, terminal_short_id, work_date) で突合し、差異を検知する。

承認フローは実装しない（計画書 v4 §2 確定方針）。confirmed_by は entered_by と
同一人物でも良い。月次で事務局責任者が adjustment_reason を目視レビューする運用は
docs/ops/OCR_INVENTORY_RUNBOOK.md に記載する。
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.inventory_reconciliation import (
    InventoryReconciliationBatch,
    InventoryReconciliationResult,
    InventorySnapshot,
)
from src.models.ocr import OcrExtractedRow
from src.services.audit import AuditService

DIFF_REASON_CATEGORIES = frozenset(
    {
        "ocr_error",
        "inventory_input_error",
        "receipt_missing",
        "image_duplicate",
        "partial_settlement",
        "terminal_mismatch",
        "staff_mismatch",
        "loss_damage",
        "unclassified",
    }
)


class InventoryReconciliationService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    # --- Inventory snapshots (実在庫記録) -----------------------------------

    def create_snapshot(
        self,
        *,
        branch_id: str,
        terminal_short_id: str,
        work_date: date,
        staff_id: str | None,
        opening_count: int,
        closing_count: int,
        adjustment_count: int,
        adjustment_reason: str | None,
        note: str | None,
        actor: str,
    ) -> InventorySnapshot:
        existing = self.session.execute(
            select(InventorySnapshot).where(
                InventorySnapshot.branch_id == branch_id,
                InventorySnapshot.terminal_short_id == terminal_short_id,
                InventorySnapshot.work_date == work_date,
                InventorySnapshot.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(
                "同一の支社・端末識別番号・稼働日の実在庫記録は既に存在します。更新APIを使用してください。"
            )
        if adjustment_count != 0 and not (adjustment_reason and adjustment_reason.strip()):
            raise ValueError("adjustment_countが0以外の場合はadjustment_reasonが必須です")

        now = datetime.now(timezone.utc)
        snapshot = InventorySnapshot(
            id=generate_ulid(),
            branch_id=branch_id,
            terminal_short_id=terminal_short_id,
            work_date=work_date,
            staff_id=staff_id,
            opening_count=opening_count,
            closing_count=closing_count,
            adjustment_count=adjustment_count,
            adjustment_reason=adjustment_reason,
            entered_by=actor,
            entered_at=now,
            confirmed_by=actor,
            confirmed_at=now,
            note=note,
        )
        self.session.add(snapshot)
        self.session.flush()
        self.audit.log(
            "inventory_snapshot_created",
            target_type="inventory_snapshot",
            target_id=snapshot.id,
            actor=actor,
            after_value={
                "branch_id": branch_id,
                "terminal_short_id": terminal_short_id,
                "work_date": work_date.isoformat(),
                "opening_count": opening_count,
                "closing_count": closing_count,
                "adjustment_count": adjustment_count,
            },
        )
        return snapshot

    def update_snapshot(self, snapshot_id: str, updates: dict, *, actor: str) -> InventorySnapshot:
        snapshot = self.session.get(InventorySnapshot, snapshot_id)
        if snapshot is None or snapshot.deleted_at is not None:
            raise ValueError("Snapshot not found")

        before = {
            "opening_count": snapshot.opening_count,
            "closing_count": snapshot.closing_count,
            "adjustment_count": snapshot.adjustment_count,
            "adjustment_reason": snapshot.adjustment_reason,
        }
        for key, value in updates.items():
            if value is None and key not in {"adjustment_reason", "note", "staff_id"}:
                continue
            if hasattr(snapshot, key):
                setattr(snapshot, key, value)

        new_adjustment = snapshot.adjustment_count
        if new_adjustment != 0 and not (snapshot.adjustment_reason and snapshot.adjustment_reason.strip()):
            raise ValueError("adjustment_countが0以外の場合はadjustment_reasonが必須です")

        snapshot.confirmed_by = actor
        snapshot.confirmed_at = datetime.now(timezone.utc)

        self.audit.log(
            "inventory_snapshot_updated",
            target_type="inventory_snapshot",
            target_id=snapshot.id,
            actor=actor,
            before_value=before,
            after_value={
                "opening_count": snapshot.opening_count,
                "closing_count": snapshot.closing_count,
                "adjustment_count": snapshot.adjustment_count,
                "adjustment_reason": snapshot.adjustment_reason,
            },
        )
        return snapshot

    def delete_snapshot(self, snapshot_id: str, *, actor: str) -> None:
        snapshot = self.session.get(InventorySnapshot, snapshot_id)
        if snapshot is None or snapshot.deleted_at is not None:
            raise ValueError("Snapshot not found")
        snapshot.deleted_at = datetime.now(timezone.utc)
        self.audit.log(
            "inventory_snapshot_deleted",
            target_type="inventory_snapshot",
            target_id=snapshot.id,
            actor=actor,
        )

    def list_snapshots(
        self,
        *,
        branch_id: str | None = None,
        terminal_short_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[InventorySnapshot], int]:
        from sqlalchemy import func

        query = select(InventorySnapshot).where(InventorySnapshot.deleted_at.is_(None))
        if branch_id:
            query = query.where(InventorySnapshot.branch_id == branch_id)
        if terminal_short_id:
            query = query.where(InventorySnapshot.terminal_short_id == terminal_short_id)
        if date_from:
            query = query.where(InventorySnapshot.work_date >= date_from)
        if date_to:
            query = query.where(InventorySnapshot.work_date <= date_to)
        total = self.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        items = self.session.execute(
            query.order_by(InventorySnapshot.work_date.desc()).offset(offset).limit(limit)
        ).scalars().all()
        return list(items), total

    # --- Reconciliation run --------------------------------------------------

    def run_reconciliation(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
        period_key: str | None,
        executed_by: str,
    ) -> InventoryReconciliationBatch:
        if date_from is None and date_to is None and not period_key:
            raise ValueError("date_from/date_to または period_key のいずれかを指定してください")

        if period_key and not (date_from or date_to):
            date_from, date_to = _period_key_to_date_range(period_key)

        snapshot_query = select(InventorySnapshot).where(InventorySnapshot.deleted_at.is_(None))
        if date_from:
            snapshot_query = snapshot_query.where(InventorySnapshot.work_date >= date_from)
        if date_to:
            snapshot_query = snapshot_query.where(InventorySnapshot.work_date <= date_to)
        snapshots = list(self.session.execute(snapshot_query).scalars().all())

        ocr_query = select(OcrExtractedRow).where(
            OcrExtractedRow.source_type == "paygate_settlement",
            OcrExtractedRow.deleted_at.is_(None),
            OcrExtractedRow.status == "confirmed",
            OcrExtractedRow.reconciliation_eligible.is_(True),
            OcrExtractedRow.voided_at.is_(None),
            OcrExtractedRow.work_date.is_not(None),
        )
        if date_from:
            ocr_query = ocr_query.where(OcrExtractedRow.work_date >= date_from)
        if date_to:
            ocr_query = ocr_query.where(OcrExtractedRow.work_date <= date_to)
        ocr_rows = list(self.session.execute(ocr_query).scalars().all())

        ocr_by_key: dict[tuple[str, str, date], list[OcrExtractedRow]] = {}
        for row in ocr_rows:
            key = (row.branch_id or "UNASSIGNED", row.terminal_short_id or "", row.work_date)
            ocr_by_key.setdefault(key, []).append(row)

        batch = InventoryReconciliationBatch(
            id=generate_ulid(),
            period_key=period_key,
            date_from=date_from,
            date_to=date_to,
            executed_by=executed_by,
        )
        self.session.add(batch)
        self.session.flush()

        counters = {
            "total": 0,
            "matched": 0,
            "adjusted_matched": 0,
            "count_mismatch": 0,
            "sales_only": 0,
            "inventory_only": 0,
            "excluded": 0,
        }

        matched_keys: set[tuple[str, str, date]] = set()

        for snapshot in snapshots:
            key = (snapshot.branch_id, snapshot.terminal_short_id, snapshot.work_date)
            candidates = ocr_by_key.get(key, [])
            inventory_decrease = snapshot.inventory_decrease

            if not candidates:
                result = InventoryReconciliationResult(
                    id=generate_ulid(),
                    batch_id=batch.id,
                    branch_id=snapshot.branch_id,
                    terminal_short_id=snapshot.terminal_short_id,
                    work_date=snapshot.work_date,
                    inventory_snapshot_id=snapshot.id,
                    ocr_transaction_count=None,
                    inventory_decrease=inventory_decrease,
                    diff=None,
                    match_status="inventory_only",
                    diff_reason_category=None,
                    notes=None,
                )
                counters["inventory_only"] += 1
            else:
                # DB側の部分ユニーク制約により通常は1件だが、念のため防御的に処理する。
                ocr_row = candidates[0]
                matched_keys.add(key)
                diff = ocr_row.transaction_count - inventory_decrease if ocr_row.transaction_count is not None else None
                if diff == 0 and snapshot.adjustment_count != 0 and snapshot.adjustment_reason:
                    match_status = "adjusted_matched"
                    counters["adjusted_matched"] += 1
                elif diff == 0:
                    match_status = "matched"
                    counters["matched"] += 1
                else:
                    match_status = "count_mismatch"
                    counters["count_mismatch"] += 1
                anomaly_note = (
                    f"同一キーに{len(candidates)}件のOCR確定行が存在します（想定外・要確認）"
                    if len(candidates) > 1
                    else None
                )
                result = InventoryReconciliationResult(
                    id=generate_ulid(),
                    batch_id=batch.id,
                    branch_id=snapshot.branch_id,
                    terminal_short_id=snapshot.terminal_short_id,
                    work_date=snapshot.work_date,
                    ocr_row_id=ocr_row.id,
                    inventory_snapshot_id=snapshot.id,
                    ocr_transaction_count=ocr_row.transaction_count,
                    inventory_decrease=inventory_decrease,
                    diff=diff,
                    match_status=match_status,
                    diff_reason_category=None,
                    notes=anomaly_note,
                )
            self.session.add(result)
            counters["total"] += 1

        for key, candidates in ocr_by_key.items():
            if key in matched_keys:
                continue
            branch_id, terminal_short_id, work_date = key
            for ocr_row in candidates:
                result = InventoryReconciliationResult(
                    id=generate_ulid(),
                    batch_id=batch.id,
                    branch_id=branch_id,
                    terminal_short_id=terminal_short_id,
                    work_date=work_date,
                    ocr_row_id=ocr_row.id,
                    inventory_snapshot_id=None,
                    ocr_transaction_count=ocr_row.transaction_count,
                    inventory_decrease=None,
                    diff=None,
                    match_status="sales_only",
                    diff_reason_category=None,
                    notes=None,
                )
                self.session.add(result)
                counters["total"] += 1
                counters["sales_only"] += 1

        batch.total_count = counters["total"]
        batch.matched_count = counters["matched"]
        batch.adjusted_matched_count = counters["adjusted_matched"]
        batch.count_mismatch_count = counters["count_mismatch"]
        batch.sales_only_count = counters["sales_only"]
        batch.inventory_only_count = counters["inventory_only"]
        batch.excluded_count = counters["excluded"]

        self.audit.log(
            "inventory_reconciliation_run",
            target_type="inventory_reconciliation_batch",
            target_id=batch.id,
            actor=executed_by,
            after_value=dict(counters),
        )
        return batch

    def get_batch(self, batch_id: str) -> InventoryReconciliationBatch | None:
        return self.session.get(InventoryReconciliationBatch, batch_id)

    def list_batch_results(self, batch_id: str) -> list[InventoryReconciliationResult]:
        return list(
            self.session.execute(
                select(InventoryReconciliationResult)
                .where(InventoryReconciliationResult.batch_id == batch_id)
                .order_by(InventoryReconciliationResult.work_date.desc())
            ).scalars().all()
        )

    def update_result(self, result_id: str, updates: dict, *, actor: str) -> InventoryReconciliationResult:
        result = self.session.get(InventoryReconciliationResult, result_id)
        if result is None:
            raise ValueError("Result not found")
        diff_reason_category = updates.get("diff_reason_category")
        if diff_reason_category is not None and diff_reason_category not in DIFF_REASON_CATEGORIES:
            raise ValueError(f"Unknown diff_reason_category: {diff_reason_category}")

        before = {"match_status": result.match_status, "diff_reason_category": result.diff_reason_category}
        for key, value in updates.items():
            if hasattr(result, key) and value is not None:
                setattr(result, key, value)

        self.audit.log(
            "inventory_reconciliation_result_updated",
            target_type="inventory_reconciliation_result",
            target_id=result.id,
            actor=actor,
            before_value=before,
            after_value=updates,
        )
        return result


def _period_key_to_date_range(period_key: str) -> tuple[date, date]:
    """"YYYYMM" -> (月初日, 月末日). DB方言に依存しないよう、Python側で範囲へ変換する。"""
    import calendar

    if len(period_key) != 6 or not period_key.isdigit():
        raise ValueError("period_key must be YYYYMM")
    year = int(period_key[:4])
    month = int(period_key[4:6])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)
