"""Guarded recovery for an already-approved operator's explicit login identity.

Only an operator explicitly named by the administrator may be associated with an
existing, free management login. Preview is read-only; no roles are changed.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import src.models
from sqlalchemy import select
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.models.enums import Permission
from src.services.auth import is_management_role, has_permission
from src.services.audit import AuditService


class BindingError(Exception):
    pass


def bind_existing(db, staff_name, username, apply=False):
    staff_query = select(VanzaiStaff).where(VanzaiStaff.name == staff_name, VanzaiStaff.is_active.is_(True), VanzaiStaff.deleted_at.is_(None))
    if apply:
        staff_query = staff_query.with_for_update().execution_options(populate_existing=True)
    rows = db.execute(staff_query).scalars().all()
    if len(rows) != 1:
        raise BindingError("指定した氏名の有効な運営スタッフを1名に特定できません")
    staff = rows[0]
    user_query = select(User).where(User.username == username)
    if apply:
        user_query = user_query.with_for_update().execution_options(populate_existing=True)
    user = db.execute(user_query).scalar_one_or_none()
    if not user or not user.is_active or user.deleted_at or user.worker_id or not is_management_role(user.role, db):
        raise BindingError("指定したIDは有効な未紐付けの管理用IDではありません")
    if user.vanzai_staff_id not in (None, staff.id):
        raise BindingError("指定したIDは別の運営スタッフに紐付いています。変更しません")
    if db.query(User.id).filter(User.vanzai_staff_id == staff.id, User.id != user.id).first():
        raise BindingError("指定した運営スタッフには別のIDが対応しています。変更しません")
    link = db.query(LineStaffLink).filter_by(staff_id=staff.id, status="active").one_or_none()
    if not link:
        raise BindingError("有効な運営LINE連携が確認できません")
    result = {"staff_name": staff.name, "username": user.username, "role": user.role,
              "already_bound": user.vanzai_staff_id == staff.id, "applied": False,
              "permissions": {"wake": has_permission(user, Permission.WAKE_STATUS_READ), "orders": has_permission(user, Permission.ORDER_READ), "availability": has_permission(user, Permission.AVAILABILITY_READ)}}
    if apply and not result["already_bound"]:
        user.vanzai_staff_id = staff.id
        AuditService(db).log("operator_login_bound", target_type="vanzai_staff", target_id=staff.id,
            actor="user-authorized-maintenance", actor_role="maintenance", after_value={"user_id": user.id, "source": "explicit_recovery"})
        db.commit()
    result["applied"] = apply
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staff-name", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from src.domain.line_registration_config import load_line_registration_config
    from src.domain.line_operator_config import load_line_operator_config
    load_line_registration_config(); load_line_operator_config()
    from src.api.deps import SessionLocal
    from src.services.line_operator_menu import reconcile, current_release, MenuClient, MenuError
    with SessionLocal() as db:
        result = bind_existing(db, args.staff_name, args.username, args.apply)
        if args.apply:
            staff = db.query(VanzaiStaff).filter_by(name=args.staff_name, is_active=True, deleted_at=None).one()
            link = db.query(LineStaffLink).filter_by(staff_id=staff.id, status="active").one()
            result["menu_sync"] = reconcile(db, link.line_user_id, force=True)
            db.commit()
            try:
                actual = MenuClient().current(link.line_user_id)
                release = current_release(db)
                result["verified_menu_kind"] = next((kind for kind, value in release.menus.items() if value == actual), None) if release else None
            except MenuError:
                result["verified_menu_kind"] = None
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except BindingError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False)); sys.exit(2)
