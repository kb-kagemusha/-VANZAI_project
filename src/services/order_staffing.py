"""Operator final decisions, per case/day headcount and immutable notification keys."""
from datetime import date
import uuid
from sqlalchemy.orm import Session
from src.models.master import Worker
from src.models.order_request import OrderRequestVersion, OrderRequestDocument, OrderRequestDelivery
from src.models.line_daily import OrderRequestSeries, WorkerScheduleEntry
from src.models.order_staffing import StaffingRound, StaffingLimit, StaffingDecision, StaffingNotice
from src.services.order_request_service import OrderRequestError
from src.services import worker_schedule as ws
from src.services.audit import AuditService

DECLINE_THANKS = "承知しました。ご回答ありがとうございます。"
INVITATION_NOTE = "上記の案件に参加できるか教えてください。\n人数調整で見送りになる場合もあります。\n結果は改めて連絡しますので、少しお待ちください。"


def open_response_dates(db, version, worker_id):
    """Called under the series lock shared with final decisions."""
    closed = {r.work_date.isoformat() for r in db.query(StaffingLimit).filter_by(version_id=version.id, closed=True)}
    return {d["work_date"] for d in ws.version_work_days(version)} - closed


def ensure_round(db, version):
    if not version.requires_operator_confirmation:
        return None
    row = db.get(StaffingRound, version.id)
    if row:
        return row
    row = StaffingRound(version_id=version.id, revision=0, created_at=ws.now_utc())
    db.add(row); db.flush()
    days = sorted({d["work_date"] for d in ws.version_work_days(version)})
    previous = db.get(OrderRequestVersion, version.revision_of_version_id) if version.revision_of_version_id else None
    previous_id = previous.id if previous and previous.series_id == version.series_id else None
    old_limits = {r.work_date.isoformat(): r for r in db.query(StaffingLimit).filter_by(version_id=previous_id)} if previous_id else {}
    from src.models.order_formalization import OrderFormalization
    formalization=db.query(OrderFormalization).filter_by(formal_document_id=version.document_id).first() if not previous_id else None
    recipients = {r.worker_id for r in db.query(OrderRequestDelivery).filter_by(version_id=version.id)}
    for value in days:
        old = old_limits.get(value)
        capacity=old.capacity if old else (formalization.capacity_snapshot.get(value,0) if formalization else 0)
        db.add(StaffingLimit(version_id=version.id, work_date=date.fromisoformat(value), capacity=capacity, closed=False))
    db.flush()
    # Existing operator-selected workers keep their selection across a revision.
    if previous_id:
        for old in db.query(StaffingDecision).filter_by(version_id=previous_id, status="confirmed"):
            if old.worker_id in recipients and old.work_date.isoformat() in days:
                db.add(StaffingDecision(version_id=version.id, worker_id=old.worker_id, work_date=old.work_date,
                    status="confirmed", reason="改訂前の運営確定を引き継ぎ", decided_by=old.decided_by, decided_at=old.decided_at))
    db.flush()
    return row


def current_version(db, version_id, *, write=False):
    version = db.get(OrderRequestVersion, version_id)
    if not version:
        raise OrderRequestError(404, "依頼書が見つかりません")
    if write:
        from src.services.staffing_replacement import lock_family
        lock_family(db, version.series_id)
        db.refresh(version)
    document = db.get(OrderRequestDocument, version.document_id)
    series = db.get(OrderRequestSeries, version.series_id)
    if not document or document.deleted_at or version.status != "confirmed" or version.dispatch_stopped or not series or series.answerable_version_id != version.id:
        raise OrderRequestError(409, "回答受付中の最新の確定版で操作してください")
    return version, document


def answers(db, version):
    result = {}
    for delivery in db.query(OrderRequestDelivery).filter_by(version_id=version.id):
        worker = db.get(Worker, delivery.worker_id)
        state = ws.current_state(db, delivery)
        available = bool(worker and worker.is_active and not worker.deleted_at and not delivery.view_revoked)
        accepted = set(state.dates or []) if state and delivery.ack_status == "acked" and available else set()
        result[delivery.worker_id] = {"worker_id": delivery.worker_id,
            "name": worker.name if worker else delivery.worker_name_snapshot,
            "offered_dates": delivery.offered_dates or [], "accepted_dates": sorted(accepted),
            "ack_status": delivery.ack_status, "send_status": delivery.send_status, "available": available}
    return result


