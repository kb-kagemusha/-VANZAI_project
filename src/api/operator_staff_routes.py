"""Operator contacts. Management labels do not grant login privileges."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.base import generate_ulid
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.services.audit import AuditService
from src.services.operator_staff import OperatorStaffService
from src.services.order_request_service import OrderRequestError

router = APIRouter(prefix="/api/operator-staff", tags=["Operator staff"])
ManagementRole = Literal["総合管理", "支払い経理", "収益管理", "現場管理", "基礎管理"]


class ProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    can_drive: bool | None = None
    smoking_area_ok: bool | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=200)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    emergency_contact_relationship: str | None = Field(default=None, max_length=50)
    management_roles: list[ManagementRole] = Field(default_factory=list, max_length=5)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=10000)
    profile_revision: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        if not value.strip():
            raise ValueError("氏名を入力してください")
        return value.strip()

    @field_validator("management_roles")
    @classmethod
    def role_unique(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("付与ロールが重複しています")
        return value


class Reason(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    @field_validator("reason")
    @classmethod
    def reason_valid(cls, value):
        if not value.strip():
            raise ValueError("解除理由を入力してください")
        return value.strip()


def ensure_admin(user):
    if user.role != "admin":
        raise HTTPException(403, "運営スタッフの管理は総合管理者が行います")


def out(staff, link):
    fields = ("id", "name", "phone", "email", "can_drive", "smoking_area_ok", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship", "management_roles", "is_active", "notes", "profile_revision")
    return {**{key: getattr(staff, key) for key in fields}, "management_roles": staff.management_roles or [], "line_linked": link is not None, "line_display_name": link.line_display_name if link else None, "line_linked_at": link.linked_at if link else None}


def transact(db, action):
    try:
        result = action()
        db.commit()
        return result
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, exc.detail) from None


@router.get("")
def list_profiles(search: str = Query("", max_length=100), offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200), current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(current_user)
    query = db.query(VanzaiStaff).filter(VanzaiStaff.deleted_at.is_(None))
    if search.strip():
        query = query.filter(VanzaiStaff.name.ilike(f"%{search.strip()}%"))
    total = query.count()
    staff = query.order_by(VanzaiStaff.name, VanzaiStaff.id).offset(offset).limit(limit).all()
    links = {link.staff_id: link for link in db.query(LineStaffLink).filter(LineStaffLink.status == "active", LineStaffLink.staff_id.in_([s.id for s in staff])).all()}
    return {"items": [out(s, links.get(s.id)) for s in staff], "total": total, "offset": offset, "limit": limit}


@router.post("", status_code=201)
def create_profile(body: ProfileWrite, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(current_user)
    def action():
        staff = VanzaiStaff(id=generate_ulid(), **body.model_dump(exclude={"profile_revision"}), profile_revision=1)
        db.add(staff)
        db.flush()
        AuditService(db).log("operator_staff_created", target_type="vanzai_staff", target_id=staff.id, actor=current_user.id, actor_role=current_user.role, after_value={"management_roles": staff.management_roles, "profile_revision": 1})
        return out(staff, None)
    return transact(db, action)


@router.put("/{staff_id}")
def update_profile(staff_id: str, body: ProfileWrite, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(current_user)
    def action():
        service = OperatorStaffService(db)
        staff = service.staff(staff_id, lock=True)
        if body.profile_revision is None or body.profile_revision != staff.profile_revision:
            raise OrderRequestError(409, "他の担当者が情報を更新しています。最新の内容を読み込んでください")
        before_roles = staff.management_roles or []
        for key, value in body.model_dump(exclude={"profile_revision"}).items():
            setattr(staff, key, value)
        staff.profile_revision += 1
        AuditService(db).log("operator_staff_updated", target_type="vanzai_staff", target_id=staff.id, actor=current_user.id, actor_role=current_user.role, before_value={"management_roles": before_roles}, after_value={"management_roles": staff.management_roles, "profile_revision": staff.profile_revision})
        return out(staff, service.active_link(staff_id))
    return transact(db, action)


@router.post("/{staff_id}/line-code")
def issue_code(staff_id: str, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(current_user)
    def action():
        code, expiry = OperatorStaffService(db).issue_code(staff_id, current_user)
        return {"code": code, "expires_at": expiry, "instruction": "友だち追加した公式LINEへ、このコードだけを本人から送ってください。有効期限は30分です。"}
    return transact(db, action)


@router.post("/{staff_id}/line-revoke")
def revoke(staff_id: str, body: Reason, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(current_user)
    return transact(db, lambda: OperatorStaffService(db).revoke(staff_id, current_user, body.reason))
