"""テスト依頼書8件をインセンティブありへ改訂。元のPDF・回答・金額は保持。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from src.models.master import User, Client
from src.models.order_request import OrderRequestVersion, OrderRequestDelivery
from src.models.line_daily import OrderRequestWorkerApplication
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoiceLine
from src.services.order_request_service import OrderRequestService
from src.services.order_billing import OrderBillingService
from src.services.order_request_format import parse_sections, incentive_details
from src.services.participation_calendar import build
from src.services.audit import AuditService
from src.services import worker_schedule as ws

DATASET = "calendar-demo-incentive-202610-v1"
REASON = "テスト用のインセンティブ入力例を追加（予定・回答は同じ状態を再現）"


def plan(db):
    eligible = [(v, d) for v, d in OrderBillingService(db).eligible(include_test=True)
        if d.kind == "test" and (v.counterparty_note or "").startswith("calendar-demo-")]
    enabled = [(v, d) for v, d in eligible if incentive_details(parse_sections(v.request_conditions))[0]]
    needed = max(0, 8 - len(enabled))
    candidates = []
    for version, document in eligible:
        if incentive_details(parse_sections(version.request_conditions))[0] or not version.internal_client_id:
            continue
        if not db.query(Client.id).filter(Client.id == version.internal_client_id, Client.deleted_at.is_(None)).first():
            continue
        if db.query(OrderRequestVersion.id).filter(OrderRequestVersion.document_id == document.id, OrderRequestVersion.version_no > version.version_no).first():
            continue  # 入力途中の版は保護
        if db.query(OrderBillingInvoiceLine.id).filter_by(series_id=version.series_id).first():
            continue
        if db.query(OrderBillingAmount.id).join(OrderRequestVersion, OrderRequestVersion.id == OrderBillingAmount.version_id).filter(OrderRequestVersion.series_id == version.series_id).first():
            continue
        deliveries = db.query(OrderRequestDelivery).filter_by(version_id=version.id).all()
        if not deliveries or any(d.send_status != "unknown" or d.view_revoked for d in deliveries):
            continue  # 結果不明のデモだけ。実送信や閲覧取消を保護
        dates = sorted({day["work_date"] for day in ws.version_work_days(version)})
        if dates and dates[0][:7] in ("2026-10", "2026-11"):
            candidates.append((version, document, dates[0]))
    candidates.sort(key=lambda row: (row[2], row[1].id))
    chosen = []
    # 両月で試せるよう、通常は10月4件・11月4件にする。
    for month in ("2026-10", "2026-11"):
        count = sum(bool(ws.version_work_days(v)) and min(day["work_date"] for day in ws.version_work_days(v)).startswith(month) for v, _ in enabled)
        month_rows = [row for row in candidates if row[2].startswith(month)]
        chosen.extend(month_rows[:min(max(0, 4 - count), needed - len(chosen))])
    for row in candidates:
        if len(chosen) >= needed:
            break
        if row not in chosen:
            chosen.append(row)
    if len(chosen) != needed:
        raise RuntimeError("未入力・未請求で他の操作を試していないテスト依頼が8件分そろいません。変更しません")
    return chosen, len(enabled)


def preview(db):
    chosen, existing = plan(db)
    return {"already_enabled": existing, "planned": [{"document_number": d.document_number,
        "project_name": (parse_sections(v.request_conditions) or {}).get("project_name", ""), "kind": d.kind} for v, d, _ in chosen]}


def fingerprint(db, series_id):
    return sorted((day["date"], state, p["worker_id"]) for day in build(db, series_id=series_id)
        for event in day["events"] for state in ("ok", "changing", "unanswered", "unavailable") for p in event[state])


def apply(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    chosen, existing = plan(db)
    actor = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    service = OrderRequestService(db)
    changed = []
    for source, document, _ in chosen:
        series = ws.lock_series(db, source.series_id)
        db.refresh(source)
        db.refresh(document)
        # プレビュー後やロック待ち中に金額入力・請求・改訂された場合も保護する。
        if (document.kind != "test" or document.deleted_at is not None or source.status != "confirmed" or series.answerable_version_id != source.id
            or db.query(OrderRequestVersion.id).filter(OrderRequestVersion.document_id == document.id, OrderRequestVersion.version_no > source.version_no).first()
            or db.query(OrderBillingInvoiceLine.id).filter_by(series_id=source.series_id).first()
            or db.query(OrderBillingAmount.id).join(OrderRequestVersion, OrderRequestVersion.id == OrderBillingAmount.version_id).filter(OrderRequestVersion.series_id == source.series_id).first()):
            raise RuntimeError("対象が別の操作で更新されています。変更はロールバックします")
        deliveries = {d.worker_id: d for d in db.query(OrderRequestDelivery).filter_by(version_id=source.id).populate_existing()}
        if any(d.send_status != "unknown" or d.view_revoked for d in deliveries.values()):
            raise RuntimeError("送付状態が変わっているため変更はロールバックします")
        before = fingerprint(db, source.series_id)
        applications = {a.worker_id: a.applied_delivery_id for a in db.query(OrderRequestWorkerApplication).filter_by(series_id=source.series_id).populate_existing()}
        conditions = json.loads(source.request_conditions)
        conditions["incentive_enabled"] = True
        conditions["incentive"] = "成果に応じた追加報酬あり（テスト用）。確定したインセンティブ額を通常請求額と分けて入力してください。"
        revised = service.revise(source, actor=actor, reason=REASON)
        revised.request_conditions = json.dumps(conditions, ensure_ascii=False)
        revised.body = ""
        revised.counterparty_note = f"{source.counterparty_note}:incentive-v1"
        service.confirm(revised, actor=actor)
        for delivery in db.query(OrderRequestDelivery).filter_by(version_id=revised.id):
            previous = deliveries[delivery.worker_id]
            if delivery.offered_dates != previous.offered_dates:
                raise RuntimeError("提示日が変わったため全体をロールバックします")
            delivery.send_status = "unknown"  # LINEの実送信は行わない
            delivery.ack_status = previous.ack_status
            delivery.acked_at = previous.acked_at
            delivery.decline_reason = previous.decline_reason
            delivery.ack_reminded_at = datetime.now(timezone.utc)
            state = ws.current_state(db, previous)
            if state is not None:
                ws.append_state(db, delivery, dates=list(state.dates), source="full_accept" if state.dates == delivery.offered_dates else "partial_accept", actor=actor.username, reason=REASON)
            if applications.get(delivery.worker_id) == previous.id:
                ws.set_application(db, series_id=source.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
        ws.rebuild_series(db, source.series_id, actor=actor.username)
        if fingerprint(db, source.series_id) != before:
            raise RuntimeError("参加・未回答・不参加の表示が変わるため全体をロールバックします")
        AuditService(db).log("calendar_demo_incentive_revised", target_type="order_request_version", target_id=revised.id,
            actor=actor.username, actor_role=actor.role, reason=REASON, before_value={"version_id":source.id,"incentive_enabled":False},
            after_value={"dataset":DATASET,"incentive_enabled":True,"document_id":document.id})
        changed.append({"document_number":document.document_number,"version_no":revised.version_no})
    db.flush()
    result = {"revised":len(changed),"already_enabled":existing,"enabled_demo_count":existing+len(changed),"documents":changed}
    return result


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = apply(session) if args.apply else preview(session)
        if args.apply:
            session.commit()
        print(json.dumps(result, ensure_ascii=False))
