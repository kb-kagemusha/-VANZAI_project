"""2026年10・11月の閲覧デモ。既存マスタを利用し、LINE送信・実績・請求生成はしない。

本番は 02_app_deploy.sh --calendar-demo-preview / --calendar-demo-apply で実行。
通常デプロイでは実行しない。設定済み環境を利用し、秘密情報ファイルは開かない。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from src.models.master import Client, User, Worker
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.models.line_order import LineWorkerLink
from src.models.order_billing import OrderBillingInvoiceLine
from src.models.transaction import WorkerAvailability
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestService, render_order_request_pdf
from src.services.order_request_format import CATEGORY_OPTIONS, parse_sections
from src.services import worker_schedule as ws

DATASET = "calendar-demo-202610-v1"
MARKERS = ("サンプル", "テスト", "sample", "dummy", "デモ")


def sample_documents(db):
    """対象名のない依頼をサンプル扱いしない。照合出力は承認された3項目のみ。"""
    result = []
    for document in db.query(OrderRequestDocument).filter(OrderRequestDocument.deleted_at.is_(None)):
        version = db.query(OrderRequestVersion).filter_by(document_id=document.id).order_by(OrderRequestVersion.version_no.desc()).first()
        name = (parse_sections(version.request_conditions) or {}).get("project_name", "") if version else ""
        if any(marker in name.casefold() for marker in MARKERS):
            result.append((document, name))
    return result


def schedule(first, last):
    return {"version": 1, "rates_follow_work": True,
        "work_groups": [{"id": "w1", "date_mode": "range", "from": first, "to": last,
            "start_time": "09:00", "end_time": "17:00", "end_next_day": False, "gathering_time": "08:45", "notes": "テスト用", "excluded_dates": []}],
        "rate_groups": [{"id": "r1", "work_group_id": "w1", "date_mode": "range", "from": first, "to": last,
            "amount": "15000", "unit": "day", "lunch_included": True, "transport_included": True}]}


def seed(db, *, convert_existing=True):
    # 同時実行と再試行で二重作成しない。
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User).filter_by(role="admin", is_active=True).filter(User.deleted_at.is_(None)).order_by(User.id).first()
    linked = {wid for (wid,) in db.query(LineWorkerLink.worker_id).filter_by(status="active")}
    workers = db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.id).all()
    workers = [w for w in workers if w.id not in linked]
    client = db.query(Client).filter(Client.deleted_at.is_(None)).order_by(Client.id).first()
    if not actor or not workers or not client:
        raise RuntimeError("有効な管理者・LINE未連携の既存ダミー稼働者・依頼元が必要です")
    service = OrderRequestService(db)
    audit = AuditService(db)
    converted = 0
    if convert_existing:
        targets = [d for d, _ in sample_documents(db) if d.kind != "test"]
        # 会計に使用済みなら全体をロールバックし、個別の訂正判断を待つ。
        for document in targets:
            versions = db.query(OrderRequestVersion).filter_by(document_id=document.id).all()
            series_ids = {v.series_id for v in versions if v.series_id}
            if series_ids and db.query(OrderBillingInvoiceLine).filter(OrderBillingInvoiceLine.series_id.in_(series_ids)).first():
                raise RuntimeError("サンプルに請求書明細の利用履歴があります。区分変更は停止しました")
        for document in targets:
            document.kind = "test"
            for version in db.query(OrderRequestVersion).filter_by(document_id=document.id):
                if not version.snapshot_json:
                    continue
                snap = version.snapshot_json
                key = f"order-requests/{document.document_number}/v{version.version_no}-test-{DATASET}.pdf"
                if service.storage.exists(key):
                    raise RuntimeError("変換先PDFが既にあります。旧PDFは上書きしません")
                content = render_order_request_pdf(document_number=document.document_number, version_no=version.version_no, kind="test",
                    work_date_label=snap.get("work_date_label", version.work_date_label), site_name=snap.get("site_name", version.site_name),
                    site_address=snap.get("site_address"), request_conditions=snap.get("request_conditions", version.request_conditions),
                    body=snap.get("body", version.body), contact_name=snap.get("contact_name", version.contact_name),
                    contact_desk=snap.get("contact_desk", version.contact_desk), counterparty_note=snap.get("counterparty_note"),
                    worker_names=snap.get("worker_names", []), created_at=version.created_at, **service._notice_pdf_kwargs(version))
                old_key = version.pdf_object_key
                service.storage.save_bytes(key, content)
                version.pdf_object_key = key
                audit.log("calendar_demo_pdf_reclassified", target_type="order_request_version", target_id=version.id,
                    actor=actor.username, actor_role=actor.role, reason="ユーザー指定: 既存サンプルをテストへ変更",
                    before_value={"pdf_object_key": old_key}, after_value={"pdf_object_key": key})
            audit.log("calendar_demo_reclassified", target_type="order_request_document", target_id=document.id,
                actor=actor.username, actor_role=actor.role, reason="ユーザー指定: 既存サンプルをテストへ変更",
                before_value={"kind": "formal"}, after_value={"kind": "test", "dataset": DATASET})
            converted += 1
    created = 0
    names = ["秋のグルメ巡回", "駅前喫煙所サポート", "商業施設キャンペーン", "オータム音楽フェス", "街頭リサーチ", "販促履行チェック", "新人導入研修",
             "飲食店フォロー巡回", "駐車場ご案内", "たばこ店プロモーション", "週末フードフェス", "来場者アンケート", "店頭掲示確認", "接客基礎研修", "月末スポーツフェス"]
    for month in (10, 11):
        for index, name in enumerate(names):
            marker = f"{DATASET}:{month}:{index}"
            if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
                continue
            first = date(2026, month, 1) + timedelta(days=index * 2)
            last = first + timedelta(days=(3 if index == 14 else index % 3))
            category = CATEGORY_OPTIONS[index % 7]
            categories = [category] + (["研修"] if category != "研修" and index % 3 == 0 else [])
            chosen = [workers[(index * 3 + offset) % len(workers)] for offset in range(min(3 + index % 4, len(workers)))]
            conditions = {"format": "additional-request-v1", "project_name": f"【テスト】{month}月 {name}", "categories": categories,
                "background": "画面確認用の架空イベント", "meeting_place": "会場の受付（架空）", "schedule": schedule(first.isoformat(), last.isoformat()),
                "incentive_enabled": False}
            version = service.create_draft(actor=actor, kind="test", work_date_label="", site_name=f"テスト会場{index % 5 + 1}",
                site_id=None, site_address=None, request_conditions=json.dumps(conditions, ensure_ascii=False), body="", contact_name="テスト担当",
                contact_desk="", counterparty_note=marker, worker_ids=[w.id for w in chosen], phone_first=False, phone_contacted_at=None,
                phone_note=None, tracker_user_id=None, follow_up_due_on=date(2026, 12, 31),
                internal_source={"client_id": client.id, "client_staff_id": None}, internal_source_set=True, allow_partial_accept=True)
            service.confirm(version, actor=actor)
            for pos, delivery in enumerate(db.query(OrderRequestDelivery).filter_by(version_id=version.id).all()):
                # unknown は送信成功を偽装せず表示を試せる状態。催促対象はacceptedのみ。
                delivery.send_status = "unknown"
                delivery.ack_reminded_at = datetime.now(timezone.utc)
                if pos % 3 != 2:
                    delivery.ack_status = "acked"
                    delivery.acked_at = datetime.now(timezone.utc)
                    offered = delivery.offered_dates or []
                    selected = offered[::2] if pos % 3 == 1 else offered
                    ws.append_state(db, delivery, dates=selected, source=ws.SOURCE_FULL_ACCEPT, actor=actor.username, reason="テスト参加状態・実送信なし")
                    ws.set_application(db, series_id=version.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
            # 一部を改訂し、旧版受諾者の変更確認待ちを再現。
            if index % 5 == 0:
                revised = service.revise(version, actor=actor, reason="テスト: 集合場所の変更確認")
                revised.counterparty_note = marker + ":revision"
                service.confirm(revised, actor=actor)
                for delivery in db.query(OrderRequestDelivery).filter_by(version_id=revised.id):
                    delivery.send_status = "unknown"
                    delivery.ack_reminded_at = datetime.now(timezone.utc)
            audit.log("calendar_demo_created", target_type="order_request_version", target_id=version.id, actor=actor.username,
                actor_role=actor.role, reason="カレンダー画面確認用", after_value={"dataset": DATASET, "is_test": True, "sent": False})
            created += 1
    # 既存の出勤可否は保持し、空いている日だけを埋める。タグは空の人にだけ追加。
    availability_created = 0
    for index, worker in enumerate(workers):
        if not worker.tags:
            worker.tags = ["newcomer"] if index % 4 == 0 else ["event_small_d", "food_d", "event_medium_d"][index % 3:index % 3 + 1]
            if "newcomer" in worker.tags:
                worker.newcomer_until = date(2027, 1, 23)
            audit.log("calendar_demo_worker_tags", target_type="worker", target_id=worker.id, actor=actor.username,
                actor_role=actor.role, before_value={"tags": []}, after_value={"tags": worker.tags}, reason="既存ダミー稼働者の表示確認")
        day = date(2026, 10, 1)
        while day <= date(2026, 11, 30):
            if not db.query(WorkerAvailability.id).filter_by(worker_id=worker.id, availability_date=day).first():
                statuses = ("available_all_day", "available_all_day", "unavailable", "available_after_15", "consult_required")
                db.add(WorkerAvailability(worker_id=worker.id, availability_date=day, status=statuses[(day.day + index) % 5], notes=DATASET))
                db.flush()
                availability_created += 1
            day += timedelta(days=1)
    audit.log("calendar_demo_seeded", target_type="calendar_demo", target_id=DATASET, actor=actor.username, actor_role=actor.role,
        after_value={"created": created, "converted": converted, "availability_created": availability_created}, reason="2026年10・11月 各15件のテスト")
    return {"created": created, "converted": converted, "availability_created": availability_created}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from src.api.deps import SessionLocal
    with SessionLocal() as db:
        if args.apply:
            result = seed(db)
            db.commit()
            print(json.dumps(result))
        else:
            for document, name in sample_documents(db):
                print(json.dumps({"document_number": document.document_number, "project_name": name, "kind": document.kind}, ensure_ascii=False))


if __name__ == "__main__":
    main()
