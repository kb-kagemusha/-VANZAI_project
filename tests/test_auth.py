"""
権限管理のテスト
仕様参照: DESIGN_SPEC_v0.3 セクション5
"""
import pytest
from sqlalchemy.orm import Session

from src.models.enums import UserRole, Permission
from src.models.master import User, Worker
from src.models.base import generate_ulid
from src.api.jwt_auth import (
    authenticate_user,
    create_user_with_hashed_password,
    oauth2_scheme,
)
from src.services.auth import (
    has_permission,
    check_permission,
    require_permission,
    AuthorizationError,
    ROLE_PERMISSIONS,
    can_access_project,
)


class TestRolePermissions:
    """ロール別権限のテスト"""
    
    def test_admin_has_all_permissions(self, db_session: Session):
        """Admin は全権限を持つ"""
        user = User(
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        
        # 全権限をチェック
        for permission in Permission:
            assert has_permission(user, permission), f"Admin should have {permission}"
    
    def test_ops_permissions(self, db_session: Session):
        """Ops の権限確認"""
        user = User(
            username="ops",
            email="ops@example.com",
            role=UserRole.OPS.value,
            is_active=True,
        )
        
        # 許可されている権限
        assert has_permission(user, Permission.PROJECT_WRITE)
        assert has_permission(user, Permission.SHIFT_WRITE)
        assert has_permission(user, Permission.CSV_IMPORT)
        assert has_permission(user, Permission.INVOICE_GENERATE)
        assert has_permission(user, Permission.PAYOUT_GENERATE)
        
        # 許可されていない権限
        assert not has_permission(user, Permission.PRICE_WRITE)
        assert not has_permission(user, Permission.INVOICE_ISSUE)
        assert not has_permission(user, Permission.PAYOUT_APPROVE)
        assert not has_permission(user, Permission.HARD_CLOSE)
    
    def test_accounting_permissions(self, db_session: Session):
        """Accounting の権限確認"""
        user = User(
            username="accounting",
            email="accounting@example.com",
            role=UserRole.ACCOUNTING.value,
            is_active=True,
        )
        
        # 許可されている権限
        assert has_permission(user, Permission.INVOICE_ISSUE)
        assert has_permission(user, Permission.PAYOUT_APPROVE)
        assert has_permission(user, Permission.SOFT_CLOSE)
        assert has_permission(user, Permission.HARD_CLOSE)
        
        # 許可されていない権限
        assert not has_permission(user, Permission.PROJECT_WRITE)
        assert not has_permission(user, Permission.SHIFT_WRITE)
        assert not has_permission(user, Permission.CSV_IMPORT)
        assert not has_permission(user, Permission.PRICE_WRITE)
    
    def test_site_manager_permissions(self, db_session: Session):
        """Site Manager の権限確認"""
        user = User(
            username="site_manager",
            email="manager@example.com",
            role=UserRole.SITE_MANAGER.value,
            is_active=True,
        )
        
        # 許可されている権限
        assert has_permission(user, Permission.PROJECT_READ)
        assert has_permission(user, Permission.SHIFT_READ)
        assert has_permission(user, Permission.CSV_SUBMIT)
        
        # 許可されていない権限
        assert not has_permission(user, Permission.PROJECT_WRITE)
        assert not has_permission(user, Permission.SHIFT_WRITE)
        assert not has_permission(user, Permission.CSV_IMPORT)
        assert not has_permission(user, Permission.INVOICE_GENERATE)
        assert not has_permission(user, Permission.PRICE_READ)
    
    def test_worker_permissions(self, db_session: Session):
        """Worker の権限確認"""
        user = User(
            username="worker",
            email="worker@example.com",
            role=UserRole.WORKER.value,
            is_active=True,
        )
        
        # 許可されている権限
        assert has_permission(user, Permission.ASSIGNMENT_READ)
        assert has_permission(user, Permission.ACTUAL_READ)
        
        # 許可されていない権限
        assert not has_permission(user, Permission.PROJECT_READ)
        assert not has_permission(user, Permission.SHIFT_READ)
        assert not has_permission(user, Permission.CSV_SUBMIT)


class TestPermissionCheck:
    """権限チェック機能のテスト"""
    
    def test_check_permission_success(self, db_session: Session):
        """権限チェック成功"""
        user = User(
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        
        # 例外が発生しないことを確認
        check_permission(user, Permission.INVOICE_ISSUE)
    
    def test_check_permission_failure(self, db_session: Session):
        """権限チェック失敗"""
        user = User(
            username="worker",
            email="worker@example.com",
            role=UserRole.WORKER.value,
            is_active=True,
        )
        
        # AuthorizationError が発生することを確認
        with pytest.raises(AuthorizationError) as exc_info:
            check_permission(user, Permission.INVOICE_ISSUE)
        
        assert "does not have permission" in str(exc_info.value)
    
    def test_inactive_user_has_no_permission(self, db_session: Session):
        """非アクティブユーザーは権限なし"""
        user = User(
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN.value,
            is_active=False,  # 非アクティブ
        )
        
        assert not has_permission(user, Permission.INVOICE_ISSUE)


class TestRequirePermissionDecorator:
    """権限チェックデコレータのテスト"""
    
    def test_decorator_allows_authorized_user(self, db_session: Session):
        """権限のあるユーザーは実行可能"""
        user = User(
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        
        @require_permission(Permission.INVOICE_ISSUE)
        def issue_invoice(user: User):
            return "success"
        
        result = issue_invoice(user=user)
        assert result == "success"
    
    def test_decorator_blocks_unauthorized_user(self, db_session: Session):
        """権限のないユーザーは実行不可"""
        user = User(
            username="worker",
            email="worker@example.com",
            role=UserRole.WORKER.value,
            is_active=True,
        )
        
        @require_permission(Permission.INVOICE_ISSUE)
        def issue_invoice(user: User):
            return "success"
        
        with pytest.raises(AuthorizationError):
            issue_invoice(user=user)
    
    def test_decorator_with_kwargs(self, db_session: Session):
        """kwargs での user 指定"""
        user = User(
            username="ops",
            email="ops@example.com",
            role=UserRole.OPS.value,
            is_active=True,
        )
        
        @require_permission(Permission.CSV_IMPORT)
        def import_csv(session: Session, user: User):
            return "imported"
        
        result = import_csv(session=db_session, user=user)
        assert result == "imported"


class TestRolePermissionsCompleteness:
    """全ロールに対して権限が定義されているかのテスト"""
    
    def test_all_roles_have_permissions(self):
        """すべてのロールが権限マッピングに含まれている"""
        for role in UserRole:
            assert role in ROLE_PERMISSIONS, f"Role {role} missing in ROLE_PERMISSIONS"
    
    def test_permissions_are_valid(self):
        """すべての権限が Permission enum に存在する"""
        for role, permissions in ROLE_PERMISSIONS.items():
            for permission in permissions:
                assert isinstance(permission, Permission), \
                    f"Invalid permission {permission} for role {role}"


class TestJwtAuthUtilities:
    """JWT認証ユーティリティのテスト"""

    def test_oauth2_token_url_matches_api_route(self):
        """OAuth2 tokenUrl が実APIと一致する"""
        assert oauth2_scheme.model.flows.password.tokenUrl == "/api/auth/token"

    def test_create_user_with_hashed_password(self, db_session: Session):
        """作成時に hashed_password へ保存される"""
        user = create_user_with_hashed_password(
            db=db_session,
            username="login_user",
            email="login_user@example.com",
            password="secret123",
            role="ops",
        )

        assert user.hashed_password
        assert user.hashed_password != "secret123"
        assert user.role == UserRole.OPS.value

    def test_authenticate_user_success(self, db_session: Session):
        """有効ユーザーは認証成功する"""
        create_user_with_hashed_password(
            db=db_session,
            username="active_user",
            email="active_user@example.com",
            password="secret123",
            role="worker",
        )

        user = authenticate_user(db_session, "active_user", "secret123")

        assert user is not None
        assert user.username == "active_user"

    def test_authenticate_user_rejects_inactive_user(self, db_session: Session):
        """非アクティブユーザーは認証拒否される"""
        user = create_user_with_hashed_password(
            db=db_session,
            username="inactive_user",
            email="inactive_user@example.com",
            password="secret123",
            role="worker",
        )
        user.is_active = False
        db_session.add(user)
        db_session.commit()

        assert authenticate_user(db_session, "inactive_user", "secret123") is None


class TestProjectAccessScope:
    """プロジェクトアクセス範囲のテスト"""

    def test_site_manager_can_access_primary_manager_project(
        self,
        db_session: Session,
        worker: Worker,
        project,
    ):
        """primary_manager に紐づく site_manager はアクセス可能"""
        project.primary_manager_id = worker.id
        db_session.add(project)
        db_session.flush()

        user = User(
            id=generate_ulid(),
            username="manager_primary",
            email="manager_primary@example.com",
            role=UserRole.SITE_MANAGER.value,
            is_active=True,
            worker_id=worker.id,
        )

        assert can_access_project(db_session, user, project.id)

    def test_site_manager_can_access_secondary_manager_project(
        self,
        db_session: Session,
        worker: Worker,
        project,
    ):
        """secondary_manager に紐づく site_manager はアクセス可能"""
        project.secondary_manager_id = worker.id
        db_session.add(project)
        db_session.flush()

        user = User(
            id=generate_ulid(),
            username="manager_secondary",
            email="manager_secondary@example.com",
            role=UserRole.SITE_MANAGER.value,
            is_active=True,
            worker_id=worker.id,
        )

        assert can_access_project(db_session, user, project.id)

    def test_site_manager_cannot_access_unassigned_project(
        self,
        db_session: Session,
        worker: Worker,
        project,
    ):
        """担当外案件にはアクセスできない"""
        other_worker = Worker(
            id=generate_ulid(),
            name="Other Worker",
            email="other_worker@example.com",
        )
        db_session.add(other_worker)
        db_session.flush()

        project.primary_manager_id = other_worker.id
        db_session.add(project)
        db_session.flush()

        user = User(
            id=generate_ulid(),
            username="manager_other",
            email="manager_other@example.com",
            role=UserRole.SITE_MANAGER.value,
            is_active=True,
            worker_id=worker.id,
        )

        assert not can_access_project(db_session, user, project.id)

    def test_worker_can_access_assigned_project(
        self,
        db_session: Session,
        worker: Worker,
        project,
        assignment,
    ):
        """worker は自分が割り当てられた案件へアクセス可能"""
        user = User(
            id=generate_ulid(),
            username="worker_user",
            email="worker_user@example.com",
            role=UserRole.WORKER.value,
            is_active=True,
            worker_id=worker.id,
        )

        assert assignment.worker_id == worker.id
        assert can_access_project(db_session, user, project.id)
