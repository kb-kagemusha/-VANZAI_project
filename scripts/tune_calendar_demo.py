"""表示名と可否の補正、および同日重複のない4〜8人のデモを追記する。"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from src.models.master import User, Worker
from src.models.line_order import LineWorkerLink
from src.models.order_request import OrderRequestVersion, OrderRequestDelivery
from src.models.transaction import WorkerAvailability
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestService
from src.services.participation_calendar import build
from src.services import worker_schedule as ws
from scripts.seed_calendar_demo import DEMO_EXTRA_NAMES, REQUESTED_WORKERS, schedule

DATASET = "calendar-demo-202610-v3"


def tune(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User).filter_by(role="admin", is_active=True).filter(User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    audit = AuditService(db)
    renames = {f"【テスト】追加スタッフ{i}": value for i, value in zip(("01", "02", "03", "04"), DEMO_EXTRA_NAMES)}
    renames.update({"テスト アカウント": ("高橋 直樹", "たかはし なおき"), "テストアカウント": ("高橋 直樹", "たかはし なおき")})
    renamed = 0
    for worker in db.query(Worker).filter(Worker.deleted_at.is_(None)):
        if worker.name not in renames:
            continue
        before = {"name": worker.name, "furigana": worker.furigana}
        worker.name, worker.furigana = renames[worker.name]
        audit.log("calendar_demo_worker_renamed", target_type="worker", target_id=worker.id, actor=actor.username, actor_role=actor.role,
            reason="ユーザー指定: ダミー稼働者の表示名を日本名に変更", before_value=before, after_value={"name": worker.name, "furigana": worker.furigana})
        renamed += 1
    db.flush()
    linked = {wid for (wid,) in db.query(LineWorkerLink.worker_id).filter_by(status="active")}
    workers = [w for w in db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.id)
        if w.id not in linked or re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS]
    occupied = defaultdict(set)
    positive = defaultdict(set)
    for day in build(db, start="2026-10-01", end="2026-12-13", include_test=True):
        for event in day["events"]:
            for state in ("ok", "changing", "unanswered", "unavailable"):
                for person in event[state]:
                    occupied[person["worker_id"]].add(day["date"])
                    if state in ("ok", "changing"):
                        positive[person["worker_id"]].add(day["date"])
    service = OrderRequestService(db)
    source = db.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.like("calendar-demo-202610-v2:%")).order_by(OrderRequestVersion.id).first()
    if source is None:
        raise RuntimeError("配置済みデモが必要です")
    created = []
    for month, count, preferred_duration, name in ((10, 8, 3, "会場受付"), (11, 6, 2, "来場者案内"), (11, 5, 1, "店舗キャンペーン"), (10, 4, 1, "街頭調査")):
        marker = f"{DATASET}:{count}"
        if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
            continue
        options = []
        for duration in range(preferred_duration, 0, -1):
            for start_day in range(1, 29 - duration + 2):
                dates = [(date(2026, month, start_day) + timedelta(days=i)).isoformat() for i in range(duration)]
                free = [w for w in workers if not occupied[w.id].intersection(dates)]
                if len(free) >= count:
                    options.append((duration, len(free), dates, free))
            if options:
                break
        if not options:
            raise RuntimeError(f"同日重複を避けて{count}名を配置できません。変更はロールバックします")
        _, _, dates, free = max(options, key=lambda option: (option[0], option[1], -int(option[2][0][-2:])))
        chosen = sorted(free, key=lambda w: (len(occupied[w.id]), w.id))[:count]
        conditions = {"format": "additional-request-v1", "project_name": f"【テスト】{month}月 {count}名参加の{name}",
            "categories": ["調査系" if count == 4 else "商業施設/たばこ屋"], "background": "参加人数の違いを確認するデモ",
            "meeting_place": "会場受付（架空）", "schedule": schedule(dates[0], dates[-1]), "incentive_enabled": False}
        version = service.create_draft(actor=actor, kind="test", work_date_label="", site_name="デモ会場", site_id=None, site_address=None,
            request_conditions=json.dumps(conditions, ensure_ascii=False), body="", contact_name="担当者", contact_desk="", counterparty_note=marker,
            worker_ids=[w.id for w in chosen], phone_first=False, phone_contacted_at=None, phone_note=None, tracker_user_id=None,
            follow_up_due_on=date(2026, 12, 31), internal_source={"client_id": source.internal_client_id, "client_staff_id": None}, internal_source_set=True,
            allow_partial_accept=True)
        service.confirm(version, actor=actor)
        for index, delivery in enumerate(db.query(OrderRequestDelivery).filter_by(version_id=version.id)):
            delivery.send_status = "unknown"
            delivery.ack_reminded_at = datetime.now(timezone.utc)
            delivery.ack_status = "acked"
            delivery.acked_at = datetime.now(timezone.utc)
            selected = dates[:max(1, len(dates) - (index - count + 3))] if index >= count - 2 else dates
            ws.append_state(db, delivery, dates=selected, source="partial_accept" if selected != dates else "full_accept", actor=actor.username, reason="人数のばらつき確認")
            ws.set_application(db, series_id=version.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
            occupied[delivery.worker_id].update(dates)
            positive[delivery.worker_id].update(selected)
        created.append({"version_id": version.id, "count": count, "from": dates[0], "to": dates[-1]})
        audit.log("calendar_demo_group_created", target_type="order_request_version", target_id=version.id, actor=actor.username, actor_role=actor.role,
            reason="ユーザー指定: 4〜8人の参加ケース", after_value=created[-1])
    availability_updated = 0
    for row in db.query(WorkerAvailability).filter(WorkerAvailability.notes.like("calendar-demo-%")):
        day = row.availability_date.isoformat()
        status = "available_all_day" if day in positive[row.worker_id] else (
            ("available_all_day", "unavailable", "available_after_15", "consult_required")[row.availability_date.day % 4] if row.status == "undecided" else row.status)
        if status != row.status:
            audit.log("calendar_demo_availability_updated", target_type="worker_availability", target_id=row.id, actor=actor.username, actor_role=actor.role,
                reason="ユーザー指定: 未定の補完と参加日の可否を整合", before_value={"status": row.status}, after_value={"status": status})
            row.status = status
            availability_updated += 1
    db.flush()
    daily = defaultdict(set)
    max_ok = 0
    participant_counts = set()
    for day in build(db, start="2026-10-01", end="2026-12-13", test_only=True):
        for event in day["events"]:
            max_ok = max(max_ok, len(event["ok"]))
            participant_counts.add(len(event["ok"]))
            for state in ("ok", "changing", "unanswered", "unavailable"):
                for person in event[state]:
                    daily[(person["worker_id"], day["date"])].add(event["series_id"])
    maximum = max((len(value) for value in daily.values()), default=0)
    if maximum > 1 or max_ok < 8:
        raise RuntimeError("同日重複または8人参加の検証に失敗したためロールバックします")
    result = {"renamed": renamed, "created": created, "availability_updated": availability_updated,
        "max_events_per_worker_day": maximum, "max_participants": max_ok, "participant_counts": sorted(participant_counts)}
    audit.log("calendar_demo_tuned", target_type="calendar_demo", target_id=DATASET, actor=actor.username, actor_role=actor.role,
        reason="ダミー表示と人数のばらつき確認", after_value=result)
    return result


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    with SessionLocal() as session:
        result = tune(session)
        session.commit()
        print(json.dumps(result, ensure_ascii=False))
