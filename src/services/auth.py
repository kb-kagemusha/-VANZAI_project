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

from sqlalchemy.orm import Session

from src.models.enums import UserRole, Permission
from src.models.master import User


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
        # 担当案件の参照、CSV提出、エラー修正再提出
        Permission.MASTER_READ,
        Permission.PROJECT_READ,  # 担当案件のみ
        Permission.SHIFT_READ,    # 担当案件のみ
        Permission.ASSIGNMENT_READ,  # 担当案件のみ
        Permission.ACTUAL_READ,   # 担当案件のみ
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
    },
}


class AuthorizationError(Exception):
    """権限エラー"""
    pass


def has_permission(user: User, permission: Permission) -> bool:
    """
    ユーザーが指定された権限を持つか確認
    
    Args:
        user: ユーザー
        permission: 確認する権限
    
    Returns:
        True: 権限あり, False: 権限なし
    """
    if not user.is_active:
        return False
    
    role = UserRole(user.role)
    return permission in ROLE_PERMISSIONS.get(role, set())


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
    role = UserRole(user.role)
    
    # Admin, Ops, Accounting は全プロジェクトにアクセス可
    if role in (UserRole.ADMIN, UserRole.OPS, UserRole.ACCOUNTING):
        return True
    
    # Site Manager は担当プロジェクトのみ
    if role == UserRole.SITE_MANAGER:
        if user.worker_id:
            from src.models.transaction import Project
            
            project = session.get(Project, project_id)
            if not project:
                return False
            
            # Method 1: Project の primary/secondary manager
            if project.primary_manager_id == user.worker_id:
                return True
            if project.secondary_manager_id == user.worker_id:
                return True

            return False
        return False
    
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
