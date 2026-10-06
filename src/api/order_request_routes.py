"""発注依頼書 API。画面と取得は admin / ops。保存先URLでは PDF を返さない。"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.enums import UserRole
from src.models.master import User
from src.models.order_request import (
    ACK_UNACKED,
    SEND_UNSENT,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestNote,
    OrderRequestVersion,
)
from src.services.line_messaging import line_settings
from src.services.line_order import (
    LINK_INSTRUCTION,
    PURPOSE_TEXT,
    UNLINK_TEXT,
    LineOrderService,
    active_line_labels,
    latest_send_errors,
)
from src.services.order_request_format import parse_sections
from src.services.order_request_pdf import (
    TEMPLATE_LAYOUT_APPLIED,
    attachment_content_disposition,
    order_request_pdf_filename,
    project_name_from_document,
)
from src.services.order_request_service import (
    OrderRequestError,
    OrderRequestService,
    follow_up_time_label,
)

router = APIRouter(prefix="/api/order-requests", tags=["Order Requests"])

_ROLES = {UserRole.ADMIN.value, UserRole.OPS.value}


class OrderRequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "formal"
    work_date_label: str = ""
    site_id: str | None = None
    site_name: str = ""
    site_address: str | None = None
    request_conditions: str = ""
    body: str = ""
    contact_name: str = ""
    contact_desk: str = ""
    counterparty_note: str | None = None
    worker_ids: list[str] = Field(default_factory=list)
    phone_first: bool = False
    phone_contacted_at: datetime | None = None
    phone_note: str | None = None
    tracker_user_id: str | None = None
    follow_up_due_on: date | None = None
    follow_up_due_time: str | None = "21:00"
    assign_tracker_self: bool = False


class OrderRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str | None = None
    work_date_label: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    site_address: str | None = None
    request_conditions: str | None = None
    body: str | None = None
    contact_name: str | None = None
    contact_desk: str | None = None
    counterparty_note: str | None = None
    worker_ids: list[str] | None = None
    phone_first: bool | None = None
    phone_contacted_at: datetime | None = None
    phone_note: str | None = None
    tracker_user_id: str | None = None
    follow_up_due_on: date | None = None
    follow_up_due_time: str | None = None
    assign_tracker_self: bool | None = None


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str


class LineLinkCodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: str


def _ensure(user: User) -> None:
    if user.role not in _ROLES:
        raise HTTPException(status_code=403, detail="発注依頼書へのアクセス権限がありません")


def _service(db: Session) -> OrderRequestService:
    return OrderRequestService(db)


def _call(db: Session, action):
    try:
        result = action()
        db.commit()
        return result
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _user_map(db: Session, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = db.query(User).filter(User.id.in_(user_ids)).all()
    return {row.id: row.display_name or row.username for row in rows}


def _delivery_out(
    row: OrderRequestDelivery,
    links: dict[str, str | None],
    errors: dict[str, str | None],
) -> dict:
    return {
        "id": row.id,
        "worker_id": row.worker_id,
        "worker_name_snapshot": row.worker_name_snapshot,
        "send_status": row.send_status,
        "ack_status": row.ack_status,
        "acked_at": row.acked_at,
        "decline_reason": row.decline_reason,
        "ack_reminded_at": row.ack_reminded_at,
        "view_revoked": row.view_revoked,
        "line_linked": row.worker_id in links,
        "line_display_name": links.get(row.worker_id),
        "last_send_error": errors.get(row.id),
    }


def _note_out(row: OrderRequestNote, names: dict[str, str]) -> dict:
    return {
        "id": row.id,
        "author_user_id": row.author_user_id,
        "author_name": names.get(row.author_user_id),
        "body": row.body,
        "created_at": row.created_at,
    }


def _version_out(
    db: Session,
    document: OrderRequestDocument,
    version: OrderRequestVersion,
) -> dict:
    deliveries = (
        db.query(OrderRequestDelivery)
        .filter(OrderRequestDelivery.version_id == version.id)
        .order_by(OrderRequestDelivery.worker_name_snapshot)
        .all()
    )
    notes = (
        db.query(OrderRequestNote)
        .filter(OrderRequestNote.version_id == version.id)
        .order_by(OrderRequestNote.created_at)
        .all()
    )
    names = _user_map(
        db,
        {
            document.created_by_user_id,
            version.created_by_user_id,
            version.tracker_user_id,
            version.confirmed_by_user_id,
            version.cancelled_by_user_id,
            *[note.author_user_id for note in notes],
        }
        - {None},
    )
    links = active_line_labels(db, {row.worker_id for row in deliveries})
    errors = latest_send_errors(db, {row.id for row in deliveries})
    return {
        "document_id": document.id,
        "document_number": document.document_number,
        "kind": document.kind,
        "id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "revision_of_version_id": version.revision_of_version_id,
        "revision_reason": version.revision_reason,
        "work_date_label": version.work_date_label,
        "site_id": version.site_id,
        "site_name": version.site_name,
        "site_address": version.site_address,
        "request_conditions": version.request_conditions,
        "body": version.body,
        "contact_name": version.contact_name,
        "contact_desk": version.contact_desk,
        "counterparty_note": version.counterparty_note,
        "draft_worker_ids": list(version.draft_worker_ids or []),
        "phone_first": version.phone_first,
        "phone_contacted_at": version.phone_contacted_at,
        "phone_note": version.phone_note,
        "tracker_user_id": version.tracker_user_id,
        "tracker_name": names.get(version.tracker_user_id or ""),
        "follow_up_due_on": version.follow_up_due_on,
        "follow_up_due_time": follow_up_time_label(version.follow_up_due_at),
        "confirmed_at": version.confirmed_at,
        "confirmed_by_name": names.get(version.confirmed_by_user_id or ""),
        "cancelled_at": version.cancelled_at,
        "cancel_reason": version.cancel_reason,
        "dispatch_stopped": version.dispatch_stopped,
        "created_by_name": names.get(version.created_by_user_id),
        "has_pdf": bool(version.pdf_object_key),
        "template_layout_applied": TEMPLATE_LAYOUT_APPLIED,
        "line_send_available": line_settings().configured,
        "deliveries": [_delivery_out(row, links, errors) for row in deliveries],
        "notes": [_note_out(row, names) for row in notes],
        "created_at": version.created_at,
        "updated_at": version.updated_at,
    }


def _project_name(request_conditions: str | None) -> str:
    sections = parse_sections(request_conditions)
    if not sections:
        return ""
    return str(sections.get("project_name") or "")


def _list_item(db: Session, document: OrderRequestDocument, version: OrderRequestVersion, names: dict[str, str]) -> dict:
    deliveries = (
        db.query(OrderRequestDelivery)
        .filter(OrderRequestDelivery.version_id == version.id)
        .all()
    )
    recipient_count = len(deliveries) if deliveries else len(version.draft_worker_ids or [])
    return {
        "document_id": document.id,
        "document_number": document.document_number,
        "kind": document.kind,
        "version_id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "project_name": _project_name(version.request_conditions),
        "site_name": version.site_name,
        "work_date_label": version.work_date_label,
        "created_by_name": names.get(document.created_by_user_id),
        "tracker_name": names.get(version.tracker_user_id or ""),
        "recipient_count": recipient_count,
        "unsent_count": sum(1 for row in deliveries if row.send_status == SEND_UNSENT),
        "unacked_count": sum(1 for row in deliveries if row.ack_status == ACK_UNACKED),
        "acked_count": sum(1 for row in deliveries if row.ack_status != ACK_UNACKED),
        "phone_first": version.phone_first,
        "follow_up_due_on": version.follow_up_due_on,
        "follow_up_due_time": follow_up_time_label(version.follow_up_due_at),
        "dispatch_stopped": version.dispatch_stopped,
        "cancel_reason": version.cancel_reason,
        "has_pdf": bool(version.pdf_object_key),
        "template_layout_applied": TEMPLATE_LAYOUT_APPLIED,
        "line_send_available": line_settings().configured,
        "confirmed_at": version.confirmed_at,
    }


@router.get("")
def list_order_requests(
    kind: str = Query(default="formal"),
    queue: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    service = _service(db)
    try:
        rows, total = service.list_latest(kind=kind, queue=queue, limit=limit, offset=offset)
    except OrderRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    user_ids = {doc.created_by_user_id for doc, _version in rows}
    user_ids.update(version.tracker_user_id for _doc, version in rows if version.tracker_user_id)
    names = _user_map(db, user_ids)
    return {
        "items": [_list_item(db, doc, version, names) for doc, version in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "template_layout_applied": TEMPLATE_LAYOUT_APPLIED,
        "line_send_available": line_settings().configured,
    }


@router.post("")
def create_order_request(
    body: OrderRequestWrite,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        payload = body.model_dump()
        if payload.pop("assign_tracker_self"):
            payload["tracker_user_id"] = current_user.id
        version = _service(db).create_draft(actor=current_user, **payload)
        document = db.get(OrderRequestDocument, version.document_id)
        return document, version

    document, version = _call(db, action)
    db.refresh(version)
    return _version_out(db, document, version)


@router.get("/versions/{version_id}")
def get_order_request_version(
    version_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    service = _service(db)
    try:
        version = service.get_version(version_id)
    except OrderRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.patch("/versions/{version_id}")
def update_order_request_version(
    version_id: str,
    body: OrderRequestUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    fields = body.model_dump(exclude_unset=True)
    if fields.get("assign_tracker_self") is True:
        fields["tracker_user_id"] = current_user.id
    elif fields.get("assign_tracker_self") is False:
        fields["tracker_user_id"] = None
    fields.pop("assign_tracker_self", None)

    def action():
        service = _service(db)
        version = service.get_version(version_id)
        return service.update_draft(
            version,
            kind=fields.get("kind"),
            work_date_label=fields.get("work_date_label"),
            site_name=fields.get("site_name"),
            site_id=fields.get("site_id"),
            site_address=fields.get("site_address"),
            clear_site_id="site_id" in fields and fields.get("site_id") is None,
            request_conditions=fields.get("request_conditions"),
            body=fields.get("body"),
            contact_name=fields.get("contact_name"),
            contact_desk=fields.get("contact_desk"),
            counterparty_note=fields.get("counterparty_note") if "counterparty_note" in fields else None,
            worker_ids=fields.get("worker_ids"),
            phone_first=fields.get("phone_first"),
            phone_contacted_at=fields.get("phone_contacted_at") if "phone_contacted_at" in fields else None,
            phone_note=fields.get("phone_note") if "phone_note" in fields else None,
            tracker_user_id=fields.get("tracker_user_id"),
            clear_tracker="tracker_user_id" in fields and fields.get("tracker_user_id") is None,
            follow_up_due_on=fields.get("follow_up_due_on"),
            follow_up_due_time=fields.get("follow_up_due_time"),
            clear_follow_up="follow_up_due_on" in fields and fields.get("follow_up_due_on") is None,
        )

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.post("/versions/{version_id}/confirm")
def confirm_order_request(
    version_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        return service.confirm(service.get_version(version_id), actor=current_user)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.post("/versions/{version_id}/revise")
def revise_order_request(
    version_id: str,
    body: ReasonBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        return service.revise(service.get_version(version_id), actor=current_user, reason=body.reason)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.post("/versions/{version_id}/cancel")
def cancel_order_request(
    version_id: str,
    body: ReasonBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        return service.cancel(service.get_version(version_id), actor=current_user, reason=body.reason)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.post("/versions/{version_id}/notes")
def add_order_request_note(
    version_id: str,
    body: NoteBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        service.add_note(service.get_version(version_id), actor=current_user, body=body.body)
        return service.get_version(version_id)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.get("/replies")
def list_order_request_replies(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    rows = _service(db).list_sent_replies()
    return {
        "items": [
            {
                "delivery_id": delivery.id,
                "version_id": version.id,
                "document_number": document.document_number,
                "version_no": version.version_no,
                "kind": document.kind,
                "project_name": _project_name(version.request_conditions),
                "site_name": version.site_name,
                "work_date_label": version.work_date_label,
                "worker_name": delivery.worker_name_snapshot,
                "send_status": delivery.send_status,
                "ack_status": delivery.ack_status,
                "decline_reason": delivery.decline_reason,
                "acked_at": delivery.acked_at,
                "follow_up_due_on": version.follow_up_due_on,
                "ack_reminded_at": delivery.ack_reminded_at,
            }
            for delivery, document, version in rows
        ]
    }


@router.get("/line-links")
def list_line_links(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    rows = LineOrderService(db).list_active_links()
    return {
        "line_send_available": line_settings().configured,
        "purpose": PURPOSE_TEXT,
        "unlink_notice": UNLINK_TEXT,
        "items": [
            {
                "worker_id": worker.id,
                "worker_name": worker.name,
                "line_display_name": link.line_display_name,
                "linked_at": link.linked_at,
            }
            for link, worker in rows
        ],
    }


@router.post("/line-links/codes")
def issue_line_link_code(
    body: LineLinkCodeBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        return LineOrderService(db).issue_code(actor=current_user, worker_id=body.worker_id)

    worker, code, expires_at = _call(db, action)
    return {
        "worker_id": worker.id,
        "worker_name": worker.name,
        "code": code,
        "expires_at": expires_at,
        "instruction": LINK_INSTRUCTION,
        "purpose": PURPOSE_TEXT,
        "unlink_notice": UNLINK_TEXT,
    }


@router.post("/line-links/{worker_id}/revoke")
def revoke_line_link(
    worker_id: str,
    body: ReasonBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        return LineOrderService(db).revoke_link(actor=current_user, worker_id=worker_id, reason=body.reason)

    _call(db, action)
    return {"worker_id": worker_id, "status": "revoked"}


@router.post("/deliveries/{delivery_id}/line-send")
def send_order_request_line(
    delivery_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        delivery = LineOrderService(db).send_one(
            actor=current_user,
            delivery=service.get_delivery(delivery_id),
        )
        return service.get_version(delivery.version_id)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.post("/deliveries/{delivery_id}/revoke-view")
def revoke_order_request_view(
    delivery_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)

    def action():
        service = _service(db)
        delivery = service.revoke_view(service.get_delivery(delivery_id), actor=current_user)
        return service.get_version(delivery.version_id)

    version = _call(db, action)
    document = db.get(OrderRequestDocument, version.document_id)
    return _version_out(db, document, version)


@router.get("/versions/{version_id}/pdf")
def download_order_request_pdf(
    version_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure(current_user)
    service = _service(db)
    try:
        version = service.get_version(version_id)
        payload = service.read_pdf(version)
    except OrderRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    filename = order_request_pdf_filename(
        work_date_label=version.work_date_label,
        project_name=project_name_from_document(version.request_conditions, version.body),
    )
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_content_disposition(filename)},
    )
