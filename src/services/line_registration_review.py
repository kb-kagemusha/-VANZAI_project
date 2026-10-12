"""LINE申請の専用審査。入口の無効化では、既に届いた申請の審査を止めない。

承認も却下も、この処理の中で受付の継続を終える。失敗したらこの処理だけを巻き戻す。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
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
    read_line_review_claims,
    verify_line_review_ticket,
)
from src.models.base import generate_ulid
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.line_registration import LineRegistrationContext
from src.models.master import RegistrationRequest, User, Worker, WorkerRegistrationRequestDetail
from src.services.audit import AuditService

CREATE_NEW = "create_new"
FIXED_UPDATE = "fixed_update"
CHOOSE = "choose"
EXISTING = "existing"
FIXED_REFUSED = "申請時の紐付けが解除または差し替えられたため、承認できません。比較票を取り直しても、反映先は変わりません。"
CHOOSE_MESSAGE = "新規の稼働者として作るか、既存の稼働者を選んでください。氏名や電話が一致しても、自動では統合しません。"
CODE_WAIT = "この稼働者は、一次性コードで紐付いてから承認できます。承認では紐付けを作りません。紐付けができたら、もう一度この稼働者を選んでください。"
INCOMPLETE = "新しい稼働者に必要な項目が揃っていません。"
LINK_EXISTS = "すでに有効な紐付けがあるため、新しい稼働者は作れません。"


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
        if context.worker_id:
            worker, link = self._fixed_rows(context)
            before = values_from_worker(worker) if worker is not None else empty_worker_values()
            ready = self._fixed_link_ready(context, worker, link)
            return self._payload(
                request,
                context,
                detail,
                reviewer,
                mode=FIXED_UPDATE,
                worker=worker,
                link=link,
                before=before,
                after=project_worker_values(before, detail),
                can_decide=ready,
                blocked_reason=None if ready else FIXED_REFUSED,
                candidates=[],
                issue_ticket=worker is not None,
            )
        return self._payload(
            request,
            context,
            detail,
            reviewer,
            mode=CHOOSE,
            worker=None,
            link=None,
            before=empty_worker_values(),
            after=empty_worker_values(),
            can_decide=False,
            blocked_reason=CHOOSE_MESSAGE,
            candidates=self._candidates(detail, None),
            issue_ticket=False,
        )

    def candidates(self, request_id: str, query: str | None) -> list[dict]:
        _request, context, detail = self._loaded(request_id)
        if context.worker_id:
            return []
        return self._candidates(detail, query)

    def choose(self, request_id: str, reviewer: User, decision: str, worker_id: str | None) -> dict:
        request, context, detail = self._loaded(request_id)
        if context.worker_id:
            raise LineReviewError(409, FIXED_REFUSED, "fixed_target", request.id)
        if decision == CREATE_NEW:
            return self._choose_new(request, context, detail, reviewer)
        if decision == EXISTING:
            if not worker_id:
                raise LineReviewError(422, "既存の稼働者を選んでください。", "incomplete", request.id)
            return self._choose_existing(request, context, detail, reviewer, worker_id)
        raise LineReviewError(422, "新規作成か、既存の稼働者かを選んでください。", "incomplete", request.id)

    def approve(self, request_id: str, ticket: str, reviewer: User) -> dict:
        try:
            claims = read_line_review_claims(ticket, request_id=request_id, reviewer_id=reviewer.id)
        except LineReviewTicketError as exc:
            raise LineReviewError(409, exc.message, "ticket_mismatch", request_id) from exc
        self._lock_request(request_id)
        request, context, detail = self._loaded(request_id)
        self._ensure_open(request, context)
        mode = str(claims.get("mode") or "")
        if context.worker_id:
            worker, before = self._approve_fixed(request, context, reviewer, ticket, claims)
            mode = FIXED_UPDATE
        elif mode == CREATE_NEW:
            worker, before = self._approve_new(request, context, reviewer, ticket)
        elif mode == EXISTING:
            worker, before = self._approve_existing(request, context, reviewer, ticket, claims)
        else:
            raise LineReviewError(409, "表示中の内容が変わりました。最新の内容を読み込んでから、もう一度審査してください。", "ticket_mismatch", request.id)
        request, context, detail = self._loaded(request.id)
        after = project_worker_values(before, detail)
        if mode != CREATE_NEW:
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

    def _choose_new(self, request, context, detail, reviewer: User) -> dict:
        before = empty_worker_values()
        after = project_worker_values(before, detail)
        active = self._active_link(context.line_user_id)
        problem = LINK_EXISTS if active is not None else self._new_worker_problem(detail)
        return self._payload(
            request,
            context,
            detail,
            reviewer,
            mode=CREATE_NEW,
            worker=None,
            link=None,
            before=before,
            after=after,
            can_decide=problem is None,
            blocked_reason=problem,
            candidates=self._candidates(detail, None),
            issue_ticket=problem is None,
        )

    def _choose_existing(self, request, context, detail, reviewer: User, worker_id: str) -> dict:
        worker = self.session.get(Worker, worker_id)
        if worker is None or worker.deleted_at is not None or not worker.is_active:
            raise LineReviewError(404, "選択した稼働者を確認できません。", "not_line", request.id)
        link = self._active_link_for_worker(context.line_user_id, worker.id)
        before = values_from_worker(worker)
        ready = link is not None
        return self._payload(
            request,
            context,
            detail,
            reviewer,
            mode=EXISTING,
            worker=worker,
            link=link,
            before=before,
            after=project_worker_values(before, detail),
            can_decide=ready,
            blocked_reason=None if ready else CODE_WAIT,
            candidates=self._candidates(detail, None),
            issue_ticket=ready,
        )

    def _approve_fixed(self, request, context, reviewer: User, ticket: str, claims: dict):
        if (
            claims.get("mode") != FIXED_UPDATE
            or claims.get("worker_id") != context.worker_id
            or claims.get("link_id") != (context.line_worker_link_id or "")
        ):
            raise LineReviewError(409, FIXED_REFUSED, "fixed_target", request.id)
        self._lock_worker(context.worker_id)
        self._lock_links(context.line_user_id, context.worker_id)
        self.session.expire_all()
        request, context, _detail = self._loaded(request.id)
        self._ensure_open(request, context)
        worker, link = self._fixed_rows(context)
        if not self._fixed_link_ready(context, worker, link):
            raise LineReviewError(409, FIXED_REFUSED, "fixed_target", request.id)
        before = values_from_worker(worker)
        self._check_ticket(
            ticket,
            request=request,
            reviewer=reviewer,
            mode=FIXED_UPDATE,
            worker_id=context.worker_id,
            link_id=context.line_worker_link_id,
            before=before,
        )
        return worker, before

    def _approve_new(self, request, context, reviewer: User, ticket: str):
        self._lock_links(context.line_user_id, None)
        self.session.expire_all()
        request, context, detail = self._loaded(request.id)
        self._ensure_open(request, context)
        if context.worker_id or self._active_link(context.line_user_id) is not None:
            raise LineReviewError(409, LINK_EXISTS, "link_exists", request.id)
        problem = self._new_worker_problem(detail)
        if problem:
            raise LineReviewError(409, problem, "incomplete", request.id)
        before = empty_worker_values()
        self._check_ticket(
            ticket,
            request=request,
            reviewer=reviewer,
            mode=CREATE_NEW,
            worker_id=None,
            link_id=None,
            before=before,
        )
        after = project_worker_values(before, detail)
        worker = Worker(id=generate_ulid(), name=after["name"], is_active=True, tags=[])
        self.session.add(worker)
        self.session.flush()
        assign_worker_values(worker, after)
        self.session.add(
            LineWorkerLink(
                id=generate_ulid(),
                worker_id=worker.id,
                line_user_id=context.line_user_id,
                status=LINK_ACTIVE,
                linked_at=datetime.now(timezone.utc),
            )
        )
        self.session.flush()
        return worker, before

    def _approve_existing(self, request, context, reviewer: User, ticket: str, claims: dict):
        worker_id = str(claims.get("worker_id") or "")
        link_id = str(claims.get("link_id") or "")
        if not worker_id or not link_id:
            raise LineReviewError(409, CODE_WAIT, "code_required", request.id)
        self._lock_worker(worker_id)
        self._lock_links(context.line_user_id, worker_id)
        self.session.expire_all()
        request, context, _detail = self._loaded(request.id)
        self._ensure_open(request, context)
        worker = self.session.get(Worker, worker_id)
        link = self.session.get(LineWorkerLink, link_id)
        if worker is None or link is None or not self._same_active_link(context.line_user_id, worker, link):
            raise LineReviewError(409, CODE_WAIT, "code_required", request.id)
        before = values_from_worker(worker)
        self._check_ticket(
            ticket,
            request=request,
            reviewer=reviewer,
            mode=EXISTING,
            worker_id=worker.id,
            link_id=link.id,
            before=before,
        )
        return worker, before

    def _payload(
        self,
        request,
        context,
        detail,
        reviewer: User,
        *,
        mode: str,
        worker,
        link,
        before: dict[str, str],
        after: dict[str, str],
        can_decide: bool,
        blocked_reason: str | None,
        candidates: list[dict],
        issue_ticket: bool,
    ) -> dict:
        pending = request.status == "pending" and request.deleted_at is None and context.is_open
        ticket = None
        if pending and issue_ticket:
            ticket = issue_line_review_ticket(
                request_id=request.id,
                reviewer_id=reviewer.id,
                mode=mode,
                worker_id=worker.id if worker is not None else (context.worker_id if mode == FIXED_UPDATE else None),
                link_id=(
                    context.line_worker_link_id
                    if mode == FIXED_UPDATE
                    else (link.id if link is not None else None)
                ),
                before=before,
            )
        shown_worker_id = context.worker_id if mode == FIXED_UPDATE else (worker.id if worker is not None else None)
        shown_link_id = context.line_worker_link_id if mode == FIXED_UPDATE else (link.id if link is not None else None)
        return {
            "request_id": request.id,
            "status": request.status,
            "mode": mode,
            "can_decide": bool(pending and can_decide and ticket),
            "blocked_reason": None if pending and can_decide and ticket else blocked_reason,
            "worker_id": shown_worker_id,
            "worker_name": worker.name if worker is not None else None,
            "link_id": shown_link_id,
            "before": before,
            "after": after,
            "components": submitted_components(detail),
            "comparison_ticket": ticket,
            "candidates": candidates,
        }

    def _fixed_rows(self, context: LineRegistrationContext):
        worker = self.session.get(Worker, context.worker_id) if context.worker_id else None
        link = self.session.get(LineWorkerLink, context.line_worker_link_id) if context.line_worker_link_id else None
        return worker, link

    def _fixed_link_ready(self, context: LineRegistrationContext, worker, link) -> bool:
        return bool(
            context.worker_id
            and context.line_worker_link_id
            and worker is not None
            and link is not None
            and link.id == context.line_worker_link_id
            and self._same_active_link(context.line_user_id, worker, link)
            and link.worker_id == context.worker_id
        )

    def _same_active_link(self, line_user_id: str, worker, link) -> bool:
        return bool(
            worker is not None
            and worker.deleted_at is None
            and worker.is_active
            and link is not None
            and link.worker_id == worker.id
            and link.line_user_id == line_user_id
            and link.status == LINK_ACTIVE
        )

    def _active_link(self, line_user_id: str):
        return self.session.scalar(
            select(LineWorkerLink).where(
                LineWorkerLink.line_user_id == line_user_id,
                LineWorkerLink.status == LINK_ACTIVE,
            )
        )

    def _active_link_for_worker(self, line_user_id: str, worker_id: str):
        return self.session.scalar(
            select(LineWorkerLink).where(
                LineWorkerLink.line_user_id == line_user_id,
                LineWorkerLink.worker_id == worker_id,
                LineWorkerLink.status == LINK_ACTIVE,
            )
        )

    def _candidates(self, detail, query: str | None) -> list[dict]:
        text_query = (query or "").strip()
        stmt = select(Worker).where(Worker.deleted_at.is_(None), Worker.is_active.is_(True))
        if text_query:
            pattern = f"%{text_query}%"
            rows = self.session.scalars(
                stmt.where(
                    or_(
                        Worker.name.ilike(pattern),
                        Worker.furigana.ilike(pattern),
                        Worker.phone.ilike(pattern),
                    )
                )
                .order_by(Worker.name)
                .limit(20)
            ).all()
            return [self._candidate(row, ["検索"]) for row in rows]
        parts = submitted_components(detail)
        submitted_name = _compact(f"{parts['last_name']}{parts['first_name']}")
        submitted_kana = _compact(f"{parts['last_name_furigana']}{parts['first_name_furigana']}")
        phone = parts["phone"]
        if not submitted_name and not submitted_kana and not phone:
            return []
        compact_name = func.replace(func.replace(func.coalesce(Worker.name, ""), " ", ""), "　", "")
        compact_kana = func.replace(func.replace(func.coalesce(Worker.furigana, ""), " ", ""), "　", "")
        conditions = []
        if submitted_name:
            conditions.append(compact_name == submitted_name)
        if submitted_kana:
            conditions.append(compact_kana == submitted_kana)
        if phone:
            conditions.append(Worker.phone == phone)
        rows = self.session.scalars(stmt.where(or_(*conditions)).order_by(Worker.name).limit(20)).all()
        found = []
        for row in rows:
            reasons = []
            if submitted_name and _compact(row.name or "") == submitted_name:
                reasons.append("氏名")
            if submitted_kana and _compact(row.furigana or "") == submitted_kana:
                reasons.append("ふりがな")
            if phone and (row.phone or "") == phone:
                reasons.append("電話")
            if reasons:
                found.append(self._candidate(row, reasons))
        return found

    def _candidate(self, worker, reasons: list[str]) -> dict:
        return {
            "worker_id": worker.id,
            "name": worker.name,
            "phone": worker.phone or "",
            "match_reasons": reasons,
        }

    def _new_worker_problem(self, detail) -> str | None:
        parts = submitted_components(detail)
        if (detail.line_registration_form_version or 0) >= 2:
            from src.domain.line_registration_input import normalize_line_registration, LineRegistrationInputError
            try:
                normalize_line_registration(parts, sent=set(parts), linked=False, full_required=True)
            except LineRegistrationInputError as exc:
                return f"{INCOMPLETE} {exc.message}"
        missing = (
            not parts["last_name"]
            or not parts["first_name"]
            or not parts["last_name_furigana"]
            or not parts["first_name_furigana"]
            or not parts["phone"]
            or not parts["birth_date"]
            or not parts["postal_code"]
            or not parts["prefecture"]
            or not parts["address1"]
        )
        postal = parts["postal_code"]
        if missing or len(postal) != 7 or not postal.isascii() or not postal.isdigit():
            return INCOMPLETE
        name = f"{parts['last_name']} {parts['first_name']}"
        furigana = f"{parts['last_name_furigana']} {parts['first_name_furigana']}"
        if len(name) > 100 or len(furigana) > 200:
            return "氏名またはふりがなが長すぎるため、承認できません。"
        try:
            birth = date.fromisoformat(parts["birth_date"])
        except ValueError:
            return INCOMPLETE
        if birth > datetime.now(ZoneInfo("Asia/Tokyo")).date():
            return INCOMPLETE
        return None

    def _check_ticket(self, ticket: str, *, request, reviewer: User, mode: str, worker_id, link_id, before) -> None:
        try:
            verify_line_review_ticket(
                ticket,
                request_id=request.id,
                reviewer_id=reviewer.id,
                mode=mode,
                worker_id=worker_id,
                link_id=link_id,
                before=before,
            )
        except LineReviewTicketError as exc:
            raise LineReviewError(409, exc.message, "ticket_mismatch", request.id) from exc

    def _ensure_open(self, request, context) -> None:
        if request.status != "pending" or request.deleted_at is not None or not context.is_open:
            raise LineReviewError(409, "この申請は、すでに審査が終わっています。", "already_closed", request.id)

    def _lock_request(self, request_id: str) -> None:
        lock_request_row(self.session, request_id)

    def _lock_worker(self, worker_id: str) -> None:
        lock_worker_row(self.session, worker_id)

    def _lock_links(self, line_user_id: str, worker_id: str | None) -> None:
        lock_link_rows(self.session, line_user_id=line_user_id, worker_id=worker_id)


def _compact(value: str) -> str:
    return value.replace(" ", "").replace("　", "").strip()