def read(db, version_id):
    version, document = current_version(db, version_id)
    row = db.get(StaffingRound, version_id)
    if not row:
        return {"enabled": False, "version_id": version_id, "days": [], "revision": 0, "people": []}
    people = answers(db, version)
    decisions = {(r.worker_id, r.work_date.isoformat()): r for r in db.query(StaffingDecision).filter_by(version_id=version_id)}
    from src.services.staffing_replacement import family, active_workers
    root_id, related_series = family(db,version.series_id)
    days = []
    for limit in db.query(StaffingLimit).filter_by(version_id=version_id).order_by(StaffingLimit.work_date):
        value = limit.work_date.isoformat()
        scheduled = {r.worker_id for r in ws.visible_schedule_entries(db).filter(
            WorkerScheduleEntry.series_id == version.series_id, WorkerScheduleEntry.work_date == limit.work_date,
            WorkerScheduleEntry.status.in_(("active", "changing")))}
        confirmed = [wid for (wid, day), d in decisions.items() if day == value and d.status == "confirmed"
                     and wid in people and people[wid]["available"] and wid in scheduled]
        days.append({"date": value, "capacity": limit.capacity, "closed": limit.closed,
                     "confirmed_ids": confirmed, "confirmed": len(confirmed),
                     "family_confirmed": len(active_workers(db,related_series,limit.work_date)) if root_id == version.series_id else len(confirmed),
                     "remaining": max(0,limit.capacity-len(confirmed))})
    from src.services import wake_test_notifications as tests
    return {"enabled": True, "version_id": version_id, "revision": row.revision, "is_test": document.kind == "test",
            "notifications_enabled": document.kind != "test" or tests.active(tests.setting(db)), "is_replacement": root_id != version.series_id, "days": days,
            "people": [{**person, "decisions": {day: decision.status for (wid,day),decision in decisions.items() if wid == person["worker_id"]}} for person in people.values()],
            "notices": [{"kind": n.kind, "status": n.status, "date": n.work_date.isoformat(), "worker_id": n.worker_id} for n in db.query(StaffingNotice).filter_by(version_id=version_id)]}


def locked_round(db, version_id, revision):
    version, document = current_version(db, version_id, write=True)
    row = db.query(StaffingRound).filter_by(version_id=version_id).with_for_update().populate_existing().one_or_none()
    if not row or not version.requires_operator_confirmation:
        raise OrderRequestError(409, "この依頼書は従来の受諾方式です。新規作成時に運営の最終確定を選んでください")
    if row.revision != revision:
        raise OrderRequestError(409, "別の操作で人数が変更されました。最新の状態を読み直してください")
    return version, document, row


def save_limits(db, version_id, capacities, revision, actor):
    version, _document, row = locked_round(db, version_id, revision)
    limits = {r.work_date.isoformat(): r for r in db.query(StaffingLimit).filter_by(version_id=version_id)}
    if set(capacities) != set(limits) or any(isinstance(v,bool) or not isinstance(v,int) or v < 0 for v in capacities.values()):
        raise OrderRequestError(422, "稼働日ごとに0以上の人数を設定してください")
    before = {day: limit.capacity for day,limit in limits.items()}
    current = read(db, version_id)
    from src.models.staffing_replacement import StaffingRecruitment
    if db.query(StaffingRecruitment.id).filter_by(series_id=version.series_id).first() and any(v != 1 for v in capacities.values()):
        raise OrderRequestError(409,"代替募集は欠員1名に対して1枠です。元の案件と重複して人数を増やせません")
    for day in current["days"]:
        limit = limits[day["date"]]
        value = capacities[day["date"]]
        if value < day["family_confirmed"]:
            raise OrderRequestError(409, "確定人数より少ない上限には変更できません")
        if limit.closed and value != limit.capacity:
            raise OrderRequestError(409, "終了した募集は人数を直接変更できません")
        limit.capacity = value
    row.revision += 1
    AuditService(db).log("staffing_limits_changed", target_type="order_request_version", target_id=version_id,
        actor=actor.username, actor_role=actor.role, before_value=before, after_value=capacities)
    db.flush()
    return read(db, version_id)


def queue_notice(db, version, worker_id, day, kind, body):
    if db.query(StaffingNotice.id).filter_by(version_id=version.id, worker_id=worker_id, work_date=day, kind=kind).first():
        return
    name = ws.version_display(version)["project_name"]
    document = db.get(OrderRequestDocument, version.document_id)
    text = f"{'【テスト】' if document.kind == 'test' else ''}{name}\n{day:%Y/%m/%d}\n\n{body}"
    db.add(StaffingNotice(version_id=version.id, worker_id=worker_id, work_date=day, kind=kind,
                         message=text, retry_key=str(uuid.uuid4()), status="pending", attempts=0, created_at=ws.now_utc()))


