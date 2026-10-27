"""One-day vacancies and explicit replacement invitations, shared by admin and LINE."""
import copy
import hashlib
import json
from datetime import date, datetime, time, timezone
from sqlalchemy import or_
from src.models.line_daily import WorkerScheduleEntry, OrderRequestSeries, WakeContactLog
from src.models.master import Worker
from src.models.line_order import LineWorkerLink
from src.models.order_request import OrderRequestVersion, OrderRequestDocument, OrderRequestDelivery, MAX_RECIPIENTS
from src.models.order_staffing import StaffingRound, StaffingLimit, StaffingDecision
from src.models.staffing_replacement import StaffingVacancy, StaffingRecruitment
from src.models.transaction import WorkerAvailability, Assignment, ShiftSlot
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestService, OrderRequestError
from src.domain.order_schedule import normalize_schedule, normalize_work_period, work_period_label
from src.services.order_request_format import FORMAT_ID


def family(db, series_id):
    campaign = db.query(StaffingRecruitment).filter_by(series_id=series_id).one_or_none()
    root_id = db.get(StaffingVacancy,campaign.vacancy_id).root_series_id if campaign else series_id
    children = {r.series_id for r in db.query(StaffingRecruitment).join(StaffingVacancy,StaffingRecruitment.vacancy_id == StaffingVacancy.id).filter(StaffingVacancy.root_series_id == root_id)}
    return root_id, children | {root_id}


def lock_family(db, series_id):
    root_id, series_ids = family(db,series_id)
    ws.lock_series(db,root_id)
    if root_id != series_id: ws.lock_series(db,series_id)
    return root_id, series_ids


def active_workers(db, series_ids, day):
    return {r.worker_id for r in ws.visible_schedule_entries(db).filter(WorkerScheduleEntry.series_id.in_(series_ids),
        WorkerScheduleEntry.work_date == day,WorkerScheduleEntry.status.in_(("active","changing")))}


def capacity(db, root_id, day):
    root = db.get(OrderRequestSeries,root_id)
    limit = db.get(StaffingLimit,(root.answerable_version_id,day)) if root and root.answerable_version_id else None
    if limit and limit.capacity > 0: return limit.capacity
    values = [v.expected_capacity for v in db.query(StaffingVacancy).filter(StaffingVacancy.root_series_id == root_id,StaffingVacancy.work_date == day,StaffingVacancy.status != "cancelled")]
    return max(values,default=0)


def verify_selection(db, version, selected, previous):
    """Parent series is locked before any child series and worker locks."""
    root_id, ids = family(db,version.series_id)
    vacancies = db.query(StaffingVacancy).filter(StaffingVacancy.root_series_id == root_id,StaffingVacancy.status != "cancelled").all()
    if not vacancies: return
    campaign=db.query(StaffingRecruitment).filter_by(series_id=version.series_id).one_or_none()
    if campaign and any(set(values)-previous.get(day,set()) for day,values in selected.items()):
        vacancy=db.get(StaffingVacancy,campaign.vacancy_id)
        _entry_for_vacancy(db,vacancy)
        if vacancy.status != "recruiting": raise OrderRequestError(409,"この欠員の募集は終了しています")
    for value, chosen in selected.items():
        day=date.fromisoformat(value)
        if not (set(chosen)-previous.get(value,set())): continue
        if root_id == version.series_id and any(v.work_date == day and v.status in ("open","recruiting") for v in vacancies):
            raise OrderRequestError(409,"欠員への参加者は、関連する代替募集の画面から確定してください")
        other=active_workers(db,ids-{version.series_id},day)
        if len(other | set(chosen)) > capacity(db,root_id,day):
            raise OrderRequestError(409,"元の案件の日別上限を超えます。別の運営による確定も含めて確認してください")


def selected(db, version, choices):
    campaign=db.query(StaffingRecruitment).filter_by(series_id=version.series_id).one_or_none()
    if not campaign: return
    vacancy=db.get(StaffingVacancy,campaign.vacancy_id)
    if choices.get(vacancy.work_date.isoformat()) and vacancy.status != "filled":
        vacancy.status="filled"; vacancy.revision+=1


