"""有効なダミー依頼の受諾参加日から、欠けたLINE用予定を復元する。"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from src.models.master import User
from src.models.order_request import OrderRequestDocument as Document, OrderRequestVersion as Version
from src.models.line_daily import OrderRequestSeries, WorkerScheduleEntry
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.participation_calendar import build


def target_series(db):
    rows = db.query(OrderRequestSeries.id).join(
        Version, Version.id == OrderRequestSeries.answerable_version_id,
    ).join(Document, Document.id == Version.document_id).filter(
        Document.kind == "test", Document.deleted_at.is_(None), Version.status == "confirmed",
        Version.counterparty_note.like("calendar-demo-%"),
    ).all()
    return {row.id for row in rows}


def comparison(db, series_ids):
    expected = set()
    for day in build(db, test_only=True):
        for event in day["events"]:
            if event["series_id"] not in series_ids:
                continue
            for bucket, status in (("ok", "active"), ("changing", "changing")):
                expected.update((event["series_id"], p["worker_id"], day["date"], status) for p in event[bucket])
    actual = {(r.series_id, r.worker_id, r.work_date.isoformat(), r.status)
        for r in ws.visible_schedule_entries(db).filter(
            WorkerScheduleEntry.series_id.in_(series_ids), WorkerScheduleEntry.status.in_(("active", "changing")),
        )}
    return expected, actual


def repair(db, *, apply=False):
    if apply and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    series_ids = target_series(db)
    if apply:
        for sid in sorted(series_ids):
            ws.lock_series(db, sid)
        # ロック待ち中に取消・一覧除外された系列を操作しない。
        series_ids &= target_series(db)
    expected, actual = comparison(db, series_ids)
    before = {"demo_series": len(series_ids), "missing_worker_days": len(expected - actual),
        "unexpected_worker_days": len(actual - expected)}
    if not apply:
        return before
    actor = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    for sid in sorted(series_ids):
        ws.rebuild_series(db, sid, actor=actor.username)
    db.flush()
    after_expected, after_actual = comparison(db, series_ids)
    if after_expected != expected or after_actual != after_expected:
        raise RuntimeError("参加日とLINE用予定が一致しないため全変更をロールバックします")
    if before["missing_worker_days"] or before["unexpected_worker_days"]:
        AuditService(db).log("demo_schedule_gaps_repaired", target_type="calendar_demo",
            target_id="demo-schedule-gaps-v1", actor=actor.username, actor_role=actor.role,
            reason="ダミー受諾後の予定再構築漏れを修正。元回答・参加日・版・会計は変更しない",
            before_value=before, after_value={"missing_worker_days": 0, "unexpected_worker_days": 0})
    return {**before, "remaining_missing_worker_days": len(after_expected - after_actual),
        "remaining_unexpected_worker_days": len(after_actual - after_expected)}


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
