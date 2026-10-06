"""発注依頼書の下書き、確定、改訂、取消。

確定時にスナップショットと送付行を同一トランザクションで作る。
PDFの書き込みに失敗した場合、呼び出し側がロールバックすれば送付行は残らない。
LINEへの push はこのサービスでは行わない。
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.enums import AuditAction
from src.models.master import Site, User, Worker
from src.models.order_request import (
    ACK_ACKED,
    ACK_UNACKED,
    KIND_FORMAL,
    KIND_TEST,
    MAX_RECIPIENTS,
    SEND_ACCEPTED,
    SEND_UNKNOWN,
    SEND_UNSENT,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_DRAFT,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestNote,
    OrderRequestVersion,
)
from src.services.audit import AuditService
from src.services.document_storage import DocumentStorage
from src.services.order_request_format import apply_template_fields, parse_sections
from src.services.order_request_pdf import TEMPLATE_LAYOUT_APPLIED, render_order_request_pdf

JST = ZoneInfo("Asia/Tokyo")


class OrderRequestError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(JST).date()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _case_text(value: str | None) -> str:
    return _clean(value).replace("~", "～")


def _user_label(user: User | None) -> str | None:
    if user is None:
        return None
    return user.display_name or user.username


class OrderRequestService:
    def __init__(self, session: Session, storage: DocumentStorage | None = None):
        self.session = session
        self.storage = storage or DocumentStorage()
        self.audit = AuditService(session)

    def create_draft(
        self,
        *,
        actor: User,
        kind: str,
        work_date_label: str,
        site_name: str,
        site_id: str | None,
        site_address: str | None,
        request_conditions: str,
        body: str,
        contact_name: str,
        contact_desk: str,
        counterparty_note: str | None,
        worker_ids: list[str],
        phone_first: bool,
        phone_contacted_at: datetime | None,
        phone_note: str | None,
        tracker_user_id: str | None,
        follow_up_due_on: date | None,
    ) -> OrderRequestVersion:
        self._validate_kind(kind)
        worker_ids = self._normalize_worker_ids(worker_ids)
        self._ensure_workers_exist(worker_ids)
        if tracker_user_id:
            self._ensure_user(tracker_user_id)
        if site_id:
            self._ensure_site(site_id)

        document = OrderRequestDocument(
            id=generate_ulid(),
            document_number=self._new_document_number(),
            kind=kind,
            created_by_user_id=actor.id,
        )
        version = OrderRequestVersion(
            id=generate_ulid(),
            document_id=document.id,
            version_no=1,
            status=STATUS_DRAFT,
            created_by_user_id=actor.id,
            draft_worker_ids=worker_ids,
        )
        self._apply_draft_fields(
            version,
            work_date_label=work_date_label,
            site_name=site_name,
            site_id=site_id,
            site_address=site_address,
            request_conditions=request_conditions,
            body=body,
            contact_name=contact_name,
            contact_desk=contact_desk,
            counterparty_note=counterparty_note,
            worker_ids=worker_ids,
            phone_first=phone_first,
            phone_contacted_at=phone_contacted_at,
            phone_note=phone_note,
            tracker_user_id=tracker_user_id,
            follow_up_due_on=follow_up_due_on,
        )
        self.session.add(document)
        self.session.add(version)
        self.session.flush()
        return version

    def update_draft(
        self,
        version: OrderRequestVersion,
        *,
        kind: str | None = None,
        work_date_label: str | None = None,
        site_name: str | None = None,
        site_id: str | None = None,
        site_address: str | None = None,
        clear_site_id: bool = False,
        request_conditions: str | None = None,
        body: str | None = None,
        contact_name: str | None = None,
        contact_desk: str | None = None,
        counterparty_note: str | None = None,
        worker_ids: list[str] | None = None,
        phone_first: bool | None = None,
        phone_contacted_at: datetime | None = None,
        phone_note: str | None = None,
        tracker_user_id: str | None = None,
        clear_tracker: bool = False,
        follow_up_due_on: date | None = None,
        clear_follow_up: bool = False,
    ) -> OrderRequestVersion:
        if version.status == STATUS_CANCELLED:
            raise OrderRequestError(409, "取消済みの版は編集できません")

        document = self._document(version)
        content_keys = [
            work_date_label,
            site_name,
            request_conditions,
            body,
            contact_name,
            contact_desk,
            counterparty_note,
            worker_ids,
            site_address,
        ]
        content_change = any(item is not None for item in content_keys) or clear_site_id or site_id is not None
        if content_change and version.status != STATUS_DRAFT:
            raise OrderRequestError(409, "確定済みの本文と送付先は変更できません。改訂で新しい版を作ってください")

        if kind is not None and kind != document.kind:
            self._validate_kind(kind)
            if self._has_confirmed(document.id):
                raise OrderRequestError(409, "確定後にテスト／正式の区分は変更できません")
            document.kind = kind

        if version.status != STATUS_DRAFT:
            if tracker_user_id is not None or clear_tracker or follow_up_due_on is not None or clear_follow_up:
                self._apply_follow_up(
                    version,
                    tracker_user_id=version.tracker_user_id if tracker_user_id is None else tracker_user_id,
                    clear_tracker=clear_tracker,
                    follow_up_due_on=version.follow_up_due_on if follow_up_due_on is None else follow_up_due_on,
                    clear_follow_up=clear_follow_up,
                )
            self.session.flush()
            return version

        ids = version.draft_worker_ids if worker_ids is None else self._normalize_worker_ids(worker_ids)
        if worker_ids is not None:
            self._ensure_workers_exist(ids)
        next_site_id = None if clear_site_id else (site_id if site_id is not None else version.site_id)
        if next_site_id:
            self._ensure_site(next_site_id)
        self._apply_draft_fields(
            version,
            work_date_label=version.work_date_label if work_date_label is None else work_date_label,
            site_name=version.site_name if site_name is None else site_name,
            site_id=next_site_id,
            site_address=version.site_address if site_address is None else site_address,
            request_conditions=version.request_conditions if request_conditions is None else request_conditions,
            body=version.body if body is None else body,
            contact_name=version.contact_name if contact_name is None else contact_name,
            contact_desk=version.contact_desk if contact_desk is None else contact_desk,
            counterparty_note=version.counterparty_note if counterparty_note is None else counterparty_note,
            worker_ids=list(ids or []),
            phone_first=version.phone_first if phone_first is None else phone_first,
            phone_contacted_at=version.phone_contacted_at if phone_contacted_at is None else phone_contacted_at,
            phone_note=version.phone_note if phone_note is None else phone_note,
            tracker_user_id=None if clear_tracker else (
                version.tracker_user_id if tracker_user_id is None else tracker_user_id
            ),
            follow_up_due_on=None if clear_follow_up else (
                version.follow_up_due_on if follow_up_due_on is None else follow_up_due_on
            ),
        )
        self.session.flush()
        return version

    def confirm(self, version: OrderRequestVersion, *, actor: User) -> OrderRequestVersion:
        if version.status != STATUS_DRAFT:
            raise OrderRequestError(409, "下書きだけを確定できます")
        if version.dispatch_stopped:
            raise OrderRequestError(409, "送付を止めた版は確定できません")

        worker_ids = self._normalize_worker_ids(list(version.draft_worker_ids or []))
        if not worker_ids:
            raise OrderRequestError(400, "送付先を1人以上選んでください")
        if len(worker_ids) > MAX_RECIPIENTS:
            raise OrderRequestError(400, f"1回の送付先は{MAX_RECIPIENTS}人までです")

        sections = parse_sections(version.request_conditions)
        required = (
            (
                ("案件名", sections.get("project_name") if sections else ""),
                ("稼働日", version.work_date_label),
                ("稼働場所", version.site_name),
                ("担当者", version.contact_name),
                ("業務用窓口", version.contact_desk),
            )
            if sections is not None
            else (
                ("日付", version.work_date_label),
                ("現場", version.site_name),
                ("依頼条件", version.request_conditions),
                ("担当者", version.contact_name),
                ("業務用窓口", version.contact_desk),
            )
        )
        missing = [name for name, value in required if not _clean(value)]
        if missing:
            raise OrderRequestError(400, "確定前に入力してください: " + "、".join(missing))

        workers = self._load_workers(worker_ids)
        site_name = _clean(version.site_name)
        site_address = version.site_address
        if version.site_id:
            site = self._ensure_site(version.site_id)
            site_name = site.name
            site_address = site.address
            version.site_name = site_name
            version.site_address = site_address

        document = self._document(version)
        names = [workers[worker_id].name for worker_id in worker_ids]
        snapshot = {
            "work_date_label": _clean(version.work_date_label),
            "site_id": version.site_id,
            "site_name": site_name,
            "site_address": site_address,
            "request_conditions": version.request_conditions,
            "body": version.body,
            "contact_name": _clean(version.contact_name),
            "contact_desk": _clean(version.contact_desk),
            "counterparty_note": version.counterparty_note,
            "worker_ids": worker_ids,
            "worker_names": names,
            "template_layout_applied": TEMPLATE_LAYOUT_APPLIED,
        }
        pdf_bytes = render_order_request_pdf(
            document_number=document.document_number,
            version_no=version.version_no,
            kind=document.kind,
            work_date_label=snapshot["work_date_label"],
            site_name=site_name,
            site_address=site_address,
            request_conditions=version.request_conditions,
            body=version.body or "",
            contact_name=snapshot["contact_name"],
            contact_desk=snapshot["contact_desk"],
            counterparty_note=version.counterparty_note,
            worker_names=names,
        )
        object_key = (
            f"order-requests/{document.document_number}/v{version.version_no}.pdf"
        )
        version.snapshot_json = snapshot
        version.pdf_object_key = object_key
        version.status = STATUS_CONFIRMED
        version.confirmed_at = _now()
        version.confirmed_by_user_id = actor.id
        version.work_date_label = snapshot["work_date_label"]
        version.contact_name = snapshot["contact_name"]
        version.contact_desk = snapshot["contact_desk"]

        for worker_id in worker_ids:
            self.session.add(
                OrderRequestDelivery(
                    id=generate_ulid(),
                    version_id=version.id,
                    worker_id=worker_id,
                    worker_name_snapshot=workers[worker_id].name,
                    send_status=SEND_UNSENT,
                    ack_status=ACK_UNACKED,
                    view_revoked=False,
                )
            )
        self.session.flush()
        try:
            self.storage.save_bytes(object_key, pdf_bytes)
        except Exception:
            self.session.rollback()
            raise OrderRequestError(500, "PDFの保存に失敗したため、確定と送付行は残していません") from None

        self.audit.log(
            AuditAction.ORDER_REQUEST_CONFIRMED,
            target_type="order_request_version",
            target_id=version.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            after_value={
                "document_number": document.document_number,
                "version_no": version.version_no,
                "kind": document.kind,
                "recipient_count": len(worker_ids),
                "pdf_object_key": object_key,
            },
        )
        self.session.flush()
        return version

    def revise(self, version: OrderRequestVersion, *, actor: User, reason: str) -> OrderRequestVersion:
        reason = _clean(reason)
        if not reason:
            raise OrderRequestError(400, "改訂理由を入力してください")
        if version.status == STATUS_DRAFT:
            raise OrderRequestError(409, "下書きは改訂せず、その版を編集してください")
        document = self._document(version)
        next_no = (
            self.session.query(func.max(OrderRequestVersion.version_no))
            .filter(OrderRequestVersion.document_id == document.id)
            .scalar()
            or 0
        ) + 1
        source_ids = [row.worker_id for row in self._deliveries(version.id)]
        if not source_ids:
            source_ids = list(version.draft_worker_ids or [])
        draft = OrderRequestVersion(
            id=generate_ulid(),
            document_id=document.id,
            version_no=next_no,
            status=STATUS_DRAFT,
            revision_of_version_id=version.id,
            revision_reason=reason,
            work_date_label=version.work_date_label,
            site_id=version.site_id,
            site_name=version.site_name,
            site_address=version.site_address,
            request_conditions=version.request_conditions,
            body=version.body,
            contact_name=version.contact_name,
            contact_desk=version.contact_desk,
            counterparty_note=version.counterparty_note,
            draft_worker_ids=source_ids,
            phone_first=False,
            tracker_user_id=version.tracker_user_id,
            follow_up_due_on=version.follow_up_due_on,
            created_by_user_id=actor.id,
        )
        self.session.add(draft)
        self.session.flush()
        self.audit.log(
            AuditAction.ORDER_REQUEST_REVISED,
            target_type="order_request_version",
            target_id=draft.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            reason=reason,
            after_value={
                "document_number": document.document_number,
                "version_no": draft.version_no,
                "revision_of_version_id": version.id,
                "kind": document.kind,
            },
        )
        return draft

    def cancel(self, version: OrderRequestVersion, *, actor: User, reason: str) -> OrderRequestVersion:
        reason = _clean(reason)
        if not reason:
            raise OrderRequestError(400, "取消理由を入力してください")
        if version.status == STATUS_CANCELLED:
            raise OrderRequestError(409, "すでに取消済みです")
        version.status = STATUS_CANCELLED
        version.cancel_reason = reason
        version.cancelled_at = _now()
        version.cancelled_by_user_id = actor.id
        version.dispatch_stopped = True
        document = self._document(version)
        self.audit.log(
            AuditAction.ORDER_REQUEST_CANCELLED,
            target_type="order_request_version",
            target_id=version.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            reason=reason,
            after_value={
                "document_number": document.document_number,
                "version_no": version.version_no,
                "dispatch_stopped": True,
            },
        )
        self.session.flush()
        return version

    def add_note(self, version: OrderRequestVersion, *, actor: User, body: str) -> OrderRequestNote:
        text = _clean(body)
        if not text:
            raise OrderRequestError(400, "メモを入力してください")
        note = OrderRequestNote(
            id=generate_ulid(),
            version_id=version.id,
            author_user_id=actor.id,
            body=text,
            created_at=_now(),
        )
        self.session.add(note)
        self.session.flush()
        return note

    def revoke_view(self, delivery: OrderRequestDelivery, *, actor: User) -> OrderRequestDelivery:
        if delivery.view_revoked:
            return delivery
        delivery.view_revoked = True
        self.audit.log(
            AuditAction.ORDER_REQUEST_VIEW_REVOKED,
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            after_value={"version_id": delivery.version_id, "worker_id": delivery.worker_id},
        )
        self.session.flush()
        return delivery

    def read_pdf(self, version: OrderRequestVersion) -> bytes:
        if not version.pdf_object_key:
            raise OrderRequestError(404, "確定済みのPDFがありません")
        if not self.storage.exists(version.pdf_object_key):
            raise OrderRequestError(404, "PDFファイルが見つかりません")
        return self.storage.read_bytes(version.pdf_object_key)

    def get_version(self, version_id: str) -> OrderRequestVersion:
        version = self.session.get(OrderRequestVersion, version_id)
        if version is None:
            raise OrderRequestError(404, "発注依頼書が見つかりません")
        return version

    def get_delivery(self, delivery_id: str) -> OrderRequestDelivery:
        delivery = self.session.get(OrderRequestDelivery, delivery_id)
        if delivery is None:
            raise OrderRequestError(404, "送付行が見つかりません")
        return delivery

    def list_latest(
        self,
        *,
        kind: str,
        queue: str,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[OrderRequestDocument, OrderRequestVersion]], int]:
        if kind not in (KIND_FORMAL, KIND_TEST, "all"):
            raise OrderRequestError(400, "kind は formal、test、all のいずれかです")
        if queue not in ("all", "unsent", "unknown", "unacked", "overdue"):
            raise OrderRequestError(400, "queue が不正です")

        latest_no = (
            self.session.query(
                OrderRequestVersion.document_id.label("document_id"),
                func.max(OrderRequestVersion.version_no).label("version_no"),
            )
            .group_by(OrderRequestVersion.document_id)
            .subquery()
        )
        query = (
            self.session.query(OrderRequestDocument, OrderRequestVersion)
            .join(OrderRequestVersion, OrderRequestVersion.document_id == OrderRequestDocument.id)
            .join(
                latest_no,
                (OrderRequestVersion.document_id == latest_no.c.document_id)
                & (OrderRequestVersion.version_no == latest_no.c.version_no),
            )
        )
        if kind != "all":
            query = query.filter(OrderRequestDocument.kind == kind)
        rows = query.order_by(OrderRequestVersion.created_at.desc()).all()
        filtered = [row for row in rows if self._matches_queue(row[1], queue)]
        return filtered[offset : offset + limit], len(filtered)

    def _matches_queue(self, version: OrderRequestVersion, queue: str) -> bool:
        if queue == "all":
            return True
        deliveries = self._deliveries(version.id)
        if queue == "unsent":
            if version.status == STATUS_CANCELLED or version.dispatch_stopped:
                return False
            if version.status == STATUS_DRAFT:
                return True
            return any(row.send_status == SEND_UNSENT for row in deliveries)
        if queue == "unknown":
            return any(row.send_status == SEND_UNKNOWN for row in deliveries)
        if queue == "unacked":
            if version.status != STATUS_CONFIRMED:
                return False
            return any(
                row.send_status == SEND_ACCEPTED and row.ack_status == ACK_UNACKED
                for row in deliveries
            )
        due = version.follow_up_due_on
        if due is None or due >= _today():
            return False
        if version.phone_first and version.status == STATUS_DRAFT:
            return True
        if version.status == STATUS_CONFIRMED and not version.dispatch_stopped:
            return any(row.ack_status == ACK_UNACKED for row in deliveries)
        return False

    def _deliveries(self, version_id: str) -> list[OrderRequestDelivery]:
        return (
            self.session.query(OrderRequestDelivery)
            .filter(OrderRequestDelivery.version_id == version_id)
            .all()
        )

    def _apply_draft_fields(self, version: OrderRequestVersion, **fields) -> None:
        worker_ids = fields.pop("worker_ids")
        if len(worker_ids) > MAX_RECIPIENTS:
            raise OrderRequestError(400, f"1回の送付先は{MAX_RECIPIENTS}人までです")
        tracker_user_id = fields.pop("tracker_user_id")
        if tracker_user_id:
            self._ensure_user(tracker_user_id)
        version.work_date_label = _case_text(fields["work_date_label"])
        version.site_name = _case_text(fields["site_name"])
        version.site_id = fields["site_id"]
        version.site_address = fields["site_address"]
        request_conditions, body = apply_template_fields(
            fields["request_conditions"] or "",
            fields["body"] or "",
            work_date_label=version.work_date_label,
            site_name=version.site_name,
        )
        version.request_conditions = request_conditions
        version.body = body
        version.contact_name = _case_text(fields["contact_name"])
        version.contact_desk = _case_text(fields["contact_desk"])
        note = fields["counterparty_note"]
        version.counterparty_note = None if note is None else _case_text(note)
        version.draft_worker_ids = worker_ids
        version.phone_first = bool(fields["phone_first"])
        version.phone_contacted_at = fields["phone_contacted_at"]
        phone_note = fields["phone_note"]
        version.phone_note = None if phone_note is None else _case_text(phone_note)
        version.tracker_user_id = tracker_user_id
        version.follow_up_due_on = fields["follow_up_due_on"]

    def _apply_follow_up(
        self,
        version: OrderRequestVersion,
        *,
        tracker_user_id: str | None,
        clear_tracker: bool,
        follow_up_due_on: date | None,
        clear_follow_up: bool,
    ) -> None:
        if clear_tracker:
            version.tracker_user_id = None
        elif tracker_user_id:
            self._ensure_user(tracker_user_id)
            version.tracker_user_id = tracker_user_id
        if clear_follow_up:
            version.follow_up_due_on = None
        elif follow_up_due_on is not None:
            version.follow_up_due_on = follow_up_due_on

    def _document(self, version: OrderRequestVersion) -> OrderRequestDocument:
        document = version.document or self.session.get(OrderRequestDocument, version.document_id)
        if document is None:
            raise OrderRequestError(404, "発注依頼書が見つかりません")
        return document

    def _has_confirmed(self, document_id: str) -> bool:
        return (
            self.session.query(OrderRequestVersion.id)
            .filter(
                OrderRequestVersion.document_id == document_id,
                OrderRequestVersion.status.in_((STATUS_CONFIRMED, STATUS_CANCELLED)),
                OrderRequestVersion.pdf_object_key.isnot(None),
            )
            .first()
            is not None
        )

    def _validate_kind(self, kind: str) -> None:
        if kind not in (KIND_FORMAL, KIND_TEST):
            raise OrderRequestError(400, "kind は formal または test です")

    def _normalize_worker_ids(self, worker_ids: list[str]) -> list[str]:
        cleaned = [_clean(worker_id) for worker_id in worker_ids if _clean(worker_id)]
        if len(cleaned) != len(set(cleaned)):
            raise OrderRequestError(400, "送付先が重複しています")
        return cleaned

    def _ensure_workers_exist(self, worker_ids: list[str]) -> None:
        if not worker_ids:
            return
        self._load_workers(worker_ids)

    def _load_workers(self, worker_ids: list[str]) -> dict[str, Worker]:
        rows = (
            self.session.query(Worker)
            .filter(Worker.id.in_(worker_ids), Worker.deleted_at.is_(None), Worker.is_active.is_(True))
            .all()
        )
        found = {row.id: row for row in rows}
        missing = [worker_id for worker_id in worker_ids if worker_id not in found]
        if missing:
            raise OrderRequestError(400, "稼働していない、または存在しない送付先があります")
        return found

    def _ensure_user(self, user_id: str) -> User:
        user = self.session.get(User, user_id)
        if user is None or user.deleted_at is not None or not user.is_active:
            raise OrderRequestError(400, "追跡担当者が見つかりません")
        return user

    def _ensure_site(self, site_id: str) -> Site:
        site = self.session.get(Site, site_id)
        if site is None or site.deleted_at is not None:
            raise OrderRequestError(400, "現場が見つかりません")
        return site

    def _new_document_number(self) -> str:
        day = datetime.now(JST).strftime("%Y%m%d")
        for _ in range(5):
            number = f"OR-{day}-{secrets.token_hex(3).upper()}"
            exists = (
                self.session.query(OrderRequestDocument.id)
                .filter(OrderRequestDocument.document_number == number)
                .first()
            )
            if exists is None:
                return number
        raise OrderRequestError(500, "文書番号を発行できませんでした")