def _entry(db, entry_id, *, lock=False):
    entry=ws.visible_schedule_entries(db).filter(WorkerScheduleEntry.id == entry_id).one_or_none()
    if not entry: raise OrderRequestError(404,"対象の予定が見つかりません")
    if lock:
        lock_family(db,entry.series_id)
        db.refresh(entry)
    if entry.status not in ("active","changing"):
        raise OrderRequestError(409,"現在の確定予定を選び直してください")
    version=db.get(OrderRequestVersion,entry.version_id)
    series=db.get(OrderRequestSeries,entry.series_id)
    current=db.get(OrderRequestVersion,series.answerable_version_id) if series and series.answerable_version_id else None
    if not current or current.status != "confirmed" or current.dispatch_stopped:
        raise OrderRequestError(409,"現在有効な案件の予定だけを欠員にできます")
    started,_=ws.split_started(version,[entry.work_date.isoformat()])
    current_started,_=ws.split_started(current,[entry.work_date.isoformat()])
    if started or current_started:
        raise OrderRequestError(409,"勤務開始後は途中交代・実績の確認が必要です。この操作では予定を外しません")
    return entry,version,current


def _guard(db,entry,current):
    round_=db.get(StaffingRound,current.id)
    value=[entry.id,entry.version_id,entry.status,current.id,round_.revision if round_ else 0]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def preview(db, entry_id):
    entry,version,current=_entry(db,entry_id)
    worker=db.get(Worker,entry.worker_id)
    return {"entry_id":entry.id,"date":entry.work_date.isoformat(),"worker_name":worker.name,
        "project_name":entry.project_name,"is_test":bool(entry.is_test),"guard":_guard(db,entry,current)}


def create(db, entry_id, guard, reason, actor):
    name=actor.username
    entry,version,current=_entry(db,entry_id,lock=True)
    if guard != _guard(db,entry,current): raise OrderRequestError(409,"予定が変更されました。最新の状態を確認してください")
    if not reason.strip(): raise OrderRequestError(422,"欠員にする理由を入力してください")
    root_id,ids=family(db,entry.series_id)
    existing=db.query(StaffingVacancy).filter(StaffingVacancy.root_series_id == root_id,StaffingVacancy.work_date == entry.work_date,StaffingVacancy.status.in_(("open","recruiting"))).count()
    expected=max(capacity(db,root_id,entry.work_date),len(active_workers(db,ids,entry.work_date))+existing,1)
    decision=db.query(StaffingDecision).filter_by(version_id=current.id,worker_id=entry.worker_id,work_date=entry.work_date,status="confirmed").one_or_none()
    row=StaffingVacancy(source_entry_id=entry.id,source_series_id=entry.series_id,root_series_id=root_id,worker_id=entry.worker_id,
        work_date=entry.work_date,status="open",expected_capacity=expected,selection_id=decision.id if decision else None,
        reason=reason.strip(),revision=0,created_by=name,created_at=ws.now_utc())
    db.add(row)
    if decision: decision.status="vacant"
    round_=db.get(StaffingRound,current.id)
    if round_: round_.revision+=1
    db.flush()
    ws.rebuild(db,entry.series_id,entry.worker_id,actor=name)
    # Never let a test absence suppress formal wake monitoring.
    db.add(WakeContactLog(worker_id=entry.worker_id,contact_date=entry.work_date,result="absent",note=reason.strip()[:500],is_test=bool(entry.is_test),actor_user_id=actor.id,actor_name=(getattr(actor,"display_name",None) or name)[:100],created_at=ws.now_utc()))
    AuditService(db).log("staffing_vacancy_created",target_type="staffing_vacancy",target_id=row.id,actor=name,actor_role=actor.role,
        reason=reason.strip(),after_value={"entry_id":entry.id,"date":entry.work_date.isoformat(),"root_series_id":root_id,"expected_capacity":expected})
    db.flush()
    return detail(db,row.id)


def _row(db,vacancy_id,revision=None):
    row=db.get(StaffingVacancy,vacancy_id)
    if not row: raise OrderRequestError(404,"欠員の記録が見つかりません")
    if revision is not None:
        lock_family(db,row.source_series_id)
        db.refresh(row)
        if row.revision != revision: raise OrderRequestError(409,"欠員の状態が変わりました。画面を更新してください")
    return row


