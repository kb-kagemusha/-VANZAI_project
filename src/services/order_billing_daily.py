"""Explicit customer rates × reviewed actual person-days. No inference from worker pay."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from sqlalchemy import or_
from src.models.order_billing_daily import OrderBillingRateSetting, OrderBillingDailyLine, OrderBillingActualClaim
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoiceLine, OrderBillingInvoice
from src.models.order_request import OrderRequestVersion, OrderRequestDocument
from src.models.transaction import Project, Actual, Assignment, ShiftSlot, Closing
from src.models.master import Worker
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestError
from src.services.financial_guards import lock_projects, ensure_unallocated
from src.exceptions import ValidationException

MONEY=Decimal("0.01")
MAX_AMOUNT=Decimal("9999999999999.99")
def _version(db,version_id,write=False):
    from src.services.order_billing import OrderBillingService
    service=OrderBillingService(db)
    if write:
        service.lock()
        version=db.get(OrderRequestVersion,version_id)
        if not version: raise OrderRequestError(404,"依頼書が見つかりません")
        ws.lock_series(db,version.series_id)
    pair=next(((v,d) for v,d in service.eligible(include_test=True) if v.id == version_id),None)
    if not pair: raise OrderRequestError(409,"最新の有効な依頼書を確認してください。代替募集は元案件で請求します")
    version,document=pair
    days=sorted({d["work_date"] for d in ws.version_work_days(version)})
    if not days: raise OrderRequestError(409,"日付別の稼働日がありません。依頼書の日程を確認してください")
    return version,document,days


def _project(db,version,project_id):
    project=db.get(Project,project_id)
    if not project or project.deleted_at or project.client_id != version.internal_client_id:
        raise OrderRequestError(422,"依頼書と同じクライアントの実績案件を選んでください")
    return project


def _mutable(db,version,project_id,days):
    previous=db.get(OrderBillingRateSetting,version.id)
    projects={project_id} | ({previous.project_id} if previous else set())
    current=db.query(OrderBillingAmount).join(OrderRequestVersion,OrderBillingAmount.version_id == OrderRequestVersion.id).filter(OrderRequestVersion.series_id == version.series_id).order_by(OrderBillingAmount.created_at.desc(),OrderBillingAmount.revision.desc()).first()
    claims=db.query(OrderBillingActualClaim).filter_by(series_id=version.series_id,active=True).all()
    projects.update(c.project_id for c in claims)
    if current and current.snapshot.get("actual_project_id"): projects.add(current.snapshot["actual_project_id"])
    lock_projects(db,projects)
    if db.query(OrderBillingInvoiceLine.id).filter_by(active_series_id=version.series_id).first():
        raise OrderRequestError(409,"請求書に含まれています。下書きは取り消してから確認し、発行済みは変更しないでください")
    pairs={(project_id,d[:7].replace("-","")) for d in days}
    pairs.update((c.project_id,c.work_date.strftime("%Y%m")) for c in claims)
    if current and current.snapshot.get("actual_project_id"):
        pairs.update((current.snapshot["actual_project_id"],line.work_date.strftime("%Y%m")) for line in db.query(OrderBillingDailyLine).filter_by(amount_id=current.id))
    if current:
        for target,period in sorted(pairs):
            if db.query(Closing.id).filter(Closing.period_key == period,or_(Closing.project_id == target,Closing.project_id.is_(None)),Closing.status.in_(("soft_closed","hard_closed"))).first():
                raise OrderRequestError(409,"実績の案件・月が締め済みです。金額を変える前に既存の締め解除・訂正の手順を確認してください")


def setting_out(row):
    return {"project_id":row.project_id,"base_rate":str(row.base_rate),"weekday_rates":dict(row.weekday_rates),"revision":row.revision} if row else None


def state(db,version_id):
    version,document,days=_version(db,version_id)
    row=db.get(OrderBillingRateSetting,version_id)
    amount=db.query(OrderBillingAmount).filter_by(version_id=version_id).order_by(OrderBillingAmount.revision.desc()).first()
    return {"setting":setting_out(row),"dates":days,"is_test":document.kind == "test","client_id":version.internal_client_id,
        "previous_days":frozen_lines(db,amount.id) if amount and amount.snapshot.get("mode") == "person_day" else [],
        "projects":[{"id":p.id,"name":p.name,"code":p.code} for p in db.query(Project).filter(Project.client_id == version.internal_client_id,Project.deleted_at.is_(None)).order_by(Project.name,Project.id)]}


def save_setting(db,version_id,project_id,base_rate,weekday_rates,revision,reason,actor):
    actor_id,actor_name,actor_role=actor.id,actor.username,actor.role
    version,document,days=_version(db,version_id,True)
    _project(db,version,project_id);_mutable(db,version,project_id,days)
    row=db.query(OrderBillingRateSetting).filter_by(version_id=version_id).with_for_update().populate_existing().one_or_none()
    if revision != (row.revision if row else 0): raise OrderRequestError(409,"単価設定が変更されました。最新の設定を確認してください")
    if row and not reason.strip(): raise OrderRequestError(422,"単価設定を変更する理由を入力してください")
    if not set(weekday_rates) <= {str(n) for n in range(7)} or base_rate < 0 or any(v < 0 for v in weekday_rates.values()):
        raise OrderRequestError(422,"基本単価と月〜日の単価を確認してください")
    before=setting_out(row)
    if not row:
        row=OrderBillingRateSetting(version_id=version_id,revision=0)
        db.add(row)
    row.project_id=project_id;row.base_rate=base_rate
    row.weekday_rates={k:str(v) for k,v in weekday_rates.items()}
    row.revision+=1;row.updated_by=actor_id;row.updated_at=ws.now_utc()
    db.flush()
    AuditService(db).log("order_billing_daily_rates_changed",target_type="order_request_version",target_id=version_id,actor=actor.username,actor_role=actor.role,
        reason=reason,before_value=before,after_value=setting_out(row))
    return state(db,version_id)


def source(db,version,project_id,days,*,for_update=False):
    project=_project(db,version,project_id)
    query=db.query(Actual,Assignment,ShiftSlot).outerjoin(Assignment,Actual.assignment_id == Assignment.id).outerjoin(ShiftSlot,Assignment.shift_slot_id == ShiftSlot.id).filter(Actual.project_id == project_id,Actual.work_date.in_([date.fromisoformat(d) for d in days]),Actual.status == "active").order_by(Actual.work_date,Actual.worker_id,Actual.id)
    if for_update: query=query.with_for_update(of=Actual)
    rows=query.populate_existing().all()
    workers={w.id:w.name for w in db.query(Worker).filter(Worker.id.in_({a.worker_id for a,_,_ in rows}))} if rows else {}
    grouped=defaultdict(dict);proof=[];excluded=0;needs_review=0
    for actual,assignment,slot in rows:
        valid=bool(assignment and slot and not assignment.deleted_at and not slot.deleted_at and assignment.status != "canceled"
            and slot.project_id == project_id and assignment.worker_id == actual.worker_id and slot.work_date == actual.work_date and actual.period_key == actual.work_date.strftime("%Y%m"))
        proof.append({"id":actual.id,"worker_id":actual.worker_id,"date":actual.work_date.isoformat(),"assignment_id":actual.assignment_id,
            "assignment_status":assignment.status if assignment else None,"valid":valid,"needs_review":actual.needs_review,"updated_at":actual.updated_at.isoformat()})
        if not valid: excluded+=1;continue
        needs_review+=int(actual.needs_review)
        person=grouped[actual.work_date.isoformat()].setdefault(actual.worker_id,{"worker_id":actual.worker_id,"name":workers.get(actual.worker_id,""),"actual_ids":[],"minutes":0})
        person["actual_ids"].append(actual.id);person["minutes"]+=actual.calc_minutes_billable
    digest=hashlib.sha256(json.dumps({"project_id":project_id,"dates":days,"actuals":proof},sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"project_id":project_id,"project_name":project.name,"source_digest":digest,"excluded_count":excluded,"needs_review":needs_review,
        "days":[{"date":d,"quantity":len(grouped[d]),"workers":list(grouped[d].values())} for d in days]}


def preview(db,version_id,*,for_update=False):
    version,document,days=_version(db,version_id)
    setting=db.get(OrderBillingRateSetting,version_id)
    if not setting: raise OrderRequestError(409,"先に基本単価と実績の案件を設定してください")
    value=source(db,version,setting.project_id,days,for_update=for_update)
    for day in value["days"]:
        weekday=date.fromisoformat(day["date"]).weekday()
        unit=Decimal(setting.weekday_rates.get(str(weekday),str(setting.base_rate)))
        day.update(weekday=weekday,unit_price=str(unit),subtotal=str((day["quantity"]*unit).quantize(MONEY)))
    value.update(rates_revision=setting.revision,base_rate=str(setting.base_rate),weekday_rates=setting.weekday_rates,is_test=document.kind == "test")
    return value


def is_current(db,amount):
    if amount.snapshot.get("mode") != "person_day": return True
    setting=db.get(OrderBillingRateSetting,amount.version_id)
    if not setting or setting.revision != amount.snapshot.get("rates_revision"): return False
    version=db.get(OrderRequestVersion,amount.version_id)
    days=sorted({d["work_date"] for d in ws.version_work_days(version)})
    try: current=source(db,version,setting.project_id,days)
    except OrderRequestError: return False
    if not amount.snapshot.get("is_test"):
        ids=[identifier for day in current["days"] for worker in day["workers"] for identifier in worker["actual_ids"]]
        try: ensure_unallocated(db,ids,"invoice",exclude_order_series_ids=(version.series_id,))
        except ValidationException: return False
    return current["source_digest"] == amount.snapshot.get("source_digest") and not current["needs_review"]


def confirm(db,version_id,*,billing_month,source_digest,rates_revision,expected_revision,adjustments,confirm_zero_days,reason,incentive_amount,actor):
    from src.services.order_billing import OrderBillingService
    version,document,dates=_version(db,version_id,True)
    setting=db.get(OrderBillingRateSetting,version_id)
    if not setting: raise OrderRequestError(409,"単価設定がありません")
    _mutable(db,version,setting.project_id,dates)
    if document.kind != "test" and any(d > ws.today_jst().isoformat() for d in dates):
        raise OrderRequestError(409,"確定実績で請求するため、全稼働日の終了後に人数を確認してください")
    current=preview(db,version_id,for_update=True)
    if source_digest != current["source_digest"] or rates_revision != setting.revision:
        raise OrderRequestError(409,"実績または単価が変わりました。人数と明細を読み直して確認してください")
    if current["needs_review"]: raise OrderRequestError(409,"要確認の実績があります。実績を確認してから金額を確定してください")
    if document.kind != "test":
        ids=[identifier for day in current["days"] for worker in day["workers"] for identifier in worker["actual_ids"]]
        try: ensure_unallocated(db,ids,"invoice",exclude_order_series_ids=(version.series_id,))
        except ValidationException as exc: raise OrderRequestError(409,str(exc)) from None
    if any(d["quantity"] == 0 for d in current["days"]) and (not confirm_zero_days or not reason.strip()):
        raise OrderRequestError(422,"実績0人の日があります。無稼働を確認し、記録メモを入力してください")
    if not set(adjustments) <= set(dates): raise OrderRequestError(422,"稼働日以外の調整が含まれています")
    lines=[]
    for day in current["days"]:
        adjustment=adjustments.get(day["date"],{})
        difference=Decimal(str(adjustment.get("amount",0)))
        note=adjustment.get("reason","").strip()
        if difference and not note: raise OrderRequestError(422,"調整額の理由を入力してください")
        subtotal=(Decimal(day["subtotal"])+difference).quantize(MONEY)
        if subtotal < 0 or subtotal > MAX_AMOUNT: raise OrderRequestError(422,"日別の税抜金額を確認してください")
        lines.append({**day,"adjustment":str(difference),"adjustment_reason":note,"subtotal":str(subtotal)})
        if document.kind != "test" and day["quantity"]:
            key=(setting.project_id,date.fromisoformat(day["date"]))
            claim=db.get(OrderBillingActualClaim,key)
            if claim and claim.active and claim.series_id != version.series_id:
                raise OrderRequestError(409,"同じ実績の案件・日付が、別の依頼書ですでに金額確定されています。二重には請求できません")
            if not claim: db.add(OrderBillingActualClaim(project_id=key[0],work_date=key[1],series_id=version.series_id,active=True,created_at=ws.now_utc()))
            elif not claim.active:
                claim.series_id=version.series_id;claim.active=True;claim.created_at=ws.now_utc()
    total=sum((Decimal(d["subtotal"]) for d in lines),Decimal(0))
    if total > MAX_AMOUNT: raise OrderRequestError(422,"通常請求額が保存可能な上限を超えています")
    metadata={"mode":"person_day","formula_version":1,"rates_revision":setting.revision,"base_rate":str(setting.base_rate),"weekday_rates":dict(setting.weekday_rates),
        "source_digest":current["source_digest"],"actual_project_id":setting.project_id,"actual_project_name":current["project_name"],"excluded_count":current["excluded_count"]}
    amount=OrderBillingService(db).save_amount(version_id,billing_month=billing_month,amount=total,expected_revision=expected_revision,reason=reason,incentive_amount=incentive_amount,actor=actor,_daily_context=metadata)
    if document.kind != "test":
        retained={(setting.project_id,date.fromisoformat(d["date"])) for d in lines if d["quantity"]}
        for claim in db.query(OrderBillingActualClaim).filter_by(series_id=version.series_id,active=True):
            if (claim.project_id,claim.work_date) not in retained:
                claim.active=False
                AuditService(db).log("order_billing_actual_claim_released",target_type="order_request_series",target_id=version.series_id,actor=actor.username,actor_role=actor.role,reason=reason,
                    after_value={"project_id":claim.project_id,"date":claim.work_date.isoformat(),"new_amount_id":amount.id})
    for day in lines:
        db.add(OrderBillingDailyLine(amount_id=amount.id,work_date=date.fromisoformat(day["date"]),quantity=day["quantity"],unit_price=Decimal(day["unit_price"]),adjustment=Decimal(day["adjustment"]),adjustment_reason=day["adjustment_reason"],subtotal=Decimal(day["subtotal"]),source_snapshot={"workers":day["workers"],"weekday":day["weekday"]}))
    db.flush()
    AuditService(db).log("order_billing_daily_amount_confirmed",target_type="order_billing_amount",target_id=amount.id,actor=actor.username,actor_role=actor.role,reason=reason,
        after_value={**metadata,"amount":str(total),"days":lines})
    return {"id":amount.id,"revision":amount.revision,"amount":str(amount.amount),"days":lines}


def frozen_lines(db,amount_id):
    return [{"date":line.work_date.isoformat(),"quantity":line.quantity,"unit_price":str(line.unit_price),"adjustment":str(line.adjustment),"adjustment_reason":line.adjustment_reason,
        "subtotal":str(line.subtotal),"workers":line.source_snapshot["workers"],"weekday":line.source_snapshot["weekday"]}
        for line in db.query(OrderBillingDailyLine).filter_by(amount_id=amount_id).order_by(OrderBillingDailyLine.work_date)]
