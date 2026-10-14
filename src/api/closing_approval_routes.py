"""Authenticated approval endpoints for closing requests."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.closing_approval import ClosingApprovalRequest
from src.models.master import User
from src.models.transaction import Project
from src.services.closing_approval import PERMISSIONS, approve_operation, aware
from src.services.auth import has_permission, AuthorizationError
from src.services.audit import AuditService
from src.exceptions import VANZAIException
from src.services.financial_guards import lock_projects

router = APIRouter(prefix="/api/closing/approvals", tags=["Closing"])


def approval_item(db, row, user):
    requester = db.get(User, row.requested_by)
    project = db.get(Project, row.project_id)
    return {"id": row.id, "project_id": row.project_id, "project_name": project.name if project else "",
            "period_key": row.period_key, "action": row.action, "status": row.status,
            "requested_by": requester.username if requester else "", "reason": row.reason,
            "expires_at": aware(row.expires_at).isoformat(),
            "can_approve": user.id != row.requested_by and has_permission(user, PERMISSIONS[row.action])
                           and aware(row.expires_at) > datetime.now(timezone.utc)}


@router.get("")
def list_approvals(period_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    permitted = [action for action, permission in PERMISSIONS.items() if has_permission(user, permission)]
    if not permitted:
        raise HTTPException(403, "締めの確認権限がありません")
    rows = db.scalars(select(ClosingApprovalRequest).where(ClosingApprovalRequest.period_key == period_key,
        ClosingApprovalRequest.status == "pending", ClosingApprovalRequest.action.in_(permitted))
        .order_by(ClosingApprovalRequest.created_at).limit(100)).all()
    return {"items": [approval_item(db, row, user) for row in rows]}


@router.post("/{request_id}/approve")
def approve_closing(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        result = approve_operation(db, request_id, user)
        db.commit()
        return {"id": result.id, "status": result.status, "project_id": result.project_id, "period_key": result.period_key}
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc
    except VANZAIException as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/{request_id}/reject")
def reject_closing(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = db.get(ClosingApprovalRequest, request_id)
    if not row:
        raise HTTPException(404, "申請が見つかりません")
    if not has_permission(user, PERMISSIONS[row.action]):
        raise HTTPException(403, "この申請の確認権限がありません")
    lock_projects(db, [row.project_id])
    db.refresh(row, with_for_update=True)
    if row.status != "pending":
        raise HTTPException(409, "申請は処理済みです")
    row.status = "rejected"
    AuditService(db).log("closing_approval_rejected", target_type="closing_approval", target_id=row.id,
                         actor=user.username, after_value={"status": "rejected"})
    db.commit()
    return {"id": row.id, "status": row.status}
