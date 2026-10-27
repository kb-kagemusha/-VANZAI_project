"""Copy reviewed conditions into a separate formal draft; never send from here."""
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.orm import aliased
from src.models.order_formalization import OrderFormalization
from src.models.order_request import OrderRequestDocument,OrderRequestVersion,OrderRequestDelivery
from src.models.order_staffing import StaffingLimit
from src.models.order_billing_daily import OrderBillingRateSetting
from src.models.staffing_replacement import StaffingRecruitment
from src.models.master import Worker
from src.services.order_request_service import OrderRequestService,OrderRequestError
from src.services import worker_schedule as ws
from src.services.audit import AuditService


def latest(db,document_id):
    return db.query(OrderRequestVersion).filter_by(document_id=document_id).order_by(OrderRequestVersion.version_no.desc()).first()


def relation(db,document_id):
    document=db.get(OrderRequestDocument,document_id)
    current=latest(db,document_id)
    origin=aliased(OrderRequestVersion)
    condition=(OrderFormalization.source_document_id == document_id)|(OrderFormalization.formal_document_id == document_id)
    if document and document.kind == "test" and current:
        condition=condition|(origin.series_id == current.series_id)
    row=db.query(OrderFormalization).join(origin,origin.id == OrderFormalization.source_version_id).filter(condition).first()
    if not row:return None
    test=db.get(OrderRequestDocument,row.source_document_id);formal=db.get(OrderRequestDocument,row.formal_document_id)
    target=latest(db,row.formal_document_id)
    return {"source_document_number":test.document_number,"source_version_id":row.source_version_id,"formal_document_number":formal.document_number,"formal_version_id":target.id,"formal_status":target.status,"formal_hidden":formal.deleted_at is not None}


def _source(db,version_id,write=False):
    source=OrderRequestService(db).get_version(version_id)
    if write:
        ws.lock_series(db,source.series_id)
        db.execute(select(OrderRequestDocument).where(OrderRequestDocument.id == source.document_id).with_for_update().execution_options(populate_existing=True)).scalar_one()
        db.refresh(source)
    document=db.get(OrderRequestDocument,source.document_id)
    if document.kind != "test" or document.deleted_at:
        raise OrderRequestError(409,"表示中のテスト案件から正式版を作成してください")
    return source,document


def _validate(db,source):
    newest=db.query(OrderRequestVersion).filter_by(series_id=source.series_id).order_by(OrderRequestVersion.created_at.desc(),OrderRequestVersion.id.desc()).first()
    if not newest or newest.id != source.id or source.status == "cancelled" or source.dispatch_stopped:
        raise OrderRequestError(409,"取消・送付停止されていない最新のテスト版を確認してください")
    if db.query(StaffingRecruitment.id).filter_by(series_id=source.series_id).first():
        raise OrderRequestError(409,"代替募集ではなく、元のテスト案件から正式版を作成してください")


def _snapshot(db,source):
    capacity={r.work_date.isoformat():r.capacity for r in db.query(StaffingLimit).filter_by(version_id=source.id)}
    setting=db.get(OrderBillingRateSetting,source.id)
    rates={"base_rate":str(setting.base_rate),"weekday_rates":dict(setting.weekday_rates)} if setting else None
    proof={"id":source.id,"updated_at":source.updated_at.isoformat(),"capacities":capacity,"rates_revision":setting.revision if setting else 0}
    return capacity,rates,hashlib.sha256(json.dumps(proof,sort_keys=True).encode()).hexdigest()


def preview(db,version_id,actor):
    source,document=_source(db,version_id)
    existing=relation(db,document.id)
    if existing:return {"existing":existing}
    _validate(db,source)
    capacity,rates,digest=_snapshot(db,source)
    ids=set(source.draft_worker_ids or [])|{r.worker_id for r in db.query(OrderRequestDelivery).filter_by(version_id=source.id)}
    return {"existing":None,"source_digest":digest,"document_number":document.document_number,"work_date_label":source.work_date_label,
        "request_conditions":source.request_conditions,"body":source.body,"site_name":source.site_name,"contact_name":source.contact_name,
        "capacities":{d["work_date"]:capacity.get(d["work_date"],0) for d in ws.version_work_days(source)},
        "source_candidates":[{"id":w.id,"name":w.name,"active":w.is_active and not w.deleted_at} for w in db.query(Worker).filter(Worker.id.in_(ids)).order_by(Worker.name)],
        "rate_reference":rates if actor.role == "admin" else None}


def create(db,version_id,*,source_digest,internal_source,worker_ids,capacities,masters_reviewed,follow_up_due_on,actor):
    source,document=_source(db,version_id,True)
    existing=relation(db,document.id)
    if existing:return db.get(OrderRequestVersion,existing["formal_version_id"])
    _validate(db,source)
    _,rates,digest=_snapshot(db,source)
    if source_digest != digest:raise OrderRequestError(409,"テスト内容または上限・単価が変わりました。画面を開き直して確認してください")
    if not masters_reviewed or not internal_source or not worker_ids:
        raise OrderRequestError(422,"正式な発注元と送付候補を選び、内容を確認してください")
    if follow_up_due_on < ws.today_jst():raise OrderRequestError(422,"正式版の回答期限は今日以降で設定してください")
    ids=list(dict.fromkeys(worker_ids))
    workers=db.query(Worker).filter(Worker.id.in_(ids),Worker.is_active.is_(True),Worker.deleted_at.is_(None)).all()
    if len(workers) != len(ids):raise OrderRequestError(422,"送付候補に無効な稼働者が含まれています。正式な候補を選び直してください")
    days={d["work_date"] for d in ws.version_work_days(source)}
    if set(capacities) != days or any(isinstance(v,bool) or not isinstance(v,int) or v<0 or v>10000 for v in capacities.values()):
        raise OrderRequestError(422,"稼働日ごとの募集上限を確認してください")
    version=OrderRequestService(db).create_draft(actor=actor,kind="formal",work_date_label=source.work_date_label,
        site_name=source.site_name,site_id=source.site_id,site_address=source.site_address,request_conditions=source.request_conditions,
        body=source.body,contact_name=source.contact_name,contact_desk=source.contact_desk,counterparty_note=source.counterparty_note,
        worker_ids=ids,phone_first=False,phone_contacted_at=None,phone_note=None,tracker_user_id=None,follow_up_due_on=follow_up_due_on,
        internal_source=internal_source,internal_source_set=True,recipient_absences={},allow_partial_accept=source.allow_partial_accept,requires_operator_confirmation=True)
    db.add(OrderFormalization(source_document_id=document.id,source_version_id=source.id,formal_document_id=version.document_id,
        capacity_snapshot=dict(capacities),rate_reference=rates,created_by=actor.id,created_at=ws.now_utc()))
    db.flush()
    AuditService(db).log("order_test_formalized",target_type="order_request_version",target_id=version.id,actor=actor.username,actor_role=actor.role,
        after_value={"source_document_id":document.id,"source_version_id":source.id,"formal_document_id":version.document_id,"candidate_ids":ids,"capacities":capacities,"status":"draft","sent":False})
    return version
