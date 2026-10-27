"""確定した変更版を、旧版の受諾者へ送るまで運営に残す一覧。"""
from sqlalchemy.orm import aliased
from src.models.line_daily import OrderRequestSeries, OrderRequestWorkerApplication
from src.models.line_order import LineWorkerLink, LINK_ACTIVE
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion, OrderRequestDocument
from src.services import worker_schedule as ws


def pending_changes(db, *, kind="formal"):
    old = aliased(OrderRequestDelivery)
    rows = db.query(OrderRequestDelivery, OrderRequestVersion, OrderRequestDocument, old).join(
        OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id,
    ).join(OrderRequestSeries, OrderRequestSeries.answerable_version_id == OrderRequestVersion.id).join(
        OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id,
    ).join(OrderRequestWorkerApplication,
        (OrderRequestWorkerApplication.series_id == OrderRequestSeries.id) &
        (OrderRequestWorkerApplication.worker_id == OrderRequestDelivery.worker_id),
    ).join(old, old.id == OrderRequestWorkerApplication.applied_delivery_id).filter(
        OrderRequestDocument.deleted_at.is_(None), OrderRequestVersion.status == "confirmed",
        OrderRequestVersion.dispatch_stopped.is_(False), OrderRequestDelivery.view_revoked.is_(False),
        OrderRequestDelivery.ack_status == "unacked", OrderRequestDelivery.send_status != "accepted",
        old.version_id != OrderRequestVersion.id,
    )
    if kind != "all":
        rows = rows.filter(OrderRequestDocument.kind == kind)
    workers = {w.id: w.name for w in db.query(Worker)}
    linked = {r.worker_id for r in db.query(LineWorkerLink).filter_by(status=LINK_ACTIVE)}
    groups = {}
    for delivery, version, document, applied in rows.populate_existing().order_by(OrderRequestVersion.confirmed_at.desc(), OrderRequestDocument.id, OrderRequestDelivery.id):
        state = ws.current_state(db, applied)
        if state is None or not state.dates:
            continue
        group = groups.setdefault(version.id, {
            "version_id": version.id, "document_number": document.document_number, "kind": document.kind,
            "project_name": ws.version_display(version)["project_name"], "version_no": version.version_no,
            "recipients": [],
        })
        group["recipients"].append({"delivery_id": delivery.id, "worker_id": delivery.worker_id,
            "worker_name": workers.get(delivery.worker_id, delivery.worker_name_snapshot),
            "send_status": delivery.send_status, "line_linked": delivery.worker_id in linked,
            "can_send": delivery.send_status in ("unsent", "failed") and delivery.worker_id in linked})
    return list(groups.values())
