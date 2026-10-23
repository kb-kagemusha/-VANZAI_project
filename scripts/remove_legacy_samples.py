"""以前の旧サンプルだけを運用から除去し、受諾・過去を含む派生予定も解除する。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import unicodedata
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text, or_
from src.models.master import User
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.models.line_daily import OrderRequestSeries, OrderRequestWorkerApplication, WorkerScheduleEntry
from src.models.line_order import OrderRequestFileToken
from src.models.order_billing import OrderBillingInvoiceLine
from src.models.attendance_note import AttendanceNote
from src.services.audit import AuditService
from src.services.order_request_format import parse_sections
from src.services import worker_schedule as ws

REASON = "ユーザー指定: 以前のサンプルイベントを受諾・稼働予定も含めて全件削除"


def sample_name(name):
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name or ""))
    return bool(re.fullmatch(r"(?:【テスト】|\[テスト\])?サンプルイベント\d*", normalized))


def candidates(db):
    # 非表示の旧依頼も対象。本文や個人情報を出力しない。
    result = []
    candidate_ids = db.query(OrderRequestVersion.document_id).filter(or_(
        OrderRequestVersion.request_conditions.contains("サンプル", autoescape=True),
        OrderRequestVersion.request_conditions.contains(r"\u30b5\u30f3\u30d7\u30eb", autoescape=True),
    ))
    for document in db.query(OrderRequestDocument).filter(OrderRequestDocument.id.in_(candidate_ids)).order_by(OrderRequestDocument.document_number):
        version = db.query(OrderRequestVersion).filter_by(document_id=document.id).order_by(OrderRequestVersion.version_no.desc()).first()
        name = str((parse_sections(version.request_conditions) or {}).get("project_name", "")) if version else ""
        if "サンプルイベント" in unicodedata.normalize("NFKC", name).replace(" ", ""):
            result.append((document, name))
    return result


def preview(db):
    return [{"document_number": d.document_number, "project_name": name, "kind": d.kind} for d, name in candidates(db)]


def purge(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    targets = candidates(db)
    actor = db.query(User.id, User.username, User.role).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if not actor:
        raise RuntimeError("有効な管理者が必要です")
    ids = {doc.id for doc, _ in targets}
    versions = db.query(OrderRequestVersion).filter(OrderRequestVersion.document_id.in_(ids)).all() if ids else []
    for doc, name in targets:
        if not sample_name(name):
            raise RuntimeError("サンプルイベントの名称に追加文言があります。対象を確認するまで変更しません")
    for version in versions:
        name = str((parse_sections(version.request_conditions) or {}).get("project_name", ""))
        if not sample_name(name) or (version.counterparty_note or "").startswith("calendar-demo-"):
            raise RuntimeError("旧サンプル以外の版を含むため停止しました")
    series_ids = {v.series_id for v in versions if v.series_id}
    if series_ids:
        if db.query(OrderBillingInvoiceLine.id).filter(OrderBillingInvoiceLine.series_id.in_(series_ids)).first():
            raise RuntimeError("請求書に使用済みの旧サンプルがあります。会計は変更しません")
        if db.query(AttendanceNote.id).filter(AttendanceNote.series_id.in_(series_ids), AttendanceNote.voided_at.is_(None)).first():
            raise RuntimeError("勤怠報告に使用中の旧サンプルがあります。報告は変更しません")
        if db.query(OrderRequestVersion.id).join(OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id).filter(
            OrderRequestVersion.series_id.in_(series_ids), OrderRequestVersion.document_id.notin_(ids), OrderRequestDocument.deleted_at.is_(None)).first():
            raise RuntimeError("同じ系列に旧サンプル以外の有効な依頼があります。変更しません")
    for series_id in sorted(series_ids):
        ws.lock_series(db, series_id)
    audit = AuditService(db)
    now = datetime.now(timezone.utc)
    touched = set()
    before_entries = db.query(WorkerScheduleEntry).filter(WorkerScheduleEntry.document_id.in_(ids), WorkerScheduleEntry.status.in_(("active", "changing"))).count() if ids else 0
    cleared_states = 0
    removed_applications = 0
    revoked_tokens = 0
    for version in versions:
        if version.status != "cancelled" or not version.dispatch_stopped:
            before = {"status":version.status,"dispatch_stopped":version.dispatch_stopped}
            version.status = "cancelled"
            version.dispatch_stopped = True
            version.cancel_reason = REASON
            version.cancelled_at = now
            version.cancelled_by_user_id = actor.id
            touched.add(version.document_id)
            audit.log("legacy_sample_version_cancelled", target_type="order_request_version", target_id=version.id,
                actor=actor.username, actor_role=actor.role, reason=REASON, before_value=before,
                after_value={"status":"cancelled","dispatch_stopped":True})
        for delivery in db.query(OrderRequestDelivery).filter_by(version_id=version.id):
            state = ws.current_state(db, delivery)
            if state and state.dates:
                ws.append_state(db, delivery, dates=[], source="ops_recorded_decline", actor=actor.username, reason=REASON)
                cleared_states += 1
                touched.add(version.document_id)
            if not delivery.view_revoked:
                delivery.view_revoked = True
                touched.add(version.document_id)
            for token in db.query(OrderRequestFileToken).filter_by(delivery_id=delivery.id, revoked_at=None):
                token.revoked_at = now
                revoked_tokens += 1
                touched.add(version.document_id)
    for series_id in sorted(series_ids):
        series = db.get(OrderRequestSeries, series_id)
        if series.answerable_version_id:
            source = db.get(OrderRequestVersion, series.answerable_version_id)
            if source.document_id not in ids:
                raise RuntimeError("対象外の回答受付版は取り消せません")
            series.answerable_version_id = None
            touched.add(source.document_id)
        for app in db.query(OrderRequestWorkerApplication).filter_by(series_id=series_id):
            if app.applied_delivery_id:
                version = db.get(OrderRequestVersion, app.applied_version_id)
                if version.document_id not in ids:
                    raise RuntimeError("対象外の適用受諾は取り消せません")
                ws.set_application(db, series_id=series_id, worker_id=app.worker_id, delivery=None, ended_reason=ws.END_DOCUMENT_ENDED, actor=actor.username)
                removed_applications += 1
                touched.add(version.document_id)
        ws.rebuild_series(db, series_id, actor=actor.username)
    for doc, _ in targets:
        if doc.deleted_at is None:
            doc.deleted_at = now
            doc.deleted_by_user_id = actor.id
            touched.add(doc.id)
    db.flush()
    remaining = db.query(WorkerScheduleEntry.id).filter(WorkerScheduleEntry.document_id.in_(ids), WorkerScheduleEntry.status.in_(("active", "changing"))).count() if ids else 0
    if remaining:
        raise RuntimeError("対象の有効な稼働予定が残っているためロールバックします")
    for identifier in touched:
        audit.log("legacy_sample_removed", target_type="order_request_document", target_id=identifier,
            actor=actor.username, actor_role=actor.role, reason=REASON, after_value={"hidden":True,"current_acceptance_cleared":True,"active_entries":0})
    result = {"matched_documents":len(ids),"changed_documents":len(touched),"participation_states_cleared":cleared_states,
        "applications_removed":removed_applications,"schedule_entries_removed":before_entries,"active_entries_remaining":remaining,"tokens_revoked":revoked_tokens}
    return result


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = purge(session) if args.apply else preview(session)
        if args.apply:
            session.commit()
        print(json.dumps(result, ensure_ascii=False))
