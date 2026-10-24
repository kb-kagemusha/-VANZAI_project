"""Request and approve closing operations under different authenticated users."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.exceptions import ClosingViolationException, RecordNotFoundException
from src.models.closing_approval import ClosingApprovalRequest
from src.models.master import User
from src.models.transaction import Closing
from src.models.enums import Permission
from src.services.auth import check_permission, has_permission
from src.services.financial_guards import lock_projects
from src.services.audit import AuditService

PERMISSIONS = {"hard_close": Permission.HARD_CLOSE, "soft_release": Permission.SOFT_CLOSE_RELEASE,
               "hard_release": Permission.HARD_CLOSE_RELEASE}
EXPECTED = {"hard_close": "soft_closed", "soft_release": "soft_closed", "hard_release": "hard_closed"}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def request_operation(session, project_id, period_key, action, requester, reason):
    check_permission(requester, PERMISSIONS[action])
    lock_projects(session, [project_id])
    state = session.scalar(select(Closing).where(Closing.project_id == project_id, Closing.period_key == period_key))
    if not state or state.status != EXPECTED[action]:
        raise ClosingViolationException("締め状態が変わったため申請できません")
    if action != "hard_close" and state.release_count >= 2:
        raise ClosingViolationException("Release count exceeded: 締め解除は合計2回までです")
    reason = (reason or "").strip()
    if not reason:
        raise ClosingViolationException("申請理由を入力してください")
    now = datetime.now(timezone.utc)
    pending = session.scalars(select(ClosingApprovalRequest).where(
        ClosingApprovalRequest.project_id == project_id, ClosingApprovalRequest.period_key == period_key,
        ClosingApprovalRequest.action == action, ClosingApprovalRequest.status == "pending")).all()
    for row in pending:
        if aware(row.expires_at) <= now:
            row.status = "expired"
        else:
            raise ClosingViolationException("同じ操作の申請が確認待ちです")
    session.flush()
    row = ClosingApprovalRequest(project_id=project_id, period_key=period_key, action=action,
        requested_by=requester.id, reason=reason, expected_status=state.status,
        expected_release_count=state.release_count, expires_at=now + timedelta(hours=24))
    session.add(row)
    session.flush()
    AuditService(session).log("closing_approval_requested", target_type="closing_approval", target_id=row.id, actor=requester.username, after_value={"action": action, "status": "pending"})
    return row


def approve_operation(session, request_id, approver):
    row = session.get(ClosingApprovalRequest, request_id)
    if not row:
        raise RecordNotFoundException("ClosingApprovalRequest", request_id)
    lock_projects(session, [row.project_id])
    row = session.scalar(select(ClosingApprovalRequest).where(ClosingApprovalRequest.id == request_id)
                         .with_for_update().execution_options(populate_existing=True))
    check_permission(approver, PERMISSIONS[row.action])
    requester = session.get(User, row.requested_by)
    if not approver.is_active or not requester or not requester.is_active:
        raise ClosingViolationException("有効な申請者・承認者が必要です")
    check_permission(requester, PERMISSIONS[row.action])
    if requester.id == approver.id:
        raise ClosingViolationException("申請者本人は承認できません。別の権限者がログインして承認してください。")
    if row.status != "pending" or aware(row.expires_at) <= datetime.now(timezone.utc):
        raise ClosingViolationException("申請は処理済み、または期限切れです")
    state = session.scalar(select(Closing).where(Closing.project_id == row.project_id, Closing.period_key == row.period_key)
                           .execution_options(populate_existing=True))
    if not state or state.status != row.expected_status or state.release_count != row.expected_release_count:
        raise ClosingViolationException("申請後に締め状態が変わったため承認できません")
    from src.services import closing
    with session.begin_nested():
        row.status = "approved"
        row.approved_by = approver.id
        row.approved_at = datetime.now(timezone.utc)
        session.flush()
        args = dict(session=session, project_id=row.project_id, period_key=row.period_key,
                    user_id=requester.username, approver_id=approver.username, approval_request_id=row.id)
        if row.action == "hard_close":
            result = closing.hard_close(**args, notes=row.reason)
        elif row.action == "soft_release":
            result = closing.release_soft_close(**args, reason=row.reason)
        else:
            result = closing.release_hard_close(**args, reason=row.reason)
        AuditService(session).log("closing_approval_approved", target_type="closing_approval", target_id=row.id,
                                 actor=approver.username, after_value={"action": row.action, "status": "approved"})
    return result


def require_approval(session, request_id, project_id, period_key, action, requester_name, approver_name):
    row = session.get(ClosingApprovalRequest, request_id) if request_id else None
    requester = session.get(User, row.requested_by) if row else None
    approver = session.get(User, row.approved_by) if row and row.approved_by else None
    state = session.scalar(select(Closing).where(Closing.project_id == project_id, Closing.period_key == period_key))
    if (not row or not state or state.status != row.expected_status or state.release_count != row.expected_release_count
        or aware(row.expires_at) <= datetime.now(timezone.utc) or row.status != "approved" or row.project_id != project_id or row.period_key != period_key
        or row.action != action or not requester or not approver or requester.id == approver.id
        or requester.username != requester_name or approver.username != approver_name
        or not requester.is_active or not approver.is_active or not has_permission(approver, PERMISSIONS[action])):
        raise ClosingViolationException("別の認証済み権限者による承認が必要です")
