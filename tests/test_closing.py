"""締め機能のテスト"""
import pytest
from datetime import datetime, timedelta

from src.models.enums import ClosingStatus
from src.models.master import Client
from src.models.transaction import Project
from src.services.closing import (
    soft_close,
    hard_close,
    release_soft_close,
    release_hard_close,
    get_closing_status,
)
from src.exceptions import ClosingViolationException


def test_soft_close(db_session):
    """Soft Close を実施できる"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close 実施
    closing = soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    
    # 検証
    assert closing.status == ClosingStatus.SOFT_CLOSED
    assert closing.soft_closed_at is not None
    assert closing.soft_closed_by == "user1"
    assert closing.release_count == 0


def test_hard_close(db_session):
    """Hard Close を実施できる"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close → Hard Close
    closing = soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    closing = hard_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
    )
    
    # 検証
    assert closing.status == ClosingStatus.HARD_CLOSED
    assert closing.hard_closed_at is not None
    assert closing.hard_closed_by == "user1"


def test_hard_close_fails_with_same_user_and_approver(db_session):
    """Hard Close は同一ユーザー承認では不可"""
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()

    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()

    soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()

    with pytest.raises(ClosingViolationException, match="User and approver must be different"):
        hard_close(
            db_session,
            project_id=project.id,
            period_key="202401",
            user_id="user1",
            approver_id="user1",
        )


def test_release_soft_close_with_guardrails(db_session):
    """Soft Close 解除はガードレール付き"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close
    closing = soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    # 解除（二者承認）
    closing = release_soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
        reason="実績修正のため",
    )
    
    # 検証
    assert closing.status == ClosingStatus.OPEN
    assert closing.release_count == 1
    assert closing.last_released_at is not None
    assert closing.reclose_deadline is not None


def test_release_soft_close_fails_with_same_user(db_session):
    """Soft Close 解除は同一ユーザーでは不可"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close
    closing = soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    # 解除（同一ユーザー）
    with pytest.raises(ClosingViolationException, match="User and approver must be different"):
        release_soft_close(
            db_session,
            project_id=project.id,
            period_key="202401",
            user_id="user1",
            approver_id="user1",
            reason="実績修正のため",
        )


def test_release_soft_close_fails_after_max_count(db_session):
    """Soft Close 解除は 2 回まで"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close
    soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    # 1回目解除
    release_soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
        reason="1回目",
    )
    db_session.flush()
    
    # 再締め
    soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    # 2回目解除
    release_soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
        reason="2回目",
    )
    db_session.flush()
    
    # 再締め
    soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    db_session.flush()
    
    # 3回目解除（エラー）
    with pytest.raises(ClosingViolationException, match="Release count exceeded"):
        release_soft_close(
            db_session,
            project_id=project.id,
            period_key="202401",
            user_id="user1",
            approver_id="user2",
            reason="3回目",
        )


def test_release_hard_close_requires_two_approvers(db_session):
    """Hard Close 解除は二者承認必須"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # Soft Close → Hard Close
    soft_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
    )
    hard_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
    )
    db_session.flush()
    
    # 解除（二者承認）
    closing = release_hard_close(
        db_session,
        project_id=project.id,
        period_key="202401",
        user_id="user1",
        approver_id="user2",
        reason="重大な誤り発見",
    )
    
    # 検証
    assert closing.status == ClosingStatus.SOFT_CLOSED
    assert closing.release_count == 1
    assert "HARD_CLOSE_RELEASE" in closing.last_release_reason


def test_get_closing_status(db_session):
    """締め状態を取得できる"""
    # プロジェクト作成
    client = Client(name="クライアントA")
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="案件A", client_id=client.id)
    db_session.add(project)
    db_session.flush()
    
    # 存在しない場合、デフォルトのOPEN状態が返される
    closing = get_closing_status(db_session, project.id, "202401")
    assert closing is not None
    assert closing.status == ClosingStatus.OPEN.value
    
    # Soft Close 後
    soft_close(db_session, project.id, "202401", user_id="user1")
    closing = get_closing_status(db_session, project.id, "202401")
    assert closing is not None
    assert closing.status == ClosingStatus.SOFT_CLOSED
