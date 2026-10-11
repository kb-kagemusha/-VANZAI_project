"""LINE申請の専用審査。入口の無効化では、既に届いた申請の審査を止めない。

承認も却下も、この処理の中で受付の継続を終える。失敗したらこの処理だけを巻き戻す。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.domain.line_registration_apply import (
    assign_worker_values,
    changed_fields,
    empty_worker_values,
    project_worker_values,
    submitted_components,
    values_from_worker,
)
from src.domain.line_registration_locks import lock_link_rows, lock_request_row, lock_worker_row
from src.domain.line_registration_ticket import (
    LineReviewTicketError,
    issue_line_review_ticket,
    verify_line_review_ticket,
)
from src.models.base import generate_ulid
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.line_registration import LineRegistrationContext
from src.models.master import RegistrationRequest, User, Worker, WorkerRegistrationRequestDetail
from src.services.audit import AuditService

CREATE_NEW = "create_new"
FIXED_UPDATE = "fixed_update"


class LineReviewError(Exception):
    def __init__(self, status_code: int, message: str, category: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.category = category
        self.request_id = request_id


class LineRegistrationReviewService:
    def __init__(self, session: Session):
        self.session = session

    def view(self, request_id: str, reviewer: User) -> dict:
        request, context, detail = self._loaded(request_id)
        mode, worker, link = self._target(context)
        before = values_from_worker(worker) if worker is not None else empty_worker_values()
        after = project_worker_values(before, detail)
        pending = request.status == "pending" and request.deleted_at is None and context.is_open
        ticket = None
        if pending:
            ticket = issue_line_review_ticket(
                request_id=request.id,
                reviewer_id=reviewer.id,
                mode=mode,
                worker_id=worker.id if worker is not None else None,
                link_id=link.id if link is not None else None,
                before=before,
            )
        return {
            "request_id": request.id,
            "status": request.status,
            "mode": mode,
            "can_decide": pending,
            "worker_id": worker.id if worker is not None else None,
            "worker_name": worker.name if worker is not None else None,
            "link_id": link.id if link is not None else None,
            "before": before,
            "after": after,
            "components": submitted_components(detail),
            "comparison_ticket": ticket,
        }

    def approve(self, request_id: str, ticket: str, reviewer: User) -> dict:
        self._lock_request(request_id)
        request, context, detail = self._loaded(request_id)
        if request.status != "pending" or request.deleted_at is not None or not context.is_open:
            raise LineReviewError(409, "この申請は、すでに審査が終わっています。", "already_closed", request.id)
        mode, worker, link = self._target(context)
        seen_worker_id = worker.id if worker is not None else None
        seen_link_id = link.id if link is not None else None
        if worker is not None:
            self._lock_worker(worker.id)
        self._lock_links(context.line_user_id, worker.id if worker is not None else None)
        mode, worker, link = self._target(context)
        current_worker_id = worker.id if worker is not None else None
        current_link_id = link.id if link is not None else None
        if current_worker_id != seen_worker_id or current_link_id != seen_link_id:
            raise LineReviewError(
                409,
                "LINEの紐付けが変わったため、承認できません。最新の内容を読み込んでください。",
                "link_changed",
                request.id,
            )
        before = values_from_worker(worker) if worker is not None else empty_worker_values()
        try:
            verify_line_review_ticket(
                ticket,
                request_id=request.id,
                reviewer_id=reviewer.id,
                mode=mode,
                worker_id=worker.id if worker is not None else None,
                link_id=link.id if link is not None else None,
                before=before,
            )
        except LineReviewTicketError as exc:
            raise LineReviewError(409, exc.message, "ticket_mismatch", request.id) from exc
        if worker is not None and (worker.deleted_at is not None or not worker.is_active):
            raise LineReviewError(409, "反映先の稼働者が無効なため、承認できません。", "worker_inactive", request.id)
        after = project_worker_values(before, detail)
        if mode == CREATE_NEW:
            if not after["name"]:
                raise LineReviewError(409, "氏名がないため、新しい稼働者は作れません。", "incomplete", request.id)
            if len(after["name"]) > 100 or len(after["furigana"]) > 200:
                raise LineReviewError(409, "氏名またはふりがなが長すぎるため、承認できません。", "incomplete", request.id)
            worker = Worker(id=generate_ulid(), name=after["name"], is_active=True, tags=[])
            self.session.add(worker)
            self.session.flush()
            assign_worker_values(worker, after)
            link = LineWorkerLink(
                id=generate_ulid(),
                worker_id=worker.id,
                line_user_id=context.line_user_id,
                status=LINK_ACTIVE,
                linked_at=datetime.now(timezone.utc),
            )
            self.session.add(link)
            self.session.flush()
        else:
            assign_worker_values(worker, after)
            self.session.flush()
        now = datetime.now(timezone.utc)
        updated = self.session.execute(
            update(RegistrationRequest)
            .where(
                RegistrationRequest.id == request.id,
                RegistrationRequest.status == "pending",
                RegistrationRequest.deleted_at.is_(None),
            )
            .values(
                status="approved",
                reviewed_at=now,
                reviewed_by=reviewer.id,
                approved_target_type="worker",
                approved_target_id=worker.id,
            )
        )
        if updated.rowcount != 1:
            raise LineReviewError(409, "この申請は、すでに審査が終わっています。", "already_closed", request.id)
        context.is_open = False
        AuditService(self.session).log(
            "line_registration_approved",
            target_type="registration_request",
            target_id=request.id,
            actor=reviewer.username,
            actor_role=reviewer.role,
            before_value=before,
            after_value=after,
            extra_metadata={"changed": changed_fields(before, after), "worker_id": worker.id, "mode": mode},
        )
        self.session.flush()
        return {"request_id": request.id, "status": "approved", "worker_id": worker.id}

    def reject(self, request_id: str, reviewer: User, reason: str) -> dict:
        cleaned = reason.strip()
        if not cleaned:
            raise LineReviewError(422, "却下理由を入力してください。", "reason", request_id)
        self._lock_request(request_id)
        request, context, _detail = self._loaded(request_id)
        if request.status != "pending" or request.deleted_at is not None or not context.is_open:
            raise LineReviewError(409, "この申請は、すでに審査が終わっています。", "already_closed", request.id)
        now = datetime.now(timezone.utc)
        updated = self.session.execute(
            update(RegistrationRequest)
            .where(
                RegistrationRequest.id == request.id,
                RegistrationRequest.status == "pending",
                RegistrationRequest.deleted_at.is_(None),
            )
            .values(status="rejected", reviewed_at=now, reviewed_by=reviewer.id, notes=cleaned)
        )
        if updated.rowcount != 1:
            raise LineReviewError(409, "この申請は、すでに審査が終わっています。", "already_closed", request.id)
        context.is_open = False
        AuditService(self.session).log(
            "line_registration_rejected",
            target_type="registration_request",
            target_id=request.id,
            actor=reviewer.username,
            actor_role=reviewer.role,
            reason="rejected",
        )
        self.session.flush()
        return {"request_id": request.id, "status": "rejected"}

    def _loaded(self, request_id: str):
        request = self.session.get(RegistrationRequest, request_id)
        context = self.session.scalar(
            select(LineRegistrationContext).where(LineRegistrationContext.request_id == request_id)
        )
        if request is None or request.deleted_at is not None or context is None:
            raise LineReviewError(404, "LINEからの申請ではありません。", "not_line", request_id if context else None)
        detail = self.session.scalar(
            select(WorkerRegistrationRequestDetail).where(WorkerRegistrationRequestDetail.request_id == request.id)
        )
        if detail is None:
            raise LineReviewError(409, "申請の内容を確認できません。", "missing_detail", request.id)
        return request, context, detail

    def _target(self, context: LineRegistrationContext):
        link = self.session.scalar(
            select(LineWorkerLink).where(
                LineWorkerLink.line_user_id == context.line_user_id,
                LineWorkerLink.status == LINK_ACTIVE,
            )
        )
        if link is None:
            return CREATE_NEW, None, None
        worker = self.session.get(Worker, link.worker_id)
        if worker is None:
            raise LineReviewError(409, "紐付いている稼働者を確認できません。", "link_changed", context.request_id)
        return FIXED_UPDATE, worker, link

    def _lock_request(self, request_id: str) -> None:
        lock_request_row(self.session, request_id)

    def _lock_worker(self, worker_id: str) -> None:
        lock_worker_row(self.session, worker_id)

    def _lock_links(self, line_user_id: str, worker_id: str | None) -> None:
        lock_link_rows(self.session, line_user_id=line_user_id, worker_id=worker_id)
