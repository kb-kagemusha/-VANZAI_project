"""
権限管理サービス
仕様参照: DESIGN_SPEC_v0.3 セクション5（ロールと権限）

主要機能:
- ロール別権限マッピング
- 権限チェックデコレータ
- プロジェクト範囲での権限チェック（Site Manager用）
"""
from functools import wraps
from typing import Callable, Optional

from sqlalchemy.orm import Session, object_session

from src.models.enums import UserRole, Permission
from src.models.master import User
from src.models.access_policy import RoleAccessPolicy


# ロール別権限マッピング（仕様5.1, 5.2）
ROLE_PERMISSIONS = {
    UserRole.ADMIN: set(Permission),
    UserRole.OPS: {
        # 案件/シフト/アサイン作成、実績取り込み、請求/支払の生成
        Permission.MASTER_READ,
        Permission.PRICE_READ,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.SHIFT_READ,
        Permission.SHIFT_WRITE,
        Permission.ASSIGNMENT_READ,
        Permission.ASSIGNMENT_WRITE,
        Permission.ACTUAL_READ,
        Permission.AVAILABILITY_READ,
        Permission.AVAILABILITY_WRITE,
        Permission.CSV_IMPORT,
        Permission.INVOICE_READ,
        Permission.INVOICE_GENERATE,
        Permission.PAYOUT_READ,
        Permission.PAYOUT_GENERATE,
        Permission.SOFT_CLOSE,
        Permission.EXPENSE_READ,
        Permission.EXPENSE_SUBMIT,
        Permission.INCENTIVE_READ,
        Permission.INCENTIVE_CALCULATE,
        Permission.AUDIT_LOG_READ,
        Permission.NOTICE_READ,
        Permission.NOTICE_WRITE,
    },
    UserRole.ACCOUNTING: {
        # 請求発行、支払承認、締め（Hard Close）承認
        Permission.MASTER_READ,
        Permission.PRICE_READ,
        Permission.PROJECT_READ,
        Permission.SHIFT_READ,
        Permission.ASSIGNMENT_READ,
        Permission.ACTUAL_READ,
        Permission.ACTUAL_WRITE,
        Permission.AVAILABILITY_READ,
        Permission.INVOICE_READ,
        Permission.INVOICE_ISSUE,
        Permission.INVOICE_CORRECT,
        Permission.PAYOUT_READ,
        Permission.PAYOUT_APPROVE,
        Permission.PAYOUT_CORRECT,
        Permission.SOFT_CLOSE,
        Permission.HARD_CLOSE,
        Permission.EXPENSE_READ,
        Permission.EXPENSE_APPROVE,
        Permission.INCENTIVE_READ,
        Permission.INCENTIVE_APPROVE,
        Permission.AUDIT_LOG_READ,
    },
    UserRole.SITE_MANAGER: {
        # 全案件の参照（DEC-056）。CSV提出は担当案件に限定。
        Permission.MASTER_READ,
        Permission.PROJECT_READ,
        Permission.SHIFT_READ,
        Permission.ASSIGNMENT_READ,
        Permission.ACTUAL_READ,
        Permission.CSV_SUBMIT,
    },
    UserRole.WORKER: {
        # 自分のデータ参照と勤怠・経費申請
        Permission.ASSIGNMENT_READ,  # 自分のみ
        Permission.ASSIGNMENT_RESPONSE,
        Permission.ACTUAL_READ,      # 自分のみ
        Permission.ACTUAL_WRITE,     # 自分のみ
        Permission.AVAILABILITY_READ,
        Permission.AVAILABILITY_WRITE,
        Permission.EXPENSE_READ,     # 自分のみ
        Permission.EXPENSE_SUBMIT,   # 自分のみ
        Permission.NOTICE_READ,      # 自分宛ての通知
    },
}


for _role in (UserRole.OPS, UserRole.ACCOUNTING, UserRole.SITE_MANAGER):
    ROLE_PERMISSIONS[_role].add(Permission.DASHBOARD_READ)
for _role in (UserRole.OPS, UserRole.ACCOUNTING):
    ROLE_PERMISSIONS[_role].update({Permission.OCR_READ, Permission.OCR_WRITE,
                                   Permission.REGISTRATION_READ, Permission.ASSIGNMENT_REMIND})
ROLE_PERMISSIONS[UserRole.OPS].update({Permission.ORDER_READ, Permission.ORDER_WRITE, Permission.WAKE_STATUS_READ})
ROLE_PERMISSIONS[UserRole.SITE_MANAGER].add(Permission.AVAILABILITY_READ)
# 運営用LINEメニュー（起床状況・案件の参加予定・発注依頼書）を現場管理でも初期状態で使えるようにする（0.53.8、DEC-125）。
# 金額確定（/api/order-billing）は全体管理者だけのまま。
ROLE_PERMISSIONS[UserRole.SITE_MANAGER].update({Permission.ORDER_READ, Permission.WAKE_STATUS_READ})
ROLE_PERMISSIONS[UserRole.OPS].update({Permission.ATTENDANCE_NOTE_READ, Permission.ATTENDANCE_NOTE_WRITE})
ROLE_PERMISSIONS[UserRole.ACCOUNTING].add(Permission.ATTENDANCE_NOTE_READ)