def decide(db, version_id, selected, close_dates, reason, revision, actor):
    actor_name, actor_role = actor.username, actor.role
    version, _document, row = locked_round(db, version_id, revision)
    limits = {r.work_date.isoformat(): r for r in db.query(StaffingLimit).filter_by(version_id=version_id)}
    if not set(selected).issubset(limits) or not set(close_dates).issubset(selected):
        raise OrderRequestError(422, "対象日を選び直してください")
    people = answers(db, version)
    # Lock worker identities in a stable order, to prevent simultaneous allocations in different cases.
    ids = sorted({wid for values in selected.values() for wid in values})
    for wid in ids:
        db.query(Worker).filter_by(id=wid).with_for_update().populate_existing().first()
    people = answers(db, version)
    existing = {(r.worker_id,r.work_date.isoformat()): r for r in db.query(StaffingDecision).filter_by(version_id=version_id)}
    from src.services.staffing_replacement import verify_selection, selected as record_replacement_selection
    previous_by_day = {value:{wid for (wid,day),d in existing.items() if day == value and d.status == "confirmed"} for value in selected}
    verify_selection(db,version,selected,previous_by_day)
    touched = set()
    for value, chosen_list in selected.items():
        limit = limits[value]
        chosen = set(chosen_list)
        if len(chosen) != len(chosen_list) or len(chosen) > limit.capacity or (chosen and limit.capacity == 0):
            raise OrderRequestError(409, "日別の上限人数を超えています")
        previous = {wid for (wid,day),decision in existing.items() if day == value and decision.status == "confirmed"}
        if limit.closed and chosen != previous:
            raise OrderRequestError(409, "終了した募集の参加者は直接変更できません")
        if not previous.issubset(chosen):
            raise OrderRequestError(409, "確定済みの方を外すには欠員・取消の操作を行ってください")
        for wid in chosen-previous:
            person = people.get(wid)
            if not person or not person["available"] or value not in person["accepted_dates"]:
                raise OrderRequestError(409, "参加可能の回答がある方だけを確定できます。回答を読み直してください")
            conflict = ws.visible_schedule_entries(db).filter(WorkerScheduleEntry.worker_id == wid,
                WorkerScheduleEntry.work_date == date.fromisoformat(value), WorkerScheduleEntry.series_id != version.series_id,
                WorkerScheduleEntry.is_test == (_document.kind == "test"),
                WorkerScheduleEntry.status.in_(("active","changing"))).first()
            if conflict:
                raise OrderRequestError(409, "同じ日に別案件の確定予定があります")
            if _document.kind != "test":
                from src.models.transaction import Assignment, ShiftSlot
                assigned=db.query(Assignment.id).join(ShiftSlot,Assignment.shift_slot_id == ShiftSlot.id).filter(Assignment.worker_id == wid,Assignment.status != "canceled",Assignment.deleted_at.is_(None),ShiftSlot.deleted_at.is_(None),ShiftSlot.work_date == date.fromisoformat(value)).first()
                if assigned: raise OrderRequestError(409,"同じ日に配置の予定があります。担当案件を確認してください")
            decision = existing.get((wid,value))
            if decision is None:
                decision = StaffingDecision(version_id=version_id, worker_id=wid, work_date=limit.work_date)
                db.add(decision); existing[(wid,value)] = decision
            decision.status, decision.reason = "confirmed", reason
            decision.decided_by, decision.decided_at = actor_name, ws.now_utc()
            from src.models.staffing_replacement import StaffingRecruitment
            urgent = db.query(StaffingRecruitment.id).filter_by(series_id=version.series_id).first() is not None
            queue_notice(db,version,wid,limit.work_date,"confirmed","参加が確定しました。\n" + ("急なお願いにもかかわらず、" if urgent else "") + "引き受けていただきありがとうございます。\n当日はよろしくお願いします。")
            touched.add(wid)
        if value in close_dates or (limit.capacity > 0 and len(chosen) == limit.capacity):
            if len(chosen) < limit.capacity and not reason.strip():
                raise OrderRequestError(422, "人数未達で終了する理由を入力してください")
            limit.closed = True
            for wid,person in people.items():
                if wid in chosen or value not in person["offered_dates"] or person["ack_status"] in ("declined","decline_pending"):
                    continue
                decision = existing.get((wid,value))
                if decision is None:
                    decision = StaffingDecision(version_id=version_id,worker_id=wid,work_date=limit.work_date)
                    db.add(decision); existing[(wid,value)] = decision
                decision.status, decision.reason = "not_selected", reason
                decision.decided_by, decision.decided_at = actor_name, ws.now_utc()
                body = "今回は別の方で対応できることになりました。\nご検討・ご協力ありがとうございました。" if len(chosen) >= limit.capacity else "今回の募集は終了しました。\nご検討・ご協力ありがとうございました。"
                if person["send_status"] in ("accepted", "unknown") or person["ack_status"] == "acked":
                    queue_notice(db,version,wid,limit.work_date,"closed",body)
                touched.add(wid)
    db.flush()
    record_replacement_selection(db,version,selected)
    for wid in sorted(touched):
        ws.rebuild(db,version.series_id,wid,actor=actor.username)
    row.revision += 1
    AuditService(db).log("staffing_decided",target_type="order_request_version",target_id=version_id,
        actor=actor.username,actor_role=actor.role,reason=reason,after_value={"selected": selected,"closed_dates": [d for d,l in limits.items() if l.closed]})
    db.flush()
    return read(db,version_id)


