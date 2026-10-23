"""2026年10・11月の閲覧デモ。既存マスタを利用し、LINE送信・実績・請求生成はしない。

本番は 02_app_deploy.sh --calendar-demo-preview / --calendar-demo-apply で実行。
通常デプロイでは実行しない。設定済み環境を利用し、秘密情報ファイルは開かない。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import re
import unicodedata
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
REQUESTED_WORKERS = ("テストアカウント", "坂井貴博")


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


def seed(db, *, convert_existing=True, per_month=15, prune_legacy_samples=False):
    if per_month not in (15, 45):
        raise ValueError("デモ件数は15件または45件を指定してください")
    # 同時実行と再試行で二重作成しない。
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User).filter_by(role="admin", is_active=True).filter(User.deleted_at.is_(None)).order_by(User.id).first()
    linked = {wid for (wid,) in db.query(LineWorkerLink.worker_id).filter_by(status="active")}
    workers = db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.id).all()
    workers = [w for w in workers if w.id not in linked or re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS]
    client = db.query(Client).filter(Client.deleted_at.is_(None)).order_by(Client.id).first()
    if not actor or not workers or not client:
        raise RuntimeError("有効な管理者・LINE未連携の既存ダミー稼働者・依頼元が必要です")
    service = OrderRequestService(db)
    audit = AuditService(db)
    archived = 0
    if prune_legacy_samples:
        # ユーザーが作成した同内容の旧「サンプルイベント」だけを整理する。
        # 日付やカテゴリの異なるデータセット由来のテスト依頼は対象外。
        legacy = sorted(
            (d for d, name in sample_documents(db)
             if d.kind == "test" and re.fullmatch(r"サンプルイベント\d*", unicodedata.normalize("NFKC", name).strip())),
            key=lambda d: (d.created_at, d.id),
        )
        for document in legacy[1:]:
            versions = db.query(OrderRequestVersion).filter_by(document_id=document.id).all()
            series_ids = {v.series_id for v in versions if v.series_id}
            if series_ids and db.query(OrderBillingInvoiceLine).filter(OrderBillingInvoiceLine.series_id.in_(series_ids)).first():
                raise RuntimeError("整理対象のサンプルが請求書で使用済みです。変更を停止しました")
            document.deleted_at = datetime.now(timezone.utc)
            document.deleted_by_user_id = actor.id
            audit.log("calendar_demo_duplicate_archived", target_type="order_request_document", target_id=document.id,
                actor=actor.username, actor_role=actor.role, reason="ユーザー指定: 旧サンプルイベントは1件のみ残す",
                before_value={"deleted_at": None}, after_value={"retained_document_id": legacy[0].id, "is_test": True})
            archived += 1
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
    themes = (
        ("駅前グルメ巡回", "居酒屋チェーン訪問", "レストラン街フォロー", "ランチ店販促巡回", "カフェ新商品案内", "飲食店週末サポート", "深秋グルメキャンペーン"),
        ("駅南口パーキング案内", "公園喫煙所運営", "商店街駐車場受付", "繁華街喫煙所サポート", "臨時駐車場のご案内", "駅北口喫煙所巡回", "週末パーキング運営"),
        ("ショッピングモール販促", "駅ビル展示ブース", "たばこ店商品説明", "商業施設抽選会", "専門店街キャンペーン", "アウトレットPR", "百貨店新商品案内"),
        ("川沿いミュージックフェス", "秋の収穫フェス", "市民スポーツフェス", "クラフトフードフェス", "ナイトマーケット", "アートフェス受付", "週末ファミリーフェス"),
        ("駅利用者アンケート", "商圏リサーチ", "新商品モニター調査", "来場者動向調査", "商店街ヒアリング", "公園利用者調査", "買い物行動調査"),
        ("販促物設置チェック", "店舗掲示の履行確認", "キャンペーン実施確認", "売場展示チェック", "配布状況の履行確認", "店頭販促ラウンド", "月末実施報告チェック"),
        ("新人接客ロールプレイ", "会場運営の基礎研修", "安全誘導研修", "調査手順の実習", "リーダー導入研修", "商品説明の実習", "現場フォロー研修"),
    )
    for month in (10, 11):
        for index in range(per_month):
            name = names[index] if index < 15 else themes[index % 7][index // 7]
            marker = f"{DATASET}:{month}:{index}"
            if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
                continue
            offset = index - 15
            start_offset = index * 2 if index < 15 else (offset * 7 + offset // 7 * 3) % 29
            first = date(2026, month, 1) + timedelta(days=start_offset)
            duration = (3 if index == 14 else index % 3) if index < 15 else 1 + offset % 4
            last = first + timedelta(days=duration)
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
                requested_worker = delivery.worker_id in {w.id for w in workers if re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS}
                if index >= 15 and pos % 4 == 3 and not requested_worker:
                    delivery.ack_status = "declined"
                    delivery.decline_reason = "テスト: 日程が合わないため参加不可"
                elif pos % 3 != 2 or requested_worker:
                    delivery.ack_status = "acked"
                    delivery.acked_at = datetime.now(timezone.utc)
                    offered = delivery.offered_dates or []
                    selected = offered[::2] if pos % 3 == 1 and not requested_worker else offered
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
        after_value={"created": created, "converted": converted, "archived": archived, "per_month": per_month, "availability_created": availability_created}, reason=f"2026年10・11月 各{per_month}件のテスト")
    requested = {w.name: w.id for w in workers if re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS}
    from src.services.participation_calendar import build
    calendar = build(db, start="2026-10-01", end="2026-11-30", include_test=True) if requested else []
    requested_days = {name: len({day["date"] for day in calendar for event in day["events"] for state in ("ok", "changing")
        for person in event[state] if person["worker_id"] == identifier}) for name, identifier in requested.items()}
    return {"created": created, "converted": converted, "archived": archived, "per_month": per_month,
        "availability_created": availability_created, "requested_worker_days": requested_days}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from src.api.deps import SessionLocal
    with SessionLocal() as db:
        if args.apply:
            result = seed(db, per_month=45, prune_legacy_samples=True)
            db.commit()
            print(json.dumps(result))
        else:
            for document, name in sample_documents(db):
                print(json.dumps({"document_number": document.document_number, "project_name": name, "kind": document.kind}, ensure_ascii=False))


if __name__ == "__main__":
    main()
