"""Preview/apply three isolated test event copies for an explicitly selected worker.
No LINE client, actuals, assignments or financial records are created.
"""
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.master import User, Worker
from src.models.line_daily import OrderRequestSeries, WorkerScheduleEntry
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestService
from src.services.wake_test_notifications import active, lock, setting

PREFIX = "sample-participation-v1:"


def build_plan(db, query, worker_id=None):
    clean = lambda name: re.sub(r"\s+", "", name)
    workers = [w for w in db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).all()
               if (w.id == worker_id if worker_id else clean(query) in clean(w.name))]
    if len(workers) != 1:
        return {"candidates": [{"id": w.id, "name": w.name} for w in workers], "ready": False}
    worker = workers[0]
    batch = f"{PREFIX}{worker.id}:{ws.today_jst()}"
    existing = db.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.like(batch + ":%" )).all()
    if existing:
        return {"worker_id": worker.id, "name": worker.name, "ready": False, "already_created": [v.id for v in existing]}
    occupied = {r.work_date.isoformat() for r in ws.visible_schedule_entries(db).filter(
        WorkerScheduleEntry.worker_id == worker.id, WorkerScheduleEntry.status.in_(("active", "changing")))}
    candidates = []
    for version in db.query(OrderRequestVersion).join(OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id).join(
        OrderRequestSeries, OrderRequestSeries.answerable_version_id == OrderRequestVersion.id).filter(
        OrderRequestDocument.kind == "test", OrderRequestDocument.deleted_at.is_(None),
        OrderRequestVersion.status == "confirmed", OrderRequestVersion.dispatch_stopped.is_(False)).all():
        if (version.counterparty_note or "").startswith(PREFIX):
            continue
        days = sorted({d["work_date"] for d in ws.version_work_days(version)})
        if not days or len(days) > 4 or days[0] <= ws.today_jst().isoformat() or days[-1] > (ws.today_jst() + timedelta(days=45)).isoformat():
            continue
        candidates.append({"source_version_id": version.id, "event": ws.version_display(version)["project_name"], "dates": days})
    selected = []
    for row in sorted(candidates, key=lambda r: (r["dates"][0], len(r["dates"]), r["source_version_id"])):
        if occupied.intersection(row["dates"]):
            continue
        selected.append(row); occupied.update(row["dates"])
        if len(selected) == 3:
            break
    plan = {"worker_id": worker.id, "name": worker.name, "batch": batch, "events": selected, "ready": len(selected) == 3,
            "test_notifications_enabled": active(setting(db))}
    plan["token"] = hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return plan


def apply_plan(db, worker_id, token):
    lock(db)
    # Serialize per-worker runs and recheck the read-only preview under the lock.
    worker = db.query(Worker).filter_by(id=worker_id).with_for_update().one_or_none()
    if not worker:
        raise ValueError("Worker not found")
    plan = build_plan(db, "", worker_id)
    if plan.get("already_created"):
        return plan
    if not plan.get("ready") or plan.get("token") != token or plan["test_notifications_enabled"]:
        raise ValueError("Preview changed, insufficient non-overlapping events, or test notifications are enabled; no changes applied")
    for sid in sorted({db.get(OrderRequestVersion, event["source_version_id"]).series_id for event in plan["events"]}):
        ws.lock_series(db, sid)
    db.expire_all()
    plan = build_plan(db, "", worker_id)
    if not plan.get("ready") or plan.get("token") != token:
        raise ValueError("Source changed while waiting for locks; preview again")
    actor = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise ValueError("Active administrator required")
    service = OrderRequestService(db)
    results = []
    for index, event in enumerate(plan["events"]):
        source = db.get(OrderRequestVersion, event["source_version_id"])
        conditions = json.loads(source.request_conditions)
        conditions["project_name"] = f"【テスト】{worker.name}さん参加確認｜{event['event'].replace('【テスト】', '')}"
        version = service.create_draft(actor=actor, kind="test", work_date_label=source.work_date_label,
            site_name=source.site_name, site_id=source.site_id, site_address=source.site_address,
            request_conditions=json.dumps(conditions, ensure_ascii=False), body=source.body,
            contact_name=source.contact_name, contact_desk=source.contact_desk,
            counterparty_note=f"{plan['batch']}:{index}", worker_ids=[worker.id], phone_first=False,
            phone_contacted_at=None, phone_note=None, tracker_user_id=None,
            follow_up_due_on=date.fromisoformat(event["dates"][0]), based_on_version_id=source.id,
            allow_partial_accept=True)
        service.confirm(version, actor=actor)
        delivery = db.query(OrderRequestDelivery).filter_by(version_id=version.id, worker_id=worker.id).one()
        delivery.send_status = "unknown"  # Never pretend that an actual message was sent.
        delivery.ack_reminded_at = ws.now_utc()
        delivery.ack_status, delivery.acked_at = "acked", ws.now_utc()
        ws.append_state(db, delivery, dates=delivery.offered_dates, source=ws.SOURCE_FULL_ACCEPT,
                        actor=actor.username, reason="ユーザー指定のサンプル参加。本人回答・実送信ではない")
        ws.set_application(db, series_id=version.series_id, worker_id=worker.id, delivery=delivery, ended_reason=None, actor=actor.username)
        ws.rebuild(db, version.series_id, worker.id, actor=actor.username)
        actual = {r.work_date.isoformat() for r in ws.visible_schedule_entries(db).filter(
            WorkerScheduleEntry.series_id == version.series_id, WorkerScheduleEntry.worker_id == worker.id, WorkerScheduleEntry.status == "active")}
        if actual != set(event["dates"]):
            raise ValueError("Derived dates differ; rolling back")
        document = db.get(OrderRequestDocument, version.document_id)
        results.append({"document_number": document.document_number, "version_id": version.id,
                        "event": conditions["project_name"], "dates": sorted(actual)})
    AuditService(db).log("sample_participation_created", target_type="worker", target_id=worker.id,
        actor=actor.username, actor_role=actor.role, reason=f"本人指定: {worker.name}さんのサンプル参加予定。実送信なし",
        after_value={"events": results, "is_test": True, "line_sent": False})
    return {"worker_id": worker.id, "name": worker.name, "created": results, "line_sent": False, "test_notifications_enabled": False}


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="")
    parser.add_argument("--worker-id")
    parser.add_argument("--token")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and (not args.worker_id or not args.token):
        parser.error("Apply requires an explicit worker ID and preview token")
    if not args.apply and not (args.query.strip() or args.worker_id):
        parser.error("Preview requires a worker name or ID")
    with SessionLocal() as db:
        result = apply_plan(db, args.worker_id, args.token) if args.apply else build_plan(db, args.query, args.worker_id)
        if args.apply:
            db.commit()
        print(json.dumps(result, ensure_ascii=False))