def dispatch_notices(db, version_id, actor, *, client=None, retry_failed=False):
    """Bounded sends after committing decisions. Failed sends need an explicit retry.

    Each row is locked until its result commits. LINE's stable retry key handles
    a crash after the remote server accepted a message but before our commit.
    Never replay an ambiguous send outside LINE's 24-hour deduplication window.
    """
    from datetime import timedelta
    from src.models.line_order import LineWorkerLink
    from src.services.line_messaging import build_line_client
    from src.services import wake_test_notifications as tests
    statuses = ("pending", "failed") if retry_failed else ("pending",)
    ids = [n.id for n in db.query(StaffingNotice).filter(StaffingNotice.version_id == version_id,
        StaffingNotice.status.in_(statuses)).order_by(StaffingNotice.created_at, StaffingNotice.id).limit(20)]
    db.commit()
    for notice_id in ids:
        version = db.get(OrderRequestVersion, version_id)
        ws.lock_series(db, version.series_id)
        tests.lock(db)
        notice = db.query(StaffingNotice).filter_by(id=notice_id).with_for_update(skip_locked=True).populate_existing().one_or_none()
        if not notice or notice.status not in statuses:
            db.commit(); continue
        version = db.get(OrderRequestVersion, notice.version_id)
        document = db.get(OrderRequestDocument, version.document_id)
        series = db.get(OrderRequestSeries, version.series_id)
        delivery = db.query(OrderRequestDelivery).filter_by(version_id=version.id, worker_id=notice.worker_id).one_or_none()
        worker = db.get(Worker, notice.worker_id)
        decision = db.query(StaffingDecision).filter_by(version_id=version.id, worker_id=notice.worker_id, work_date=notice.work_date).one_or_none()
        now = ws.now_utc()
        valid = bool(document and not document.deleted_at and not version.dispatch_stopped and version.status == "confirmed"
            and series.answerable_version_id == version.id and delivery and not delivery.view_revoked
            and worker and worker.is_active and not worker.deleted_at
            and decision and decision.status == ("confirmed" if notice.kind == "confirmed" else "not_selected"))
        if valid and notice.kind == "confirmed":
            state = ws.current_state(db,delivery)
            valid = bool(state and notice.work_date.isoformat() in state.dates)
        if valid and notice.kind == "closed":
            from src.services.staffing_replacement import family, active_workers
            root_id,related=family(db,version.series_id)
            if notice.worker_id in active_workers(db,related-{version.series_id},notice.work_date):
                valid=False
        if not valid or (notice.kind == "closed" and delivery.ack_status in ("declined", "decline_pending")):
            notice.status = "cancelled"
        elif document.kind == "test" and (not tests.active(tests.setting(db), now)
                or tests.utc(notice.created_at) < tests.utc(tests.setting(db).enabled_from)):
            notice.status = "skipped"
        elif notice.attempts and now - tests.utc(notice.created_at) > timedelta(hours=23):
            notice.status = "skipped"
        else:
            links = db.query(LineWorkerLink).filter_by(worker_id=worker.id, status="active").all()
            if len(links) != 1:
                notice.status = "failed"
            else:
                notice.attempts += 1
                try:
                    result = (client or build_line_client()).push_receipt(links[0].line_user_id, notice.message, notice.retry_key)
                    success = result.status == 200 or (result.status == 409 and bool(result.accepted_request_id))
                    notice.status = "sent" if success else "failed"
                    if success: notice.sent_at = now
                except Exception:
                    # Do not log tokens, recipient IDs, or upstream response bodies.
                    notice.status = "failed"
        AuditService(db).log("staffing_notice_processed", target_type="order_staffing_notice", target_id=notice.id,
            actor=actor.username, actor_role=actor.role, after_value={"status": notice.status, "kind": notice.kind, "attempts": notice.attempts})
        db.commit()