class AuthorizationError(Exception):
    """権限エラー"""
    pass


ROLE_NAMES = {"admin": "全体管理者", "ops": "運用担当", "accounting": "経理担当",
              "site_manager": "現場管理者", "worker": "稼働者"}


def is_management_role(role: str, db: Session | None) -> bool:
    if role in {"admin", "ops", "accounting", "site_manager"}:
        return True
    return role != "worker" and db is not None and db.get(RoleAccessPolicy, role) is not None


def get_role_name(user: User, db: Session | None = None) -> str:
    session = db if db is not None else object_session(user)
    policy = session.get(RoleAccessPolicy, user.role) if session is not None else None
    return policy.display_name if policy is not None and policy.display_name else ROLE_NAMES.get(user.role, user.role)


def get_user_permissions(user: User, session: Session | None = None) -> set[Permission]:
    if not user.is_active or user.deleted_at is not None:
        return set()
    role = user.role
    if role == UserRole.ADMIN:
        return set(Permission)
    db = session if session is not None else object_session(user)
    if db is not None and role != UserRole.WORKER:
        policy = db.get(RoleAccessPolicy, role)
        if policy is not None:
            return {Permission(p) for p in policy.permissions if p in Permission._value2member_map_}
    return ROLE_PERMISSIONS.get(role, set()).copy()


def has_permission(user: User, permission: Permission) -> bool:
    """
    ユーザーが指定された権限を持つか確認
    
    Args:
        user: ユーザー
        permission: 確認する権限
    
    Returns:
        True: 権限あり, False: 権限なし
    """
    return permission in get_user_permissions(user)


def check_permission(user: User, permission: Permission) -> None:
    """
    権限をチェックし、なければ例外を発生
    
    Args:
        user: ユーザー
        permission: 確認する権限
    
    Raises:
        AuthorizationError: 権限がない場合
    """
    if not has_permission(user, permission):
        raise AuthorizationError(
            f"User {user.username} (role={user.role}) does not have permission: {permission.value}"
        )


def require_permission(permission: Permission):
    """
    権限チェックデコレータ
    
    使用例:
        @require_permission(Permission.INVOICE_ISSUE)
        def issue_invoice(session: Session, invoice_id: str, user: User):
            ...
    
    Args:
        permission: 必要な権限
    
    Returns:
        デコレータ関数
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # user引数を探す
            user = kwargs.get('user')
            if user is None:
                # 引数から探す
                for arg in args:
                    if isinstance(arg, User):
                        user = arg
                        break
            
            if user is None:
                raise AuthorizationError("User not found in function arguments")
            
            check_permission(user, permission)
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def can_access_project(
    session: Session,
    user: User,
    project_id: str,
) -> bool:
    """
    ユーザーが指定されたプロジェクトにアクセスできるか確認
    
    仕様参照: 5.2 Site Managerの操作範囲
    
    Args:
        session: DBセッション
        user: ユーザー
        project_id: プロジェクトID
    
    Returns:
        True: アクセス可, False: アクセス不可
    """
    role = user.role
    
    # Admin, Ops, Accounting は全プロジェクトにアクセス可
    if role in (UserRole.ADMIN, UserRole.OPS, UserRole.ACCOUNTING) or (
        role != UserRole.WORKER and is_management_role(role, session) and has_permission(user, Permission.PROJECT_READ)
    ):
        return True
    
    # Site Manager は全案件を参照（DEC-056）
    if role == UserRole.SITE_MANAGER:
        # DEC-056: all projects are readable. Write operations still require permissions.
        return user.is_active and user.deleted_at is None
    # Worker は自分がアサインされているプロジェクトのみ
    if role == UserRole.WORKER:
        if user.worker_id:
            from src.models.transaction import Assignment
            from sqlalchemy import select, and_
            
            stmt = select(Assignment).where(
                and_(
                    Assignment.worker_id == user.worker_id,
                    Assignment.shift_slot.has(project_id=project_id)
                )
            )
            assignment = session.execute(stmt).scalars().first()
            return assignment is not None
        return False
    
    return False


def can_submit_project_csv(session: Session, user: User, project_id: str) -> bool:
    """All-project visibility must not broaden the existing CSV submission scope."""
    if has_permission(user, Permission.CSV_IMPORT):
        return True
    if not has_permission(user, Permission.CSV_SUBMIT) or not user.worker_id:
        return False
    from src.models.transaction import Project
    project = session.get(Project, project_id)
    return project is not None and user.worker_id in (project.primary_manager_id, project.secondary_manager_id)


def check_project_access(
    session: Session,
    user: User,
    project_id: str,
) -> None:
    """
    プロジェクトアクセス権限をチェックし、なければ例外を発生
    
    Args:
        session: DBセッション
        user: ユーザー
        project_id: プロジェクトID
    
    Raises:
        AuthorizationError: アクセス権限がない場合
    """
    if not can_access_project(session, user, project_id):
        raise AuthorizationError(
            f"User {user.username} cannot access project {project_id}"
        )