def detail(db,vacancy_id):
    row=_row(db,vacancy_id)
    entry=db.get(WorkerScheduleEntry,row.source_entry_id)
    worker=db.get(Worker,row.worker_id)
    campaign=db.query(StaffingRecruitment).filter_by(vacancy_id=row.id).one_or_none()
    series=db.get(OrderRequestSeries,campaign.series_id) if campaign else None
    root=db.get(OrderRequestSeries,row.root_series_id)
    root_version=db.get(OrderRequestVersion,root.answerable_version_id) if root and root.answerable_version_id else None
    return {"id":row.id,"revision":row.revision,"status":row.status,"date":row.work_date.isoformat(),"worker_name":worker.name,
        "project_name":entry.project_name,"is_test":bool(entry.is_test),"reason":row.reason,"root_series_id":row.root_series_id,
        "recruitment_version_id":series.answerable_version_id if series else None,"source_entry_id":entry.id,
        "source_active":bool(root_version and root_version.status == "confirmed" and not root_version.dispatch_stopped and not db.get(OrderRequestDocument,root_version.document_id).deleted_at)}


def list_vacancies(db, day):
    return [detail(db,v.id) for v in db.query(StaffingVacancy).filter(StaffingVacancy.work_date == day,StaffingVacancy.status != "cancelled").order_by(StaffingVacancy.created_at)]


def invitation_preview(db,vacancy_id):
    from src.services import wake_test_notifications as tests
    item=detail(db,vacancy_id)
    if not item["recruitment_version_id"]: raise OrderRequestError(409,"先に打診する内容を作成してください")
    version=db.get(OrderRequestVersion,item["recruitment_version_id"])
    return {"version_id":version.id,"body":version.body,"notifications_enabled":not item["is_test"] or tests.active(tests.setting(db)),
        "recipients":[{"name":d.worker_name_snapshot,"send_status":d.send_status,"ack_status":d.ack_status} for d in db.query(OrderRequestDelivery).filter_by(version_id=version.id)]}


def candidates(db, vacancy_id):
    row=_row(db,vacancy_id)
    entry=db.get(WorkerScheduleEntry,row.source_entry_id)
    booked={r.worker_id for r in ws.visible_schedule_entries(db).filter(WorkerScheduleEntry.work_date == row.work_date,WorkerScheduleEntry.is_test == entry.is_test,WorkerScheduleEntry.status.in_(("active","changing")))}
    if not entry.is_test:
        booked |= {wid for (wid,) in db.query(Assignment.worker_id).join(ShiftSlot,Assignment.shift_slot_id == ShiftSlot.id).filter(ShiftSlot.work_date == row.work_date,Assignment.status != "canceled",Assignment.deleted_at.is_(None),ShiftSlot.deleted_at.is_(None))}
    availability={r.worker_id:r.status for r in db.query(WorkerAvailability).filter_by(availability_date=row.work_date)}
    linked={r.worker_id for r in db.query(LineWorkerLink).filter_by(status="active")}
    missing={r.worker_id for r in db.query(StaffingVacancy).filter(StaffingVacancy.root_series_id == row.root_series_id,StaffingVacancy.work_date == row.work_date,StaffingVacancy.status != "cancelled")}
    return [{"id":w.id,"name":w.name,"availability":availability.get(w.id),"line_linked":w.id in linked}
        for w in db.query(Worker).filter(Worker.is_active.is_(True),Worker.deleted_at.is_(None)).order_by(Worker.name,Worker.id)
        if w.id not in booked | missing and availability.get(w.id) != "unavailable"]


def _one_day_sections(version, value):
    sections=copy.deepcopy(ws._version_sections(version))
    sections["format"]=FORMAT_ID
    schedule=sections.get("schedule")
    if not schedule: raise OrderRequestError(409,"日付別の勤務条件がありません。依頼書を確認してください")
    work=[g for g in schedule["work_groups"] if g["from"] <= value <= g["to"] and value not in g.get("excluded_dates",[])]
    rates=[g for g in schedule["rate_groups"] if g["from"] <= value <= g["to"]]
    for group in work+rates:
        group.update({"date_mode":"single","from":value,"to":value})
        if "excluded_dates" in group: group["excluded_dates"]=[]
    sections["schedule"]=normalize_schedule({**schedule,"work_groups":work,"rate_groups":rates},complete=True)
    sections["work_period"]=normalize_work_period({"from":value,"to":value,"excluded_dates":[]},sections["schedule"],complete=True)
    sections["work_date_detail"]=""
    return sections


