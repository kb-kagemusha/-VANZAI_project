"""Administrator-only account and role management. No physical deletion."""
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user, get_password_hash
from src.models.master import User
from src.models.access_policy import RoleAccessPolicy
from src.models.enums import Permission, UserRole
from src.services.auth import ROLE_PERMISSIONS, ROLE_NAMES, get_user_permissions, get_role_name, is_management_role
from src.services.audit import AuditService

router = APIRouter(prefix="/api/access", tags=["Account management"])
MANAGEMENT_ROLES = {"admin", "ops", "accounting", "site_manager"}


def administrator(user: User = Depends(get_current_active_user)):
    if user.role != "admin":
        raise HTTPException(403, "ID作成・権限設定は全体管理者のみ操作できます")
    return user


def account_item(user):
    return {"id": user.id, "username": user.username, "display_name": user.display_name,
            "email": user.email, "role": user.role, "role_name": get_role_name(user), "is_active": user.is_active}


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.@-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(min_length=1, max_length=20)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("パスワードはUTF-8で72バイト以内にしてください")
        return value

    @field_validator("display_name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("表示名を入力してください")
        return value.strip()


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=1, max_length=20)
    is_active: bool
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonempty_reason(cls, value):
        if not value.strip():
            raise ValueError("変更理由を入力してください")
        return value.strip()


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: list[Permission]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonempty_reason(cls, value):
        if not value.strip():
            raise ValueError("変更理由を入力してください")
        return value.strip()


class RoleCreate(PolicyUpdate):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def name_valid(cls, value):
        name = value.strip()
        if not name or name in ROLE_NAMES or name in ROLE_NAMES.values():
            raise ValueError("既存の役割と異なる名前を入力してください")
        return name


def validate_permissions(permissions):
    values = sorted(set(p.value for p in permissions))
    for value in values:
        read_permission = value.rsplit("_", 1)[0] + "_read"
        if read_permission in Permission._value2member_map_ and read_permission not in values:
            raise HTTPException(422, "編集・承認などの操作には、同じ機能の閲覧権限も必要です")
    return values


@router.get("/users")
def accounts(search: str = "", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
             actor: User = Depends(administrator), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.deleted_at.is_(None))
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.username.ilike(term), User.display_name.ilike(term), User.email.ilike(term)))
    return {"items": [account_item(u) for u in query.order_by(User.username, User.id).offset(offset).limit(limit)],
            "total": query.count(), "offset": offset, "limit": limit}


@router.post("/users", status_code=201)
def create_account(body: AccountCreate, actor: User = Depends(administrator), db: Session = Depends(get_db)):
    if not is_management_role(body.role, db):
        raise HTTPException(422, "スタッフ用IDは既存のスタッフ登録フローを使用してください")
    user = User(username=body.username, display_name=body.display_name, email=body.email,
                hashed_password=get_password_hash(body.password), role=body.role, is_active=True)
    try:
        db.add(user)
        db.flush()
        AuditService(db).log("USER_CREATED", target_type="user", target_id=user.id,
                             actor=actor.id, actor_role=actor.role, after_value=account_item(user))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "このログインIDまたはメールアドレスは既に登録されています")
    return account_item(user)


@router.put("/users/{user_id}")
def update_account(user_id: str, body: AccountUpdate, actor: User = Depends(administrator), db: Session = Depends(get_db)):
    # Lock the actor as well: concurrent administrators cannot disable/demote each other.
    locked = list(db.scalars(select(User).where(User.id.in_([actor.id, user_id])).order_by(User.id).with_for_update()).all())
    current = next((u for u in locked if u.id == actor.id), None)
    db.refresh(current)
    if current.role != "admin" or not current.is_active:
        raise HTTPException(403, "管理者権限が変更されています。再ログインしてください")
    user = next((u for u in locked if u.id == user_id), None)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "IDが見つかりません")
    db.refresh(user)
    if body.role != "worker" and not is_management_role(body.role, db):
        raise HTTPException(422, "存在する役割を選択してください")
    if body.role == UserRole.WORKER and not user.worker_id:
        raise HTTPException(422, "スタッフ役割には稼働者の紐付けが必要です")
    if user.id == actor.id and (body.role != UserRole.ADMIN or not body.is_active):
        raise HTTPException(409, "自分自身の管理者権限の解除・無効化はできません")
    before = account_item(user)
    user.role = body.role
    user.is_active = body.is_active
    AuditService(db).log("USER_ACCESS_CHANGED", target_type="user", target_id=user.id,
                         actor=actor.id, actor_role="admin", before_value=before,
                         after_value=account_item(user), reason=body.reason)
    db.commit()
    return account_item(user)


@router.get("/roles")
def policies(actor: User = Depends(administrator), db: Session = Depends(get_db)):
    custom = db.query(RoleAccessPolicy).filter(RoleAccessPolicy.role.notin_(list(ROLE_NAMES))).order_by(RoleAccessPolicy.display_name, RoleAccessPolicy.role).all()
    roles = ["admin", "ops", "accounting", "site_manager"] + [row.role for row in custom]
    return {"available_permissions": [p.value for p in Permission], "roles": [
        {"role": role, "permissions": sorted(p.value for p in get_user_permissions(User(role=role, is_active=True), db)),
         "display_name": get_role_name(User(role=role, is_active=True), db),
         "default_permissions": sorted(p.value for p in ROLE_PERMISSIONS.get(role, set())), "editable": role != "admin", "builtin": role in ROLE_NAMES}
        for role in roles
    ]}


@router.post("/roles", status_code=201)
def create_role(body: RoleCreate, actor: User = Depends(administrator), db: Session = Depends(get_db)):
    values = validate_permissions(body.permissions)
    row = RoleAccessPolicy(role="r_" + secrets.token_hex(8), display_name=body.display_name, permissions=values)
    try:
        db.add(row)
        db.flush()
        AuditService(db).log("ROLE_CREATED", target_type="role_access_policy", target_id=row.role,
                             actor=actor.id, actor_role=actor.role,
                             after_value={"display_name": row.display_name, "permissions": values}, reason=body.reason)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "この役割名は既に登録されています")
    return {"role": row.role, "display_name": row.display_name, "permissions": values}


@router.put("/roles/{role}")
def update_policy(role: str, body: PolicyUpdate, actor: User = Depends(administrator), db: Session = Depends(get_db)):
    if not is_management_role(role, db) or role == "admin":
        raise HTTPException(422, "全体管理者の権限とスタッフの権限はこの画面では変更できません")
    before = sorted(p.value for p in get_user_permissions(User(role=role, is_active=True), db))
    values = validate_permissions(body.permissions)
    row = db.get(RoleAccessPolicy, role)
    if row is None:
        row = RoleAccessPolicy(role=role, permissions=values)
        db.add(row)
    else:
        row.permissions = values
    AuditService(db).log("ROLE_PERMISSIONS_CHANGED", target_type="role_access_policy", target_id=role,
                         actor=actor.id, actor_role=actor.role, before_value={"permissions": before},
                         after_value={"permissions": values}, reason=body.reason)
    db.commit()
    return {"role": role, "permissions": values}
