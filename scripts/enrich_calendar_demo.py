"""稼働開始日のデモと、同一イベント内で人数が変わる長期予定。再実行可能。"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from src.domain.worker_tags import tokyo_today, is_newcomer_from_start
from src.models.master import User, Worker
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.models.line_daily import OrderRequestSeries
from src.models.order_billing import OrderBillingInvoiceLine
from src.models.transaction import WorkerAvailability
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestService
from src.services.participation_calendar import build
from src.services import worker_schedule as ws

DATASET = "calendar-demo-202610-v4"
NEW_WORKERS = (("石川 美月", "いしかわ みづき"), ("宮本 悠真", "みやもと ゆうま"),
    ("大西 結菜", "おおにし ゆいな"), ("小野寺 陽介", "おのでら ようすけ"), ("久保田 沙織", "くぼた さおり"))
DAILY_COUNTS = (8, 4, 6, 3, 7, 5, 8, 4, 5, 7)


def enrich(db, today=None):
    today = today or tokyo_today()
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User).filter_by(role="admin", is_active=True).filter(User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    audit = AuditService(db)
    def log(action, target_type, target_id, before=None, after=None):
        audit.log(action, target_type=target_type, target_id=target_id, actor=actor.username, actor_role=actor.role,
            reason="ユーザー指定: 開始日基準の新人5名と同一イベント内の日別人数差", before_value=before, after_value=after)
    added = 0
    new_workers = []
    for index, (name, furigana) in enumerate(NEW_WORKERS):
        matches = db.query(Worker).filter_by(name=name).all()
        if matches:
            if len(matches) != 1 or matches[0].notes != DATASET or matches[0].deleted_at is not None:
                raise RuntimeError("追加予定の氏名が既存の別データと重なるため停止しました")
            worker = matches[0]
        else:
            worker = Worker(name=name, furigana=furigana, is_active=True, notes=DATASET,
                available_start_date=today - timedelta(days=25 + index * 12))
            db.add(worker)
            db.flush()
            log("calendar_demo_newcomer_created", "worker", worker.id, after={"dataset": DATASET, "available_start_date": worker.available_start_date.isoformat()})
            added += 1
        new_workers.append(worker)
    filled = 0
    workers = db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.id).all()
    for index, worker in enumerate(workers):
        if worker.available_start_date is None:
            worker.available_start_date = today - timedelta(days=365 + index * 17)
            log("calendar_demo_start_date_filled", "worker", worker.id, before={"available_start_date": None}, after={"available_start_date": worker.available_start_date.isoformat()})
            filled += 1
    db.flush()
    service = OrderRequestService(db)
    created = 0
    for month in (10, 11):
        marker = f"{DATASET}:{month}"
        if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
            continue
        source = db.query(OrderRequestVersion).filter_by(counterparty_note=f"calendar-demo-202610-v2:{month}:46").one()
        document = db.get(OrderRequestDocument, source.document_id)
        series = db.get(OrderRequestSeries, source.series_id)
        latest = db.get(OrderRequestVersion, series.answerable_version_id)
        if document.kind != "test" or document.deleted_at is not None:
            raise RuntimeError("有効な長期テスト依頼だけを置換できます")
        if db.query(OrderBillingInvoiceLine.id).filter_by(series_id=source.series_id).first():
            raise RuntimeError("請求済み依頼は置換できません")
        dates = sorted({day["work_date"] for day in ws.version_work_days(latest)})
        originals = sorted({d.worker_id for d in db.query(OrderRequestDelivery).filter_by(version_id=latest.id)})
        chosen = originals + [w.id for w in new_workers]
        if len(dates) != 20 or len(originals) != 3 or len(set(chosen)) != 8:
            raise RuntimeError("20日・既存3名＋追加5名の前提が変わっています")
        for day in build(db, start=dates[0], end=dates[-1], include_test=True):
            for event in day["events"]:
                if event["document_id"] == document.id:
                    continue
                if any(p["worker_id"] in chosen for state in ("ok", "changing", "unanswered", "unavailable") for p in event[state]):
                    raise RuntimeError("同日別イベントがあるため置換を停止しました")
        snap = latest.snapshot_json or {}
        replacement = service.create_draft(actor=actor, kind="test", work_date_label="", site_name=snap.get("site_name", latest.site_name),
            site_id=latest.site_id, site_address=snap.get("site_address", latest.site_address),
            request_conditions=snap.get("request_conditions", latest.request_conditions), body="", contact_name=latest.contact_name,
            contact_desk=latest.contact_desk, counterparty_note=marker, worker_ids=chosen, phone_first=False,
            phone_contacted_at=None, phone_note=None, tracker_user_id=None, follow_up_due_on=date(2026, 12, 31),
            internal_source={"client_id": latest.internal_client_id, "client_staff_id": latest.internal_client_staff_id},
            internal_source_set=True, allow_partial_accept=True)
        service.confirm(replacement, actor=actor)
        accepted = defaultdict(list)
        for index, day in enumerate(dates):
            # 基本3名＋追加5名を日ごとに交代。8→4→6→3…の差を1つの枠で確認する。
            rotation = index % 5
            extra = chosen[3:][rotation:] + chosen[3:][:rotation]
            for wid in chosen[:3] + extra[:DAILY_COUNTS[index % len(DAILY_COUNTS)] - 3]:
                accepted[wid].append(day)
        for delivery in db.query(OrderRequestDelivery).filter_by(version_id=replacement.id):
            delivery.send_status = "unknown"  # 実際のLINE送信は行わない
            delivery.ack_reminded_at = datetime.now(timezone.utc)
            delivery.ack_status = "acked"
            delivery.acked_at = datetime.now(timezone.utc)
            selected = accepted[delivery.worker_id]
            ws.append_state(db, delivery, dates=selected, source="full_accept" if selected == dates else "partial_accept", actor=actor.username, reason="ダミー: 日によって参加可能人数が異なる回答")
            ws.set_application(db, series_id=replacement.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by_user_id = actor.id
        log("calendar_demo_daily_variation_replaced", "order_request_document", document.id,
            before={"deleted_at": None}, after={"replacement_document_id": replacement.document_id, "daily_ok_counts": [DAILY_COUNTS[i % len(DAILY_COUNTS)] for i in range(20)]})
        created += 1
    db.flush()
    calendar = build(db, start="2026-10-01", end="2026-12-13", include_test=True)
    occupied = defaultdict(set)
    positive = defaultdict(set)
    counts = defaultdict(list)
    v4_series = {v.series_id for v in db.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.like(DATASET + ":%"))}
    for day in calendar:
        for event in day["events"]:
            if event["series_id"] in v4_series:
                counts[event["series_id"]].append(len(event["ok"]))
            for state in ("ok", "changing", "unanswered", "unavailable"):
                for person in event[state]:
                    occupied[(person["worker_id"], day["date"])].add(event["series_id"])
                    if state == "ok":
                        positive[person["worker_id"]].add(day["date"])
    maximum = max(map(len, occupied.values()), default=0)
    if maximum > 1 or len(counts) != 2 or any(len(c) != 20 or not {3,4,5,6,7,8}.issubset(c) for c in counts.values()):
        raise RuntimeError("日別人数差または同日重複の検証に失敗しました。全変更をロールバックします")
    for worker in new_workers:
        day = date(2026, 10, 1)
        while day <= date(2026, 12, 13):
            if not db.query(WorkerAvailability.id).filter_by(worker_id=worker.id, availability_date=day).first():
                db.add(WorkerAvailability(worker_id=worker.id, availability_date=day,
                    status="available_all_day" if day.isoformat() in positive[worker.id] else ("available_all_day", "unavailable", "consult_required")[day.day % 3], notes=DATASET))
            day += timedelta(days=1)
    result = {"workers_added": added, "start_dates_filled": filled, "events_replaced": created,
        "newcomers": sum(is_newcomer_from_start(w.available_start_date, today) for w in workers),
        "daily_ok_counts": list(counts.values()), "max_events_per_worker_day": maximum}
    log("calendar_demo_newcomers_completed", "calendar_demo", DATASET, after=result)
    return result


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    with SessionLocal() as session:
        result = enrich(session)
        session.commit()
        print(json.dumps(result, ensure_ascii=False))
