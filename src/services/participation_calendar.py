"""運営の参加カレンダー（統合計画 ①、A1+ §3.5、D-07）。

イベント（系列）ごとに、日ごとの人数を重ならない4つに分けて数える。今の状態で判定する（過去に受諾したかでは判定しない）。
- 参加OK：適用送付行が回答受付版で、その日が今の参加日に入る
- 参加OK・変更確認待ち：適用送付行が旧い版（回答受付版は未回答）で、その日が旧い版の参加日に入る
- 未回答：今有効な受諾がなく、回答受付版の送付行が送付済み・未回答で、その日が提示日に入る
- 参加不可：明示の個別NG・辞退・部分受諾の非選択勤務日（共通休業日を除く）
同じ人は同じ日・同じ系列でどれか1つにだけ入る（系列×日付×稼働者で重複を除く）。既定は正式のみ、include_test指定時はテストも含む。
参加者が0人の日も、回答受付版の稼働日なら0人として返す。
"""
from __future__ import annotations

from collections import defaultdict
from src.domain.worker_tags import is_newcomer_from_start, tokyo_today, is_director

from sqlalchemy.orm import Session

from src.models.line_daily import OrderRequestSeries, OrderRequestWorkerApplication, OrderRequestApplicationEnd
from src.models.order_request import (
    ACK_DECLINE_PENDING,
    ACK_DECLINED,
    ACK_ACKED,
    ACK_UNACKED,
    KIND_FORMAL,
    SEND_ACCEPTED,
    SEND_UNKNOWN,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services import worker_schedule as ws
from src.services.order_request_format import parse_sections

OK = "ok"
CHANGING = "changing"
UNANSWERED = "unanswered"
UNAVAILABLE = "unavailable"


def _in_range(day: str, start: str | None, end: str | None) -> bool:
    return (start is None or day >= start) and (end is None or day <= end)


def registered_workers(session: Session) -> list[dict]:
    """登録のある（有効な）稼働者全員と、LINEの連携の有無（俯瞰カレンダーの稼働者ごとの表示で使う）。ふりがな・名前の順。"""
    from src.models.line_order import LINK_ACTIVE, LineWorkerLink
    from src.models.master import Worker

    linked = {wid for (wid,) in session.query(LineWorkerLink.worker_id).filter(LineWorkerLink.status == LINK_ACTIVE).all()}
    workers = session.query(Worker).filter(Worker.is_active.is_(True)).all()
    workers.sort(key=lambda w: ((w.furigana or w.name or ""), w.name or ""))
    today = tokyo_today()
    return [{"worker_id": w.id, "name": w.name, "line_linked": w.id in linked, "is_newcomer": is_newcomer_from_start(w.available_start_date, today), "is_director": is_director(w.tags)} for w in workers]


def build(session: Session, *, start: str | None = None, end: str | None = None, series_id: str | None = None, include_test: bool = False, test_only: bool = False) -> list[dict]:
    """日付ごとに、イベントの人数と名前を返す。[{date, events: [{series_id, version_id, document_number, project_name, ok, changing, unanswered}]}]"""
    query = session.query(OrderRequestSeries)
    if series_id:
        query = query.filter(OrderRequestSeries.id == series_id)
    from src.models.master import Worker
    workers = session.query(Worker).all()
    worker_names = {w.id: w.name for w in workers}
    today = tokyo_today()
    newcomers = {w.id: is_newcomer_from_start(w.available_start_date, today) for w in workers}
    directors = {w.id: is_director(w.tags) for w in workers}
    days: dict[str, dict[str, dict]] = defaultdict(dict)
    for series in query.all():
        if series.answerable_version_id is not None:
            answerable = session.get(OrderRequestVersion, series.answerable_version_id)
        else:
            ending = session.query(OrderRequestApplicationEnd).filter_by(series_id=series.id).order_by(OrderRequestApplicationEnd.ended_at.desc(), OrderRequestApplicationEnd.id.desc()).first()
            if ending is None:
                continue
            answerable = session.get(OrderRequestVersion, ending.source_version_id)
        document = session.get(OrderRequestDocument, answerable.document_id)
        # 月のカレンダーは正式だけ。依頼書ごとの確認（series_id 指定）はテストも表示する
        if test_only and document.kind == KIND_FORMAL:
            continue
        if (document.kind != KIND_FORMAL and not series_id and not include_test and not test_only) or document.deleted_at is not None:
            continue
        display = ws.version_display(answerable)
        # 稼働者ごとの分類と日付
        buckets: list[tuple[str, str, set[str], str]] = []
        bucket_dates: dict[str, set[str]] = defaultdict(set)
        unavailable: dict[str, tuple[set[str], str]] = {}
        work_dates = {d["work_date"] for d in ws.version_work_days(answerable)} if series.answerable_version_id else set()
        applications = (
            session.query(OrderRequestWorkerApplication)
            .filter(OrderRequestWorkerApplication.series_id == series.id, OrderRequestWorkerApplication.applied_delivery_id.is_not(None))
            .all()
        )
        applied_workers = {app.worker_id for app in applications}
        for worker_id in ws.series_workers(session, series.id):
            for delivery, dates, status, _state_id in ws.participation_sources(session, series.id, worker_id):
                kind = OK if status == "active" else CHANGING
                name = worker_names.get(worker_id, delivery.worker_name_snapshot)
                source_version = session.get(OrderRequestVersion, delivery.version_id)
                if source_version.requires_operator_confirmation:
                    from src.models.order_staffing import StaffingDecision
                    decisions = {d.work_date.isoformat(): d.status for d in session.query(StaffingDecision).filter_by(version_id=source_version.id, worker_id=worker_id)}
                    for day in dates:
                        decision = decisions.get(day)
                        if decision == "confirmed":
                            buckets.append((worker_id, kind, {day}, name))
                        elif decision is None:
                            buckets.append((worker_id, "pending", {day}, name))
                        else:
                            buckets.append((worker_id, UNAVAILABLE, {day}, name))
                else:
                    buckets.append((worker_id, kind, dates, name))
                bucket_dates[worker_id].update(dates)
        current_deliveries = session.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == answerable.id).all() if series.answerable_version_id else []
        for delivery in current_deliveries:
            if delivery.view_revoked:
                continue
            # 個別NG日は共通休業日を除く。未回答をNGと推測しない。
            refused = set((answerable.draft_recipient_absences or {}).get(delivery.worker_id, [])) & work_dates
            offered = set(delivery.offered_dates or []) & work_dates
            if delivery.ack_status == ACK_DECLINED:
                refused |= offered
            elif delivery.ack_status == ACK_ACKED:
                state = ws.current_state(session, delivery)
                if state is not None:
                    refused |= offered - set(state.dates)
            if refused:
                unavailable[delivery.worker_id] = (refused, worker_names.get(delivery.worker_id, delivery.worker_name_snapshot))
            if delivery.worker_id in applied_workers:
                continue
            if delivery.send_status not in (SEND_ACCEPTED, SEND_UNKNOWN) or delivery.ack_status not in (ACK_UNACKED, ACK_DECLINE_PENDING):
                continue
            if delivery.offered_dates is None:
                continue
            unanswered_dates = set(delivery.offered_dates) - bucket_dates[delivery.worker_id]
            buckets.append((delivery.worker_id, UNANSWERED, unanswered_dates, worker_names.get(delivery.worker_id, delivery.worker_name_snapshot)))
            bucket_dates[delivery.worker_id].update(unanswered_dates)
        def event_of(day: str) -> dict:
            return days[day].setdefault(
                series.id,
                {
                    "series_id": series.id,
                    "version_id": answerable.id,
                    "document_id": document.id,
                    "document_number": document.document_number,
                    "project_name": display["project_name"],
                    "site_name": display.get("site_name") or "",
                    "is_test": document.kind != KIND_FORMAL,
                    "categories": (parse_sections(answerable.request_conditions) or {}).get("categories", []),
                    "pending": [],
                    OK: [],
                    CHANGING: [],
                    UNANSWERED: [],
                    UNAVAILABLE: [],
                },
            )

        # 参加者が0人の日も日程として表示する（回答受付版の実勤務日）
        for day in work_dates:
            if _in_range(day, start, end):
                event_of(day)
        for worker_id, kind, dates, name in buckets:
            for day in set(dates):
                if not _in_range(day, start, end):
                    continue
                event_of(day)[kind].append({"worker_id": worker_id, "name": name, "is_newcomer": newcomers.get(worker_id, False), "is_director": directors.get(worker_id, False)})
        for worker_id, (dates, name) in unavailable.items():
            assigned_dates = bucket_dates.get(worker_id, set())
            for day in dates - assigned_dates:
                if _in_range(day, start, end):
                    event_of(day)[UNAVAILABLE].append({"worker_id": worker_id, "name": name, "is_newcomer": newcomers.get(worker_id, False), "is_director": directors.get(worker_id, False)})
    result = []
    for day in sorted(days):
        events = sorted(days[day].values(), key=lambda e: (e["project_name"], e["document_number"]))
        for event in events:
            for kind in (OK, CHANGING, UNANSWERED, UNAVAILABLE, "pending"):
                event[kind].sort(key=lambda w: w["name"])
        result.append({"date": day, "events": events})
    return result
