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
BALANCED_DATASET = "calendar-demo-202610-v2"
MARKERS = ("サンプル", "テスト", "sample", "dummy", "デモ")
REQUESTED_WORKERS = ("テストアカウント", "坂井貴博")
DEMO_EXTRA_NAMES = (("渡邊 健太郎", "わたなべ けんたろう"), ("長谷川 亜香里", "はせがわ あかり"), ("岡田 直人", "おかだ なおと"), ("松本 彩乃", "まつもと あやの"))


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


def seed(db, *, convert_existing=True, per_month=15, prune_legacy_samples=False, include_long_events=False):
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
            for series_id in sorted(series_ids):
                ws.lock_series(db, series_id)
                ws.rebuild_series(db, series_id, actor=actor.username)
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
    long_events_created = 0
    long_event_samples = []
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
        indices = list(range(per_month)) + ([45, 46, 47] if include_long_events else [])
        for index in indices:
            is_long = index >= 45
            if is_long:
                name, start_day, duration, category = (
                    ("10日間の商業施設プロモーション", 5, 9, "商業施設/たばこ屋"),
                    ("20日間の飲食店巡回", 10, 19, "飲食店巡回"),
                    ("月またぎ20日間の秋イベント運営", 24, 19, "フェス系"),
                )[index - 45]
                first = date(2026, month, start_day)
                last = first + timedelta(days=duration)
            else:
                name = names[index] if index < 15 else themes[index % 7][index // 7]
                offset = index - 15
                start_offset = index * 2 if index < 15 else (offset * 7 + offset // 7 * 3) % 29
                first = date(2026, month, 1) + timedelta(days=start_offset)
                duration = (3 if index == 14 else index % 3) if index < 15 else 1 + offset % 4
                last = first + timedelta(days=duration)
                category = CATEGORY_OPTIONS[index % 7]
            marker = f"{DATASET}:{month}:{index}"
            if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
                continue
            categories = [category] + (["研修"] if category != "研修" and index % 3 == 0 else [])
            chosen = [workers[(index * 3 + offset) % len(workers)] for offset in range(min(8 if is_long else 3 + index % 4, len(workers)))]
            if is_long:
                chosen += [w for w in workers if re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS and w not in chosen]
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
                    ws.rebuild(db, version.series_id, delivery.worker_id, actor=actor.username)
            # 一部を改訂し、旧版受諾者の変更確認待ちを再現。
            if not is_long and index % 5 == 0:
                revised = service.revise(version, actor=actor, reason="テスト: 集合場所の変更確認")
                revised.counterparty_note = marker + ":revision"
                service.confirm(revised, actor=actor)
                for delivery in db.query(OrderRequestDelivery).filter_by(version_id=revised.id):
                    delivery.send_status = "unknown"
                    delivery.ack_reminded_at = datetime.now(timezone.utc)
            audit.log("calendar_demo_created", target_type="order_request_version", target_id=version.id, actor=actor.username,
                actor_role=actor.role, reason="カレンダー画面確認用", after_value={"dataset": DATASET, "is_test": True, "sent": False})
            created += 1
            if is_long:
                long_events_created += 1
                actual_days = sorted({day["work_date"] for day in ws.version_work_days(version)})
                long_event_samples.append({"document_number": service._document(version).document_number,
                    "name": conditions["project_name"], "from": actual_days[0], "to": actual_days[-1], "days": len(actual_days)})
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
        while day <= (date(2026, 12, 13) if include_long_events else date(2026, 11, 30)):
            if not db.query(WorkerAvailability.id).filter_by(worker_id=worker.id, availability_date=day).first():
                statuses = ("available_all_day", "available_all_day", "unavailable", "available_after_15", "consult_required")
                db.add(WorkerAvailability(worker_id=worker.id, availability_date=day, status=statuses[(day.day + index) % 5], notes=DATASET))
                db.flush()
                availability_created += 1
            day += timedelta(days=1)
    audit.log("calendar_demo_seeded", target_type="calendar_demo", target_id=DATASET, actor=actor.username, actor_role=actor.role,
        after_value={"created": created, "converted": converted, "archived": archived, "per_month": per_month,
            "long_events_created": long_events_created, "availability_created": availability_created}, reason=f"2026年10・11月 各{per_month}件＋長期予定のテスト")
    requested = {w.name: w.id for w in workers if re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS}
    from src.services.participation_calendar import build
    calendar = build(db, start="2026-10-01", end="2026-11-30", include_test=True) if requested else []
    requested_days = {name: len({day["date"] for day in calendar for event in day["events"] for state in ("ok", "changing")
        for person in event[state] if person["worker_id"] == identifier}) for name, identifier in requested.items()}
    return {"created": created, "converted": converted, "archived": archived, "per_month": per_month,
        "worker_count": len(workers), "long_events_created": long_events_created, "long_event_samples": long_event_samples,
        "availability_created": availability_created, "requested_worker_days": requested_days}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from src.api.deps import SessionLocal
    with SessionLocal() as db:
        if args.apply:
            result = seed(db, per_month=45, prune_legacy_samples=True, include_long_events=True)
            result["balanced"] = rebalance_demo(db)
            db.commit()
            print(json.dumps(result))
        else:
            for document, name in sample_documents(db):
                print(json.dumps({"document_number": document.document_number, "project_name": name, "kind": document.kind}, ensure_ascii=False))


def rebalance_demo(db):
    """同じ9〜17時のテスト依頼を1人1日1件に組み直す。旧版/PDFは保持する。"""
    from collections import defaultdict
    from src.models.line_daily import OrderRequestSeries
    from src.services.participation_calendar import build

    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User).filter_by(role="admin", is_active=True).filter(User.deleted_at.is_(None)).order_by(User.id).first()
    audit = AuditService(db)
    added_workers = 0
    for index in range(1, 5):
        name, furigana = DEMO_EXTRA_NAMES[index - 1]
        legacy_name = f"【テスト】追加スタッフ{index:02d}"
        if not db.query(Worker.id).filter(Worker.name.in_((name, legacy_name))).first():
            worker = Worker(name=name, furigana=furigana, is_active=True, tags=["newcomer"] if index < 3 else ["event_small_d"],
                newcomer_until=date(2027, 1, 23) if index < 3 else None)
            db.add(worker)
            db.flush()
            audit.log("calendar_demo_worker_created", target_type="worker", target_id=worker.id, actor=actor.username, actor_role=actor.role,
                reason="ユーザー指定: 同日重複を解消するダミー稼働者4名", after_value={"dataset": BALANCED_DATASET})
            added_workers += 1
    linked = {wid for (wid,) in db.query(LineWorkerLink.worker_id).filter_by(status="active")}
    workers = [w for w in db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.id)
        if w.id not in linked or re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS]
    sources = db.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.like(DATASET + ":%"),
        ~OrderRequestVersion.counterparty_note.like("%:revision")).all()
    source_documents = {v.document_id for v in sources}
    occupied = defaultdict(set)
    for day in build(db, start="2026-10-01", end="2026-12-13", include_test=True):
        for event in day["events"]:
            if event["document_id"] in source_documents:
                continue
            for state in ("ok", "changing", "unanswered", "unavailable"):
                for person in event[state]:
                    occupied[person["worker_id"]].add(day["date"])
    tasks = []
    for source in sources:
        marker = source.counterparty_note.replace(DATASET, BALANCED_DATASET, 1)
        if db.query(OrderRequestVersion.id).filter_by(counterparty_note=marker).first():
            continue
        document = db.get(OrderRequestDocument, source.document_id)
        if document.kind != "test" or document.deleted_at is not None:
            continue
        if db.query(OrderBillingInvoiceLine.id).filter_by(series_id=source.series_id).first():
            raise RuntimeError("再配置対象が請求書で使用済みのため停止しました")
        series = db.get(OrderRequestSeries, source.series_id)
        latest = db.get(OrderRequestVersion, series.answerable_version_id)
        dates = sorted({d["work_date"] for d in ws.version_work_days(latest)})
        tasks.append((source, latest, marker, dates))
    # 指定2名には、他の依頼と重ならない長期予定を先に予約する。
    reserved = {}
    for worker in workers:
        if re.sub(r"\s+", "", worker.name) not in REQUESTED_WORKERS:
            continue
        for month in ("2026-10", "2026-11"):
            for task in sorted(tasks, key=lambda task: (-len(task[3]), task[2])):
                dates = task[3]
                if len(dates) >= 10 and dates[0].startswith(month) and not occupied[worker.id].intersection(dates):
                    reserved[(worker.id, task[2])] = set(dates)
                    occupied[worker.id].update(dates)
                    break
    # 開始日順に割り当て、同時稼働数に余裕のある1〜3名の規模にする。
    tasks.sort(key=lambda task: (task[3][0], -len(task[3]), task[2]))
    planned = []
    for source, latest, marker, dates in tasks:
        free = [w for w in workers if not (occupied[w.id] - reserved.get((w.id, marker), set())).intersection(dates)]
        # 指定2名も、予定が重ならない範囲で優先する。
        free.sort(key=lambda w: (0 if (w.id, marker) in reserved else 1,
            0 if re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS else 1, len(occupied[w.id]), w.id))
        count = 3 if len(dates) >= 10 else 1 + int(marker.rsplit(":", 1)[1]) % 3
        chosen = free[:count]
        if not chosen:
            raise RuntimeError("同日1件で配置できる稼働者が不足しました。部分更新せず停止しました")
        for worker in chosen:
            occupied[worker.id].update(dates)
        planned.append((source, latest, marker, dates, chosen))
    service = OrderRequestService(db)
    for source, latest, marker, dates, chosen in planned:
        snap = latest.snapshot_json or {}
        version = service.create_draft(actor=actor, kind="test", work_date_label="", site_name=snap.get("site_name", latest.site_name),
            site_id=latest.site_id, site_address=snap.get("site_address", latest.site_address),
            request_conditions=snap.get("request_conditions", latest.request_conditions), body="", contact_name=latest.contact_name,
            contact_desk=latest.contact_desk, counterparty_note=marker, worker_ids=[w.id for w in chosen], phone_first=False,
            phone_contacted_at=None, phone_note=None, tracker_user_id=None, follow_up_due_on=date(2026, 12, 31),
            internal_source={"client_id": latest.internal_client_id, "client_staff_id": latest.internal_client_staff_id},
            internal_source_set=True, allow_partial_accept=True)
        service.confirm(version, actor=actor)
        for pos, delivery in enumerate(db.query(OrderRequestDelivery).filter_by(version_id=version.id)):
            delivery.send_status = "unknown"
            delivery.ack_reminded_at = datetime.now(timezone.utc)
            requested = any(w.id == delivery.worker_id and re.sub(r"\s+", "", w.name) in REQUESTED_WORKERS for w in chosen)
            if pos == 2 and int(marker.rsplit(":", 1)[1]) % 4 == 0 and not requested:
                delivery.ack_status = "declined"
                delivery.decline_reason = "テスト: 参加不可"
            elif pos != 2 or requested:
                delivery.ack_status = "acked"
                delivery.acked_at = datetime.now(timezone.utc)
                selected = dates[::2] if pos == 1 and not requested else dates
                ws.append_state(db, delivery, dates=selected, source="partial_accept" if selected != dates else "full_accept",
                    actor=actor.username, reason="ダミー予定の同日重複解消")
                ws.set_application(db, series_id=version.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
                ws.rebuild(db, version.series_id, delivery.worker_id, actor=actor.username)
        if int(marker.rsplit(":", 1)[1]) < 45 and int(marker.rsplit(":", 1)[1]) % 5 == 0:
            revised = service.revise(version, actor=actor, reason="テスト: 変更確認待ちの表示")
            revised.counterparty_note = marker + ":revision"
            service.confirm(revised, actor=actor)
            for delivery in db.query(OrderRequestDelivery).filter_by(version_id=revised.id):
                delivery.send_status = "unknown"
                delivery.ack_reminded_at = datetime.now(timezone.utc)
        document = db.get(OrderRequestDocument, source.document_id)
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by_user_id = actor.id
        ws.rebuild_series(db, source.series_id, actor=actor.username)
        audit.log("calendar_demo_rebalanced", target_type="order_request_document", target_id=document.id, actor=actor.username, actor_role=actor.role,
            reason="ユーザー指定: 原則1人1日1件のダミー予定に置換・旧PDF保持", after_value={"replacement_document_id": version.document_id, "dataset": BALANCED_DATASET})
    # 新規の4名にも可否表示を補完する。既存の入力は上書きしない。
    for worker in workers:
        day = date(2026, 10, 1)
        while day <= date(2026, 12, 13):
            row = db.query(WorkerAvailability).filter_by(worker_id=worker.id, availability_date=day).first()
            if row is None:
                db.add(WorkerAvailability(worker_id=worker.id, availability_date=day, status="available_all_day" if day.isoformat() in occupied[worker.id] else "undecided", notes=BALANCED_DATASET))
                db.flush()
            day += timedelta(days=1)
    db.flush()
    by_worker_day = defaultdict(set)
    requested_days = defaultdict(set)
    for day in build(db, start="2026-10-01", end="2026-12-13", include_test=True):
        for event in day["events"]:
            for state in ("ok", "changing", "unanswered", "unavailable"):
                for person in event[state]:
                    by_worker_day[(person["worker_id"], day["date"])].add(event["series_id"])
                    if re.sub(r"\s+", "", person["name"]) in REQUESTED_WORKERS and state in ("ok", "changing"):
                        requested_days[person["name"]].add(day["date"])
    max_events = max((len(events) for events in by_worker_day.values()), default=0)
    if max_events > 1:
        raise RuntimeError("同日重複が残ったため、デモの置換をロールバックします")
    result = {"created": len(planned), "archived": len(planned), "workers_added": added_workers, "worker_count": len(workers),
        "max_events_per_worker_day": max_events, "requested_worker_days": {name: len(days) for name, days in requested_days.items()}}
    audit.log("calendar_demo_rebalance_completed", target_type="calendar_demo", target_id=BALANCED_DATASET, actor=actor.username,
        actor_role=actor.role, reason="原則1人1日1件", after_value=result)
    return result


if __name__ == "__main__":
    main()
