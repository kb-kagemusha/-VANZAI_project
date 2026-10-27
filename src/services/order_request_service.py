"""発注依頼書の下書き、確定、改訂、取消。

確定時にスナップショットと送付行を同一トランザクションで作る。
PDFの書き込みに失敗した場合、呼び出し側がロールバックすれば送付行は残らない。
LINEへの push はこのサービスでは行わない。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from src.models.base import generate_ulid
from src.models.enums import AuditAction
from src.models.master import Client, ClientStaff, Site, User, Worker
from src.models.order_request import (
    ACK_ACKED,
    ACK_DECLINE_PENDING,
    ACK_DECLINED,
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
from src.domain.order_schedule import expand_work_days, normalize_schedule, normalize_work_period, schedule_text, work_dates, work_period_label
from src.services import worker_schedule as ws
from src.services.order_request_pdf import PDF_LAYOUT_ID, TEMPLATE_LAYOUT_APPLIED, render_order_request_pdf

JST = ZoneInfo("Asia/Tokyo")
DEFAULT_DUE_TIME = "21:00"
# OR-YYYYMMDD-001A。連番は日付ごと 001〜999、変更の文字は A〜Z。
# document_number は String(40) で足りる。Z の次を AA にはしない。
_NEW_DOCUMENT_NUMBER = re.compile(r"^OR-(\d{8})-(\d{3})([A-Z])$")
_MAX_DAILY_SEQUENCE = 999
_NUMBER_LOCK_KEY = 90261008
_SEQUENCE_EXHAUSTED = "この日の発注依頼書は999件までです。これ以上は作成できません"
_LETTER_EXHAUSTED = "この依頼書の変更はZまでです。これ以上の変更文書は作れません"


def follow_up_moment(due_on: date, due_time: str | None) -> datetime:
    text = (due_time or DEFAULT_DUE_TIME).strip()[:5]
    try:
        parsed = datetime.strptime(text, "%H:%M").time()
    except ValueError as exc:
        raise OrderRequestError(400, "期限の案内の時刻は 21:00 のように入れてください") from exc
    return datetime.combine(due_on, parsed, tzinfo=JST)


def follow_up_time_label(moment: datetime | None) -> str:
    if moment is None:
        return DEFAULT_DUE_TIME
    if moment.tzinfo is None:
        return moment.strftime("%H:%M")
    return moment.astimezone(JST).strftime("%H:%M")


# 確定に「日付・期間ごとの入力」を必須にする。試験で旧形式の確定を検証するときだけ False にする。
REQUIRE_SCHEDULE_ON_CONFIRM = True
SCHEDULE_REQUIRED = "稼働時間を「日付・期間ごとの入力」に切り替えてから確定してください。文章の入力のままでは、受諾しても稼働予定（公式LINEの予定・起床報告）が作られません"


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


def _parse_new_document_number(number: str | None) -> tuple[str, int, str] | None:
    if not number:
        return None
    match = _NEW_DOCUMENT_NUMBER.fullmatch(number)
    if match is None:
        return None
    return match.group(1), int(match.group(2)), match.group(3)


def _is_document_number_conflict(exc: IntegrityError) -> bool:
    return "document_number" in str(getattr(exc, "orig", exc)).lower()


def _drop_pending(session: Session, obj: object) -> None:
    if object_session(obj) is session:
        session.expunge(obj)


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
        follow_up_due_time: str | None = DEFAULT_DUE_TIME,
        based_on_version_id: str | None = None,
        internal_source: dict | None = None,
        internal_source_set: bool = False,
        recipient_absences: dict | None = None,
        allow_partial_accept: bool = False,
        requires_operator_confirmation: bool = False,
    ) -> OrderRequestVersion:
        self._validate_kind(kind)
        worker_ids = self._normalize_worker_ids(worker_ids)
        self._ensure_workers_exist(worker_ids)
        if tracker_user_id:
            self._ensure_user(tracker_user_id)
        if site_id:
            self._ensure_site(site_id)
        source = self.get_version(based_on_version_id) if based_on_version_id else None
        source_number = self._document(source).document_number if source is not None else None
        document, version = self._insert_numbered_draft(
            actor=actor,
            kind=kind,
            source=source,
            source_number=source_number,
            worker_ids=worker_ids,
            work_date_label=work_date_label,
            site_name=site_name,
            site_id=site_id,
            site_address=site_address,
            request_conditions=request_conditions,
            body=body,
            contact_name=contact_name,
            contact_desk=contact_desk,
            counterparty_note=counterparty_note,
            phone_first=phone_first,
            phone_contacted_at=phone_contacted_at,
            phone_note=phone_note,
            tracker_user_id=tracker_user_id,
            follow_up_due_on=follow_up_due_on,
            follow_up_due_time=follow_up_due_time,
        )
        version.draft_recipient_absences = self._normalize_absences(
            recipient_absences, version.draft_worker_ids or [], version.request_conditions
        )
        version.allow_partial_accept = bool(allow_partial_accept)
        version.requires_operator_confirmation = bool(requires_operator_confirmation)
        if source is not None:
            self._copy_internal_source(source, version)
        if internal_source_set:
            self._set_internal_source(version, internal_source, actor=actor)
        self.session.flush()
        if source is not None:
            source_document = self._document(source)
            self.audit.log(
                AuditAction.ORDER_REQUEST_REVISED,
                target_type="order_request_version",
                target_id=version.id,
                actor=_user_label(actor),
                actor_role=actor.role,
                reason="変更を作成",
                after_value={
                    "document_number": document.document_number,
                    "version_no": version.version_no,
                    "based_on_document_number": source_document.document_number,
                    "based_on_version_id": source.id,
                    "based_on_version_no": source.version_no,
                    "kind": document.kind,
                },
            )
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
        site_address_set: bool = False,
        clear_site_id: bool = False,
        internal_source: dict | None = None,
        internal_source_set: bool = False,
        request_conditions: str | None = None,
        actor: User | None = None,
        body: str | None = None,
        contact_name: str | None = None,
        contact_desk: str | None = None,
        counterparty_note: str | None = None,
        worker_ids: list[str] | None = None,
        phone_first: bool | None = None,
        phone_contacted_at: datetime | None = None,
        phone_note: str | None = None,
        phone_note_set: bool = False,
        tracker_user_id: str | None = None,
        clear_tracker: bool = False,
        follow_up_due_on: date | None = None,
        follow_up_due_time: str | None = None,
        clear_follow_up: bool = False,
        recipient_absences: dict | None = None,
        recipient_absences_set: bool = False,
        allow_partial_accept: bool | None = None,
        requires_operator_confirmation: bool | None = None,
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
        content_change = any(item is not None for item in content_keys) or clear_site_id or site_id is not None or site_address_set or internal_source_set or recipient_absences_set or allow_partial_accept is not None or requires_operator_confirmation is not None
        if content_change and version.status != STATUS_DRAFT:
            raise OrderRequestError(409, "確定済みの本文と送付先は変更できません。改訂で新しい版を作ってください")

        if kind is not None and kind != document.kind:
            self._validate_kind(kind)
            if self._has_confirmed(document.id):
                raise OrderRequestError(409, "確定後にテスト／正式の区分は変更できません")
            document.kind = kind

        if version.status != STATUS_DRAFT:
            if (
                tracker_user_id is not None
                or clear_tracker
                or follow_up_due_on is not None
                or follow_up_due_time is not None
                or clear_follow_up
            ):
                self._apply_follow_up(
                    version,
                    tracker_user_id=version.tracker_user_id if tracker_user_id is None else tracker_user_id,
                    clear_tracker=clear_tracker,
                    follow_up_due_on=version.follow_up_due_on if follow_up_due_on is None else follow_up_due_on,
                    follow_up_due_time=follow_up_due_time,
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
            site_address=version.site_address if site_address is None and not site_address_set else site_address,
            request_conditions=version.request_conditions if request_conditions is None else request_conditions,
            body=version.body if body is None else body,
            contact_name=version.contact_name if contact_name is None else contact_name,
            contact_desk=version.contact_desk if contact_desk is None else contact_desk,
            counterparty_note=version.counterparty_note if counterparty_note is None else counterparty_note,
            worker_ids=list(ids or []),
            phone_first=version.phone_first if phone_first is None else phone_first,
            phone_contacted_at=version.phone_contacted_at if phone_contacted_at is None else phone_contacted_at,
            phone_note=version.phone_note if not phone_note_set else phone_note,
            tracker_user_id=None if clear_tracker else (
                version.tracker_user_id if tracker_user_id is None else tracker_user_id
            ),
            follow_up_due_on=None if clear_follow_up else (
                version.follow_up_due_on if follow_up_due_on is None else follow_up_due_on
            ),
            follow_up_due_time=follow_up_due_time,
        )
        if internal_source_set:
            self._set_internal_source(version, internal_source, actor=actor)
        absences = recipient_absences if recipient_absences_set else version.draft_recipient_absences
        version.draft_recipient_absences = self._normalize_absences(
            absences, version.draft_worker_ids or [], version.request_conditions
        )
        if requires_operator_confirmation is not None and version.revision_of_version_id:
            previous = self.session.get(OrderRequestVersion, version.revision_of_version_id)
            if previous and bool(previous.requires_operator_confirmation) != bool(requires_operator_confirmation):
                raise OrderRequestError(409, "改訂では参加確定方式を変更できません。新しい依頼書として作成してください")
        if requires_operator_confirmation is not None:
            version.requires_operator_confirmation = bool(requires_operator_confirmation)
        if allow_partial_accept is not None:
            version.allow_partial_accept = bool(allow_partial_accept)
        self.session.flush()
        return version

    def _set_internal_source(self, version, source, *, actor=None):
        before = {"client_id": version.internal_client_id, "client_staff_id": version.internal_client_staff_id}
        previous_snapshot = version.internal_source_snapshot
        if source and before == {"client_id": source["client_id"], "client_staff_id": source.get("client_staff_id")} and previous_snapshot:
            return  # Keep the reviewed source snapshot, including archived contacts, on unrelated edits.
        if source is None:
            version.internal_client_id = None
            version.internal_client_staff_id = None
            version.internal_source_snapshot = None
            self._audit_internal_source(version, before, previous_snapshot, actor)
            return
        client = self.session.get(Client, source["client_id"])
        if client is None or client.deleted_at is not None:
            raise OrderRequestError(400, "発注元のクライアントを選び直してください")
        staff_id = source.get("client_staff_id")
        staff = self.session.get(ClientStaff, staff_id) if staff_id else None
        if staff_id and (staff is None or staff.deleted_at is not None or not staff.is_active or staff.client_id != client.id):
            raise OrderRequestError(400, "選択した発注元に属する有効な担当者を選んでください")
        version.internal_client_id = client.id
        version.internal_client_staff_id = staff_id
        version.internal_source_snapshot = {
            "client_id": client.id, "client_staff_id": staff_id,
            "client_name": client.name, "client_phone": client.phone,
            "staff_name": staff.name if staff else None, "staff_phone": staff.phone if staff else None,
        }
        self._audit_internal_source(version, before, previous_snapshot, actor)

    def _audit_internal_source(self, version, before, previous_snapshot, actor):
        if previous_snapshot == version.internal_source_snapshot:
            return
        self.audit.log("order_request_internal_source_updated", target_type="order_request_version", target_id=version.id, actor=_user_label(actor) if actor else None, actor_role=actor.role if actor else None, before_value=before, after_value={"client_id": version.internal_client_id, "client_staff_id": version.internal_client_staff_id})

    @staticmethod
    def _copy_internal_source(source, target):
        target.internal_client_id = source.internal_client_id
        target.internal_client_staff_id = source.internal_client_staff_id
        target.internal_source_snapshot = dict(source.internal_source_snapshot) if source.internal_source_snapshot else None

    def confirm(self, version: OrderRequestVersion, *, actor: User) -> OrderRequestVersion:
        series_id = ws.ensure_series(self.session, version)
        series = ws.lock_series(self.session, series_id)
        version = self.session.get(OrderRequestVersion, version.id)
        if version.status != STATUS_DRAFT:
            raise OrderRequestError(409, "下書きだけを確定できます")
        if version.dispatch_stopped:
            raise OrderRequestError(409, "送付を止めた版は確定できません")

        worker_ids = self._normalize_worker_ids(list(version.draft_worker_ids or []))
        if not worker_ids:
            raise OrderRequestError(400, "送付先を1人以上選んでください")
        if len(worker_ids) > MAX_RECIPIENTS:
            raise OrderRequestError(400, f"1回の送付先は{MAX_RECIPIENTS}人までです")

        try:
            sections = parse_sections(version.request_conditions)
            if sections and "schedule" in sections:
                normalize_schedule(sections["schedule"], complete=True)
            if sections and "work_period" in sections:
                normalize_work_period(sections["work_period"], sections.get("schedule"), complete=True)
        except ValueError as exc:
            raise OrderRequestError(400, str(exc)) from None
        if REQUIRE_SCHEDULE_ON_CONFIRM and (not sections or "schedule" not in sections):
            # 文章だけの稼働時間では稼働予定・起床の監視に載らない（DEC-063・DEC-069。2026-10-22 ユーザー判断で確定を止める）。
            # 古い依頼書を基にした新規作成・変更の作成・下書きの保存は止めない。
            raise OrderRequestError(400, SCHEDULE_REQUIRED)
        required = (
            (
                ("案件名", sections.get("project_name") if sections else ""),
                ("稼働日", version.work_date_label),
                ("稼働場所", version.site_name),
                ("運営側の連絡担当者", version.contact_name or version.contact_desk),
            )
            if sections is not None
            else (
                ("日付", version.work_date_label),
                ("現場", version.site_name),
                ("依頼条件", version.request_conditions),
                ("運営側の連絡担当者", version.contact_name or version.contact_desk),
            )
        )
        missing = [name for name, value in required if not _clean(value)]
        if sections and sections.get("incentive_enabled") is True and not sections.get("incentive", "").strip():
            missing.append("インセンティブの詳細")
        self._check_offered_days(version, worker_ids)
        if version.follow_up_due_on is None:
            missing.append("期限の案内")
        if missing:
            raise OrderRequestError(400, "確定前に入力してください: " + "、".join(missing))
        if version.follow_up_due_at is None and version.follow_up_due_on is not None:
            version.follow_up_due_at = follow_up_moment(version.follow_up_due_on, DEFAULT_DUE_TIME)

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
            created_at=version.created_at,
            requires_operator_confirmation=bool(version.requires_operator_confirmation),
            **self._notice_pdf_kwargs(version),
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

        schedule = sections.get("schedule") if sections else None
        work_days = expand_work_days(schedule) if schedule else []
        absences = self._normalize_absences(version.draft_recipient_absences, worker_ids, version.request_conditions) or {}
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
                    offered_dates=ws.offered_dates_for(work_days, absences.get(worker_id)),
                )
            )
        self.session.flush()
        from src.services.order_staffing import ensure_round
        ensure_round(self.session, version)
        self._apply_confirmation_to_series(series, version, set(worker_ids), actor)
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
        series_id = ws.ensure_series(self.session, version)
        draft = OrderRequestVersion(
            id=generate_ulid(),
            document_id=document.id,
            series_id=series_id,
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
            draft_recipient_absences=dict(version.draft_recipient_absences or {}) or None,
            allow_partial_accept=bool(version.allow_partial_accept),
            requires_operator_confirmation=bool(version.requires_operator_confirmation),
            phone_first=False,
            tracker_user_id=version.tracker_user_id,
            follow_up_due_on=version.follow_up_due_on,
            follow_up_due_at=version.follow_up_due_at,
            created_by_user_id=actor.id,
        )
        self._copy_internal_source(version, draft)
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
        series_id = ws.ensure_series(self.session, version)
        from src.services.staffing_replacement import lock_family
        lock_family(self.session,series_id)
        series = ws.lock_series(self.session, series_id)
        version = self.session.get(OrderRequestVersion, version.id)
        if version.status == STATUS_CANCELLED:
            raise OrderRequestError(409, "すでに取消済みです")
        ends_series = series.answerable_version_id == version.id
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
        if ends_series:
            # 回答受付版の取消は発注の中止（L-34）。旧版へは戻さない。
            self._set_answerable(series, None, actor)
            for worker_id in ws.series_workers(self.session, series.id):
                ws.set_application(self.session, series_id=series.id, worker_id=worker_id, delivery=None, ended_reason=ws.END_DOCUMENT_ENDED, actor=actor.id)
            ws.rebuild_series(self.session, series.id, actor=actor.id)
            from src.models.staffing_replacement import StaffingRecruitment, StaffingVacancy
            own=self.session.query(StaffingRecruitment).filter_by(series_id=series.id).one_or_none()
            if own:
                vacancy=self.session.get(StaffingVacancy,own.vacancy_id)
                root=ws.lock_series(self.session,vacancy.root_series_id)
                if root.answerable_version_id:
                    vacancy.status="open"; vacancy.revision+=1
                    self.audit.log("staffing_recruitment_cancelled",target_type="staffing_vacancy",target_id=vacancy.id,actor=actor.username,actor_role=actor.role,reason=reason)
            children=self.session.query(StaffingRecruitment).join(StaffingVacancy,StaffingRecruitment.vacancy_id == StaffingVacancy.id).filter(StaffingVacancy.root_series_id == series.id).all()
            for campaign in children:
                child_series=ws.lock_series(self.session,campaign.series_id)
                if child_series.answerable_version_id:
                    child=self.session.get(OrderRequestVersion,child_series.answerable_version_id)
                    if child.status != STATUS_CANCELLED:
                        self.cancel(child,actor=actor,reason="元の案件の取消："+reason)
        return version

    def withdraw_acceptance(self, document: OrderRequestDocument, worker_id: str, *, actor: User, reason: str) -> dict:
        """今後の参加を終了する（受諾後の辞退の記録。DEC-065、統合計画 D-05）。

        記録した時点で勤務が始まっている日（日本時間）は参加日として残し、まだ始まっていない日だけ外した状態を追記する。
        """
        reason = _clean(reason)
        if not reason:
            raise OrderRequestError(400, "辞退の理由を入力してください")
        first = (
            self.session.query(OrderRequestVersion)
            .filter(OrderRequestVersion.document_id == document.id)
            .order_by(OrderRequestVersion.version_no)
            .first()
        )
        if first is None:
            raise OrderRequestError(404, "発注依頼書が見つかりません")
        series = ws.lock_series(self.session, ws.ensure_series(self.session, first))
        application = ws.get_application(self.session, series.id, worker_id)
        if application is None or not application.applied_delivery_id:
            raise OrderRequestError(409, "この稼働者には受諾済みの参加がありません")
        applied = self.session.get(OrderRequestDelivery, application.applied_delivery_id)
        state = ws.current_state(self.session, applied)
        applied_version = self.session.get(OrderRequestVersion, applied.version_id)
        kept, removed = ws.split_started(applied_version, list(state.dates) if state is not None else [])
        recorded = False
        if state is None or removed:
            ws.append_state(
                self.session, applied, dates=kept, source=ws.SOURCE_OPS_RECORDED_DECLINE,
                actor=actor.id, reason=reason[:500],
            )
            recorded = True
        pending = ws.delivery_in_version(self.session, series.answerable_version_id, worker_id)
        if pending is not None and pending.id != applied.id and pending.ack_status in (ACK_UNACKED, ACK_DECLINE_PENDING):
            pending.ack_status = ACK_DECLINED
            pending.decline_reason = ("運営記録：" + reason)[:500]
            pending.acked_at = _now()
        self.audit.log(
            "order_request_acceptance_withdrawn",
            target_type="order_request_delivery",
            target_id=applied.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            reason=reason,
            after_value={"document_number": document.document_number, "worker_id": worker_id, "recorded": recorded, "kept_dates": kept, "removed_dates": removed},
        )
        self.session.flush()
        ws.rebuild(self.session, series.id, worker_id, actor=actor.id)
        return {"delivery_id": applied.id, "recorded": recorded, "kept_dates": kept, "removed_dates": removed}

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

    def render_draft_preview(self, version: OrderRequestVersion) -> bytes:
        if version.status != STATUS_DRAFT:
            raise OrderRequestError(409, "下書きだけを画面で確認できます")
        document = self._document(version)
        worker_ids = [worker_id for worker_id in (version.draft_worker_ids or []) if worker_id]
        names: list[str] = []
        if worker_ids:
            workers = self._load_workers(worker_ids)
            names = [workers[worker_id].name for worker_id in worker_ids]
        return render_order_request_pdf(
            document_number=document.document_number,
            version_no=version.version_no,
            kind=document.kind,
            work_date_label=version.work_date_label,
            site_name=version.site_name,
            site_address=version.site_address,
            request_conditions=version.request_conditions or "",
            body=version.body or "",
            contact_name=version.contact_name,
            contact_desk=version.contact_desk,
            counterparty_note=version.counterparty_note,
            worker_names=names,
            created_at=version.created_at,
            requires_operator_confirmation=bool(version.requires_operator_confirmation),
            **self._notice_pdf_kwargs(version),
        )

    def read_pdf(self, version: OrderRequestVersion) -> bytes:
        if not version.pdf_object_key:
            raise OrderRequestError(404, "確定済みのPDFがありません")
        if not self.storage.exists(version.pdf_object_key):
            raise OrderRequestError(404, "PDFファイルが見つかりません")
        payload = self.storage.read_bytes(version.pdf_object_key)
        if b"IPAexGothic" in payload and PDF_LAYOUT_ID.encode("ascii") in payload:
            return payload
        payload = self._render_stored_pdf(version)
        self.storage.save_bytes(version.pdf_object_key, payload)
        return payload

    def _render_stored_pdf(self, version: OrderRequestVersion) -> bytes:
        document = self._document(version)
        snapshot = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        names = snapshot.get("worker_names")
        if not isinstance(names, list) or not names:
            names = [row.worker_name_snapshot for row in self._deliveries(version.id)]
        return render_order_request_pdf(
            document_number=document.document_number,
            version_no=version.version_no,
            kind=document.kind,
            work_date_label=version.work_date_label,
            site_name=version.site_name,
            site_address=version.site_address,
            request_conditions=version.request_conditions or "",
            body=version.body or "",
            contact_name=version.contact_name,
            contact_desk=version.contact_desk,
            counterparty_note=version.counterparty_note,
            worker_names=[str(name) for name in names],
            created_at=version.created_at,
            requires_operator_confirmation=bool(version.requires_operator_confirmation),
            **self._notice_pdf_kwargs(version),
        )

    def _notice_pdf_kwargs(self, version: OrderRequestVersion) -> dict:
        if version.status == STATUS_CANCELLED:
            return {"notice": "cancel"}
        if not version.revision_of_version_id:
            return {"notice": "new"}
        previous = self.session.get(OrderRequestVersion, version.revision_of_version_id)
        if previous is None:
            return {"notice": "change"}
        return {
            "notice": "change",
            "previous_work_date_label": previous.work_date_label or "",
            "previous_site_name": previous.site_name or "",
            "previous_site_address": previous.site_address,
            "previous_request_conditions": previous.request_conditions or "",
            "previous_body": previous.body or "",
            "previous_contact_name": previous.contact_name or "",
            "previous_contact_desk": previous.contact_desk or "",
            "previous_counterparty_note": previous.counterparty_note,
        }

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
        query = query.filter(OrderRequestDocument.deleted_at.is_(None))
        rows = query.order_by(OrderRequestVersion.created_at.desc()).all()
        filtered = [row for row in rows if self._matches_queue(row[1], queue)]
        return filtered[offset : offset + limit], len(filtered)

    def list_hidden(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[OrderRequestDocument, OrderRequestVersion]], int]:
        latest_no = (
            self.session.query(
                OrderRequestVersion.document_id.label("document_id"),
                func.max(OrderRequestVersion.version_no).label("version_no"),
            )
            .group_by(OrderRequestVersion.document_id)
            .subquery()
        )
        rows = (
            self.session.query(OrderRequestDocument, OrderRequestVersion)
            .join(OrderRequestVersion, OrderRequestVersion.document_id == OrderRequestDocument.id)
            .join(
                latest_no,
                (OrderRequestVersion.document_id == latest_no.c.document_id)
                & (OrderRequestVersion.version_no == latest_no.c.version_no),
            )
            .filter(OrderRequestDocument.deleted_at.is_not(None))
            .order_by(OrderRequestDocument.deleted_at.desc())
            .all()
        )
        return rows[offset : offset + limit], len(rows)

    def hide_document(self, document: OrderRequestDocument, *, actor: User) -> OrderRequestDocument:
        if document.deleted_at is not None:
            return document
        first = self.session.query(OrderRequestVersion).filter(OrderRequestVersion.document_id == document.id).first()
        if first is not None:
            ws.lock_series(self.session, ws.ensure_series(self.session, first))
            from src.models.staffing_replacement import StaffingRecruitment, StaffingVacancy
            from src.models.line_daily import OrderRequestSeries
            own=self.session.query(StaffingRecruitment).filter_by(series_id=first.series_id).first()
            children=self.session.query(StaffingRecruitment).join(StaffingVacancy,StaffingRecruitment.vacancy_id == StaffingVacancy.id).filter(StaffingVacancy.root_series_id == first.series_id).all()
            related=([own] if own else [])+children
            if any(self.session.get(OrderRequestSeries,c.series_id).answerable_version_id for c in related):
                raise OrderRequestError(409,"代替募集が関連しています。元の案件または募集を取り消してから一覧から外してください")
        if ws.active_entries_on_or_after(self.session, document.id, ws.today_jst()):
            raise OrderRequestError(409, "今後の稼働予定がある依頼書は一覧から外せません。依頼をやめる場合は取消してください")
        document.deleted_at = _now()
        document.deleted_by_user_id = actor.id
        self.audit.log(
            AuditAction.ORDER_REQUEST_HIDDEN,
            target_type="order_request_document",
            target_id=document.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            reason="一覧から外した",
            after_value={"document_number": document.document_number},
        )
        self.session.flush()
        return document

    def get_document(self, document_id: str) -> OrderRequestDocument:
        document = self.session.get(OrderRequestDocument, document_id)
        if document is None:
            raise OrderRequestError(404, "発注依頼書が見つかりません")
        return document

    def list_sent_replies(self, *, limit: int = 200) -> list[tuple[OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion]]:
        return (
            self.session.query(OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion)
            .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
            .join(OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id)
            .filter(
                OrderRequestDelivery.send_status != SEND_UNSENT,
                OrderRequestDocument.deleted_at.is_(None),
            )
            .order_by(OrderRequestDelivery.updated_at.desc())
            .limit(limit)
            .all()
        )

    def list_sent_reply_groups(self, *, kind: str, limit: int, offset: int):
        """文書単位でページ化してから全送付先を取得。同一人物は最新の送付版を返す。"""
        if kind not in (KIND_FORMAL, KIND_TEST, "all"):
            raise OrderRequestError(400, "kind は formal、test、all のいずれかです")
        query = (self.session.query(OrderRequestDocument.id.label("document_id"),
                    func.max(OrderRequestDelivery.updated_at).label("updated_at"))
            .join(OrderRequestVersion, OrderRequestVersion.document_id == OrderRequestDocument.id)
            .join(OrderRequestDelivery, OrderRequestDelivery.version_id == OrderRequestVersion.id)
            .filter(OrderRequestDocument.deleted_at.is_(None), OrderRequestDelivery.send_status != SEND_UNSENT))
        if kind != "all":
            query = query.filter(OrderRequestDocument.kind == kind)
        query = query.group_by(OrderRequestDocument.id)
        total = query.count()
        document_ids = [row.document_id for row in query.order_by(func.max(OrderRequestDelivery.updated_at).desc(), OrderRequestDocument.id.desc()).offset(offset).limit(limit)]
        groups = {identifier: {} for identifier in document_ids}
        if document_ids:
            rows = (self.session.query(OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion)
                .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
                .join(OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id)
                .filter(OrderRequestDocument.id.in_(document_ids), OrderRequestDelivery.send_status != SEND_UNSENT)
                .order_by(OrderRequestVersion.version_no.desc(), OrderRequestDelivery.updated_at.desc(), OrderRequestDelivery.id.desc()).all())
            for delivery, document, version in rows:
                groups[document.id].setdefault(delivery.worker_id, (delivery, document, version))
        return [list(group.values()) for group in groups.values()], total

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
        due_at = version.follow_up_due_at
        if due_at is not None:
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=JST)
            if due_at > _now():
                return False
        elif version.follow_up_due_on is None or version.follow_up_due_on >= _today():
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

    def _set_answerable(self, series, version_id: str | None, actor: User) -> None:
        before = series.answerable_version_id
        if before == version_id:
            return
        series.answerable_version_id = version_id
        self.session.flush()
        self.audit.log(
            "order_request_answerable_changed",
            target_type="order_request_series",
            target_id=series.id,
            actor=_user_label(actor),
            actor_role=actor.role,
            before_value={"answerable_version_id": before},
            after_value={"answerable_version_id": version_id},
        )

    def _apply_confirmation_to_series(self, series, version: OrderRequestVersion, recipients: set[str], actor: User) -> None:
        """確定した版を回答受付版にし、送付先から外れた人の適用送付行と旧いPDFリンクを止め、予定を作り直す。"""
        self._set_answerable(series, version.id, actor)
        for worker_id in ws.series_workers(self.session, series.id):
            if worker_id in recipients:
                continue
            application = ws.get_application(self.session, series.id, worker_id)
            if application is not None and application.applied_delivery_id:
                ws.set_application(self.session, series_id=series.id, worker_id=worker_id, delivery=None, ended_reason=ws.END_REMOVED, actor=actor.id)
            ws.revoke_tokens_for_removed(self.session, series.id, worker_id)
        ws.rebuild_series(self.session, series.id, actor=actor.id)

    def _normalize_absences(self, value: dict | None, worker_ids: list[str], request_conditions: str | None) -> dict | None:
        """送付先ごとの個人不参加日を正規化する（DEC-065）。送付先でない人の分は取り除く。

        日程がある依頼書では、不参加日は実勤務日（共通の休業日を除く）から選ぶ。"""
        if not value:
            return None
        if not isinstance(value, dict):
            raise OrderRequestError(400, "個人の不参加日の形式が正しくありません")
        allowed = set(worker_ids)
        try:
            sections = parse_sections(request_conditions or "")
        except ValueError:
            sections = None
        schedule = sections.get("schedule") if sections else None
        days = set(work_dates(schedule)) if schedule else None
        result: dict[str, list[str]] = {}
        for worker_id, dates in value.items():
            if worker_id not in allowed:
                continue
            if not isinstance(dates, list):
                raise OrderRequestError(400, "個人の不参加日の形式が正しくありません")
            cleaned: set[str] = set()
            for day in dates:
                try:
                    valid = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
                except ValueError:
                    valid = False
                if not valid:
                    raise OrderRequestError(400, "個人の不参加日の日付の形式が正しくありません")
                if days is None:
                    raise OrderRequestError(400, "個人の不参加日は、稼働日の詳細を入力した依頼書で設定してください")
                if day not in days:
                    raise OrderRequestError(400, "個人の不参加日は、休業日を除いた稼働日から選んでください")
                cleaned.add(day)
            if cleaned:
                result[worker_id] = sorted(cleaned)
        return result or None

    def _check_offered_days(self, version: OrderRequestVersion, worker_ids: list[str]) -> None:
        """確定前に、送付先ごとの提示日（実勤務日−個人不参加日）が1日以上あることを確かめる。"""
        absences = self._normalize_absences(version.draft_recipient_absences, worker_ids, version.request_conditions) or {}
        if not absences:
            return
        sections = parse_sections(version.request_conditions or "")
        days = set(work_dates(sections.get("schedule"))) if sections and sections.get("schedule") else set()
        empty = [worker_id for worker_id in worker_ids if days and not (days - set(absences.get(worker_id, [])))]
        if empty:
            names = self._load_workers(empty)
            label = "、".join(names[worker_id].name for worker_id in empty)
            raise OrderRequestError(400, f"{label}さんの稼働日が0日です。送付先から外すか、不参加日を見直してください")

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
        try:
            sections = parse_sections(fields["request_conditions"] or "")
            if sections and "work_period" in sections:
                version.work_date_label = work_period_label(sections["work_period"])
            elif sections and "schedule" in sections:
                version.work_date_label, _, _ = schedule_text(sections["schedule"])
            request_conditions, body = apply_template_fields(
                fields["request_conditions"] or "", fields["body"] or "",
                work_date_label=version.work_date_label, site_name=version.site_name, site_address=version.site_address,
            )
        except ValueError as exc:
            raise OrderRequestError(400, str(exc)) from None
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
        due_on = fields["follow_up_due_on"]
        if due_on is None:
            raise OrderRequestError(400, "期限の案内の日付を入れてください")
        version.follow_up_due_on = due_on
        version.follow_up_due_at = follow_up_moment(due_on, fields.get("follow_up_due_time"))

    def _apply_follow_up(
        self,
        version: OrderRequestVersion,
        *,
        tracker_user_id: str | None,
        clear_tracker: bool,
        follow_up_due_on: date | None,
        follow_up_due_time: str | None,
        clear_follow_up: bool,
    ) -> None:
        if clear_tracker:
            version.tracker_user_id = None
        elif tracker_user_id:
            self._ensure_user(tracker_user_id)
            version.tracker_user_id = tracker_user_id
        if clear_follow_up:
            raise OrderRequestError(400, "期限の案内の日付を入れてください")
        if follow_up_due_on is not None:
            version.follow_up_due_on = follow_up_due_on
            version.follow_up_due_at = follow_up_moment(
                follow_up_due_on,
                follow_up_due_time or follow_up_time_label(version.follow_up_due_at),
            )

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

    def _insert_numbered_draft(
        self,
        *,
        actor: User,
        kind: str,
        source: OrderRequestVersion | None,
        source_number: str | None,
        worker_ids: list[str],
        work_date_label: str,
        site_name: str,
        site_id: str | None,
        site_address: str | None,
        request_conditions: str,
        body: str,
        contact_name: str,
        contact_desk: str,
        counterparty_note: str | None,
        phone_first: bool,
        phone_contacted_at: datetime | None,
        phone_note: str | None,
        tracker_user_id: str | None,
        follow_up_due_on: date | None,
        follow_up_due_time: str | None,
    ) -> tuple[OrderRequestDocument, OrderRequestVersion]:
        self._lock_document_numbers()
        for _attempt in range(5):
            document = OrderRequestDocument(
                id=generate_ulid(),
                document_number=self._propose_document_number(source_number),
                kind=kind,
                created_by_user_id=actor.id,
            )
            version = OrderRequestVersion(
                id=generate_ulid(),
                document_id=document.id,
                version_no=1,
                status=STATUS_DRAFT,
                revision_of_version_id=source.id if source else None,
                revision_reason="変更を作成" if source else None,
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
                follow_up_due_time=follow_up_due_time,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(document)
                    self.session.flush()
                    # 系列：「変更を作成」なら元の版の系列、新規なら最初の依頼書を系列の起点にする（詳細設計§4.4）
                    version.series_id = ws.ensure_series(self.session, source) if source is not None else ws.new_series(self.session, document.id)
                    self.session.add(version)
                    self.session.flush()
                return document, version
            except IntegrityError as exc:
                if not _is_document_number_conflict(exc):
                    raise
                _drop_pending(self.session, document)
                _drop_pending(self.session, version)
        raise OrderRequestError(500, "文書番号を発行できませんでした")

    def _lock_document_numbers(self) -> None:
        """採番からコミットまでを直列化する。PostgreSQL ではトランザクション終了まで待つ。"""
        bind = self.session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _NUMBER_LOCK_KEY},
        )

    def _propose_document_number(self, source_number: str | None) -> str:
        parsed = _parse_new_document_number(source_number)
        if parsed is not None:
            day, sequence, _letter = parsed
            return self._next_family_number(day, sequence)
        return self._next_original_number()

    def _next_original_number(self) -> str:
        day = datetime.now(JST).strftime("%Y%m%d")
        max_sequence = 0
        for number in self._numbers_starting(f"OR-{day}-"):
            parsed = _parse_new_document_number(number)
            if parsed is None or parsed[0] != day:
                continue
            max_sequence = max(max_sequence, parsed[1])
        if max_sequence >= _MAX_DAILY_SEQUENCE:
            raise OrderRequestError(409, _SEQUENCE_EXHAUSTED)
        return f"OR-{day}-{max_sequence + 1:03d}A"

    def _next_family_number(self, day: str, sequence: int) -> str:
        stem = f"OR-{day}-{sequence:03d}"
        letters: list[str] = []
        for number in self._numbers_starting(stem):
            parsed = _parse_new_document_number(number)
            if parsed is None or parsed[0] != day or parsed[1] != sequence:
                continue
            letters.append(parsed[2])
        if not letters:
            raise OrderRequestError(409, "変更元の文書番号が見つかりません")
        last = max(letters)
        if last == "Z":
            raise OrderRequestError(409, _LETTER_EXHAUSTED)
        return f"{stem}{chr(ord(last) + 1)}"

    def _numbers_starting(self, prefix: str) -> list[str]:
        rows = (
            self.session.query(OrderRequestDocument.document_number)
            .filter(OrderRequestDocument.document_number.startswith(prefix))
            .all()
        )
        return [row[0] for row in rows]