def recruit(db,vacancy_id,worker_ids,deadline,revision,actor):
    row=_row(db,vacancy_id,revision)
    if row.status not in ("open","recruiting"): raise OrderRequestError(409,"募集できる欠員を選び直してください")
    entry,source,current=_entry_for_vacancy(db,row)
    current_start=ws.day_start_time(current,row.work_date.isoformat())
    starts=datetime.combine(row.work_date,time.fromisoformat(current_start) if current_start else time(0,0),tzinfo=ws.JST)
    if deadline.tzinfo is None or not ws.now_utc() < deadline <= starts:
        raise OrderRequestError(422,"回答期限は現在より後、勤務開始までの時刻を指定してください")
    if len(worker_ids) != len(set(worker_ids)) or not 1 <= len(worker_ids) <= MAX_RECIPIENTS:
        raise OrderRequestError(422,"候補者を重複なく選んでください")
    available={w["id"] for w in candidates(db,row.id) if w["line_linked"]}
    if not set(worker_ids) <= available: raise OrderRequestError(409,"候補者の予定や連携が変わりました。候補を読み直してください")
    campaign=db.query(StaffingRecruitment).filter_by(vacancy_id=row.id).one_or_none()
    service=OrderRequestService(db)
    if campaign:
        series=db.get(OrderRequestSeries,campaign.series_id)
        previous=db.get(OrderRequestVersion,series.answerable_version_id) if series.answerable_version_id else db.query(OrderRequestVersion).filter_by(series_id=series.id).order_by(OrderRequestVersion.version_no.desc()).first()
        limit=db.get(StaffingLimit,(previous.id,row.work_date)) if previous else None
        if not limit or (not limit.closed and previous.status != "cancelled") or active_workers(db,{campaign.series_id},row.work_date):
            raise OrderRequestError(409,"現在の募集が終了していません。参加者の確定画面を確認してください")
        version=service.revise(previous,actor=actor,reason="欠員への代替募集をやり直す")
        service.update_draft(version,actor=actor,worker_ids=worker_ids,follow_up_due_on=deadline.astimezone(ws.JST).date(),follow_up_due_time=deadline.astimezone(ws.JST).strftime("%H:%M"))
    else:
        sections=_one_day_sections(current,row.work_date.isoformat())
        document=db.get(OrderRequestDocument,current.document_id)
        version=service.create_draft(actor=actor,kind=document.kind,work_date_label=work_period_label(sections["work_period"]),site_name=current.site_name,site_id=current.site_id,site_address=current.site_address,
            request_conditions=json.dumps(sections,ensure_ascii=False),body="",contact_name=current.contact_name,contact_desk=current.contact_desk,counterparty_note=current.counterparty_note,
            worker_ids=worker_ids,phone_first=False,phone_contacted_at=None,phone_note=None,tracker_user_id=None,
            follow_up_due_on=deadline.astimezone(ws.JST).date(),follow_up_due_time=deadline.astimezone(ws.JST).strftime("%H:%M"),requires_operator_confirmation=True)
        service._copy_internal_source(current,version)
    service.confirm(version,actor=actor)
    limit=db.get(StaffingLimit,(version.id,row.work_date)); limit.capacity=1
    if not campaign: db.add(StaffingRecruitment(vacancy_id=row.id,series_id=version.series_id,created_at=ws.now_utc()))
    row.status="recruiting"; row.revision+=1
    AuditService(db).log("staffing_recruitment_prepared",target_type="staffing_vacancy",target_id=row.id,actor=actor.username,actor_role=actor.role,
        after_value={"version_id":version.id,"recipient_ids":worker_ids,"deadline":deadline.isoformat()})
    db.flush()
    return detail(db,row.id)


