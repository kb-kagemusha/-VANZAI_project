"""運営の参加カレンダー（統合計画 ①、A1+ §3.5、D-07）。

イベント（系列）ごとに、日ごとの人数を重ならない3つに分けて数える。今の状態で判定する（過去に受諾したかでは判定しない）。
- 参加OK：適用送付行が回答受付版で、その日が今の参加日に入る
- 参加OK・変更確認待ち：適用送付行が旧い版（回答受付版は未回答）で、その日が旧い版の参加日に入る
- 未回答：今有効な受諾がなく、回答受付版の送付行が送付済み・未回答で、その日が提示日に入る
同じ人は同じ日・同じ系列でどれか1つにだけ入る（系列×日付×稼働者で重複を除く）。正式の依頼書だけ。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from src.models.line_daily import OrderRequestSeries, OrderRequestWorkerApplication
from src.models.order_request import (
    ACK_DECLINE_PENDING,
    ACK_UNACKED,
    KIND_FORMAL,
    SEND_ACCEPTED,
    SEND_UNKNOWN,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services import worker_schedule as ws

OK = "ok"
CHANGING = "changing"
UNANSWERED = "unanswered"


def _in_range(day: str, start: str | None, end: str | None) -> bool:
    return (start is None or day >= start) and (end is None or day <= end)


def build(session: Session, *, start: str | None = None, end: str | None = None, series_id: str | None = None) -> list[dict]:
    """日付ごとに、イベントの人数と名前を返す。[{date, events: [{series_id, version_id, document_number, project_name, ok, changing, unanswered}]}]"""
    query = session.query(OrderRequestSeries).filter(OrderRequestSeries.answerable_version_id.is_not(None))
    if series_id:
        query = query.filter(OrderRequestSeries.id == series_id)
    days: dict[str, dict[str, dict]] = defaultdict(dict)
    for series in query.all():
        answerable = session.get(OrderRequestVersion, series.answerable_version_id)
        document = session.get(OrderRequestDocument, answerable.document_id)
        if document.kind != KIND_FORMAL or document.deleted_at is not None:
            continue
        display = ws.version_display(answerable)
        # 稼働者ごとの分類と日付
        buckets: dict[str, tuple[str, list[str], str]] = {}
        applications = (
            session.query(OrderRequestWorkerApplication)
            .filter(OrderRequestWorkerApplication.series_id == series.id, OrderRequestWorkerApplication.applied_delivery_id.is_not(None))
            .all()
        )
        for app in applications:
            delivery = session.get(OrderRequestDelivery, app.applied_delivery_id)
            state = ws.current_state(session, delivery)
            dates = list(state.dates) if state is not None else []
            kind = OK if delivery.version_id == series.answerable_version_id else CHANGING
            buckets[app.worker_id] = (kind, dates, delivery.worker_name_snapshot)
        for delivery in session.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == answerable.id).all():
            if delivery.worker_id in buckets:
                continue
            if delivery.send_status not in (SEND_ACCEPTED, SEND_UNKNOWN) or delivery.ack_status not in (ACK_UNACKED, ACK_DECLINE_PENDING):
                continue
            if delivery.offered_dates is None:
                continue
            buckets[delivery.worker_id] = (UNANSWERED, list(delivery.offered_dates), delivery.worker_name_snapshot)
        for worker_id, (kind, dates, name) in buckets.items():
            for day in set(dates):
                if not _in_range(day, start, end):
                    continue
                event = days[day].setdefault(
                    series.id,
                    {
                        "series_id": series.id,
                        "version_id": answerable.id,
                        "document_id": document.id,
                        "document_number": document.document_number,
                        "project_name": display["project_name"],
                        OK: [],
                        CHANGING: [],
                        UNANSWERED: [],
                    },
                )
                event[kind].append({"worker_id": worker_id, "name": name})
    result = []
    for day in sorted(days):
        events = sorted(days[day].values(), key=lambda e: (e["project_name"], e["document_number"]))
        for event in events:
            for kind in (OK, CHANGING, UNANSWERED):
                event[kind].sort(key=lambda w: w["name"])
        result.append({"date": day, "events": events})
    return result
