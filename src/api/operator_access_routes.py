"""Administrator explicitly maps an operator to an existing management login."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.operator_staff_routes import ensure_admin
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.models.line_operator import LineOperatorMenuState
from src.services.auth import is_management_role
from src.services.audit import AuditService
from src.services.line_operator_menu import reconcile

def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/operator-access", tags=["Operator access"], dependencies=[Depends(no_store)])


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str | None = Field(default=None, min_length=1, max_length=26)


@router.get("/{staff_id}")
def status(staff_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    staff = db.get(VanzaiStaff, staff_id)
    if not staff or staff.deleted_at is not None:
        raise HTTPException(404, "運営スタッフが見つかりません")
    users = db.query(User).filter(User.deleted_at.is_(None)).order_by(User.username).all()
    linked = [u for u in users if u.vanzai_staff_id == staff_id]
    line = db.query(LineStaffLink).filter_by(staff_id=staff_id, status="active").one_or_none()
    state = db.get(LineOperatorMenuState, line.line_user_id) if line else None
    return {"user_ids": [u.id for u in linked], "menu_status": state.status if state else "pending" if line else "not_linked", "users": [
        {"id": u.id, "name": u.display_name or u.username, "username": u.username, "is_active": u.is_active, "available": (not u.worker_id and u.vanzai_staff_id in (None, staff_id))}
        for u in users if is_management_role(u.role, db)]}


@router.put("/{staff_id}")
def bind(staff_id: str, body: Binding, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    staff = db.execute(select(VanzaiStaff).where(VanzaiStaff.id == staff_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
    if not staff or staff.deleted_at is not None:
        raise HTTPException(404, "運営スタッフが見つかりません")
    target = db.execute(select(User).where(User.id == body.user_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none() if body.user_id else None
    if body.user_id and (not target or not target.is_active or target.deleted_at or not is_management_role(target.role, db) or target.worker_id or target.vanzai_staff_id not in (None, staff_id)):
        raise HTTPException(409, "有効な管理ロールのIDを選んでください。稼働者/別の運営に対応したIDは紐付けられません。")
    current = db.execute(select(User).where(User.vanzai_staff_id == staff_id).with_for_update()).scalars().all()
    before = [row.id for row in current]
    for row in current:
        row.vanzai_staff_id = None
    if target:
        target.vanzai_staff_id = staff_id
    AuditService(db).log("operator_login_bound", target_type="vanzai_staff", target_id=staff_id, actor=user.id, actor_role=user.role, before_value={"user_ids": before}, after_value={"user_id": target.id if target else None})
    db.commit()
    line = db.query(LineStaffLink).filter_by(staff_id=staff_id, status="active").one_or_none()
    if line:
        try:
            reconcile(db, line.line_user_id, force=True)
            db.commit()
        except Exception:
            db.rollback()
    return status(staff_id, user, db)


@router.post("/{staff_id}/sync")
def sync(staff_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    line = db.query(LineStaffLink).filter_by(staff_id=staff_id, status="active").one_or_none()
    if not line:
        raise HTTPException(409, "有効なLINE連携がありません")
    result = reconcile(db, line.line_user_id, force=True)
    db.commit()
    return {"status": result}