def _entry_for_vacancy(db,row):
    entry=db.get(WorkerScheduleEntry,row.source_entry_id)
    source=db.get(OrderRequestVersion,entry.version_id)
    series=db.get(OrderRequestSeries,row.root_series_id)
    current=db.get(OrderRequestVersion,series.answerable_version_id) if series and series.answerable_version_id else None
    if not current or current.dispatch_stopped or current.status != "confirmed" or db.get(OrderRequestDocument,current.document_id).deleted_at:
        raise OrderRequestError(409,"元の案件が終了しています。募集は開始できません")
    if row.work_date.isoformat() not in {d["work_date"] for d in ws.version_work_days(current)}:
        raise OrderRequestError(409,"元の案件から対象日が外れています。日程を確認してください")
    started,_=ws.split_started(source,[row.work_date.isoformat()])
    current_started,_=ws.split_started(current,[row.work_date.isoformat()])
    if started or current_started: raise OrderRequestError(409,"勤務開始後の手配は実績と途中交代を確認してください")
    return entry,source,current


def cancel(db,vacancy_id,reason,revision,actor):
    row=_row(db,vacancy_id,revision)
    entry,source,current=_entry_for_vacancy(db,row)
    if not reason.strip(): raise OrderRequestError(422,"欠員を取り消す理由を入力してください")
    campaign=db.query(StaffingRecruitment).filter_by(vacancy_id=row.id).one_or_none()
    if campaign:
        raise OrderRequestError(409,"代替募集を始めた欠員は直接戻せません。募集の終了と参加者を確認してください")
    root_id,ids=family(db,row.root_series_id)
    if len(active_workers(db,ids,row.work_date)|{row.worker_id}) > capacity(db,root_id,row.work_date):
        raise OrderRequestError(409,"元の案件の上限を超えるため復帰できません")
    db.query(Worker).filter_by(id=row.worker_id).with_for_update().one()
    conflict=ws.visible_schedule_entries(db).filter(WorkerScheduleEntry.worker_id == row.worker_id,WorkerScheduleEntry.series_id.notin_(ids),WorkerScheduleEntry.work_date == row.work_date,WorkerScheduleEntry.is_test == entry.is_test,WorkerScheduleEntry.status.in_(("active","changing"))).first()
    if conflict: raise OrderRequestError(409,"同じ日に別案件の確定予定があります")
    row.status="cancelled"; row.revision+=1
    if row.selection_id: db.get(StaffingDecision,row.selection_id).status="confirmed"
    db.flush(); ws.rebuild(db,row.source_series_id,row.worker_id,actor=actor.username)
    AuditService(db).log("staffing_vacancy_cancelled",target_type="staffing_vacancy",target_id=row.id,actor=actor.username,actor_role=actor.role,reason=reason)
    db.flush()
    return detail(db,row.id)


def send(db,vacancy_id,version_id,revision,actor):
    """A separate, explicit operation after the prepared invitation can be reviewed."""
    from src.services.line_order import LineOrderService
    row=_row(db,vacancy_id,revision)
    _entry_for_vacancy(db,row)
    campaign=db.query(StaffingRecruitment).filter_by(vacancy_id=row.id).one_or_none()
    series=db.get(OrderRequestSeries,campaign.series_id) if campaign else None
    if row.status != "recruiting" or not series or series.answerable_version_id != version_id:
        raise OrderRequestError(409,"募集内容が変わりました。最新の依頼書を確認してください")
    service=LineOrderService(db)
    rows=db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == version_id,OrderRequestDelivery.ack_status == "unacked",OrderRequestDelivery.send_status.notin_(("accepted","unknown"))).order_by(OrderRequestDelivery.id).limit(20).all()
    sent=0; failures=0
    for delivery in rows:
        try:
            row=_row(db,vacancy_id,revision)
            _entry_for_vacancy(db,row)
            if row.status != "recruiting": break
            service.send_one(actor=actor,delivery=delivery)
            db.commit()
            if delivery.send_status == "accepted": sent+=1
            else: failures+=1
        except OrderRequestError:
            db.rollback()
            failures+=1
    remaining=db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == version_id,OrderRequestDelivery.ack_status == "unacked",OrderRequestDelivery.send_status.notin_(("accepted","unknown"))).count()
    unknown=db.query(OrderRequestDelivery).filter_by(version_id=version_id,send_status="unknown").count()
    return {"sent":sent,"failed":failures,"remaining":remaining,"unknown":unknown,"vacancy":detail(db,vacancy_id)}
