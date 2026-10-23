"""置換済みダミー依頼の派生予定だけを再構築。受諾・PDF・金額は保持。"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from src.models.master import User
from src.models.transaction import AuditLog
from src.models.order_request import OrderRequestDocument, OrderRequestVersion
from src.models.line_daily import WorkerScheduleEntry
from src.services import worker_schedule as ws
from src.services.audit import AuditService


def targets(db):
    ids = db.query(AuditLog.target_id).filter(
        AuditLog.target_type == "order_request_document",
        AuditLog.action.in_(("calendar_demo_rebalanced", "calendar_demo_daily_variation_replaced")),
    )
    documents = db.query(OrderRequestDocument).filter(
        OrderRequestDocument.id.in_(ids), OrderRequestDocument.kind == "test",
        OrderRequestDocument.deleted_at.is_not(None),
    ).all()
    series_ids = set()
    for document in documents:
        versions = db.query(OrderRequestVersion).filter_by(document_id=document.id).all()
        if any(not (v.counterparty_note or "").startswith("calendar-demo-") for v in versions):
            raise RuntimeError("ダミー以外の版を含むため中止しました")
        series_ids.update(v.series_id for v in versions if v.series_id)
    return documents, series_ids


def repair(db, *, apply=False):
    if apply and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    documents, series_ids = targets(db)
    ids = [d.id for d in documents]
    entries = db.query(WorkerScheduleEntry).filter(
        WorkerScheduleEntry.document_id.in_(ids), WorkerScheduleEntry.status.in_(("active", "changing")),
    )
    before = entries.count()
    if not apply:
        return {"archived_demo_documents": len(ids), "stale_schedule_entries": before}
    actor = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    for series_id in sorted(series_ids):
        ws.lock_series(db, series_id)
        ws.rebuild_series(db, series_id, actor=actor.username)
    db.flush()
    remaining = entries.count()
    if remaining:
        raise RuntimeError("旧予定が残っているため変更をロールバックします")
    if before:
        AuditService(db).log("archived_demo_schedules_repaired", target_type="calendar_demo",
            target_id="calendar-demo-archived-schedules-v1", actor=actor.username, actor_role=actor.role,
            reason="置換後もLINEに表示されていた削除済みダミー依頼の派生予定を解除",
            before_value={"stale_schedule_entries": before}, after_value={"active_entries_remaining": remaining})
    return {"archived_demo_documents": len(ids), "schedule_entries_removed": before, "active_entries_remaining": remaining}


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = repair(db, apply=args.apply)
        if args.apply:
            db.commit()
        print(json.dumps(result, ensure_ascii=False))
