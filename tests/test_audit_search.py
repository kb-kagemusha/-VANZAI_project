"""
監査ログ検索APIのテスト
仕様参照: DESIGN_SPEC_v0.3 セクション16（監査ログ）
推奨タスク: 監査ログの充実（検索API実装）
"""
import pytest
from datetime import date, datetime, timezone
from src.models.enums import AuditAction, UserRole
from src.models.master import User
from src.services.audit import AuditService, AuditLogSearchFilter


def test_search_audit_logs_by_action(session):
    """アクション種別でフィルタできること"""
    user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    session.add(user)
    session.flush()
    
    service = AuditService(session)
    
    # 3種類のログを作成
    service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="batch1", actor="ops")
    service.log(AuditAction.IMPORT_BATCH_COMPLETED, target_type="import_batch", target_id="batch1", actor="ops")
    service.log(AuditAction.CLOSING_HARD_CLOSED, target_type="closing", target_id="202601", actor="ops")
    session.commit()
    
    # IMPORT_BATCH_CREATED のみ検索
    result = service.search_audit_logs(
        AuditLogSearchFilter(action_type=AuditAction.IMPORT_BATCH_CREATED)
    )
    
    assert result.total_count == 1
    assert len(result.logs) == 1
    assert result.logs[0].action == AuditAction.IMPORT_BATCH_CREATED.value
    assert result.has_more is False


def test_search_audit_logs_by_actor(session):
    """実行者でフィルタできること"""
    service = AuditService(session)
    
    service.log(AuditAction.IMPORT_BATCH_CREATED, actor="admin", target_type="import_batch", target_id="b1")
    service.log(AuditAction.IMPORT_BATCH_CREATED, actor="ops", target_type="import_batch", target_id="b2")
    service.log(AuditAction.IMPORT_BATCH_CREATED, actor="ops", target_type="import_batch", target_id="b3")
    session.commit()
    
    result = service.search_audit_logs(
        AuditLogSearchFilter(actor="ops")
    )
    
    assert result.total_count == 2
    assert all(log.actor == "ops" for log in result.logs)


def test_search_audit_logs_by_date_range(session):
    """日付範囲でフィルタできること"""
    service = AuditService(session)
    
    # 異なる日付で3件作成
    log1 = service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="b1")
    log1.created_at = datetime(2026, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
    
    log2 = service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="b2")
    log2.created_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    
    log3 = service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="b3")
    log3.created_at = datetime(2026, 1, 25, 14, 0, 0, tzinfo=timezone.utc)
    
    session.commit()
    
    # 1/10 ~ 1/20 で検索
    result = service.search_audit_logs(
        AuditLogSearchFilter(
            date_from=date(2026, 1, 10),
            date_to=date(2026, 1, 20)
        )
    )
    
    assert result.total_count == 1
    assert result.logs[0].target_id == "b2"


def test_search_audit_logs_by_period_key(session):
    """period_keyで検索できること（created_atでおおよそフィルタ）"""
    service = AuditService(session)
    
    # 2026年1月のログ
    log1 = service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="b1")
    log1.created_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    # 2026年2月のログ
    log2 = service.log(AuditAction.IMPORT_BATCH_CREATED, target_type="import_batch", target_id="b2")
    log2.created_at = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    session.commit()
    
    # period_key="202601" で検索
    result = service.search_audit_logs(
        AuditLogSearchFilter(period_key="202601")
    )
    
    assert result.total_count == 1
    assert result.logs[0].target_id == "b1"


def test_search_audit_logs_pagination(session):
    """ページングが機能すること"""
    service = AuditService(session)
    
    # 10件作成
    for i in range(10):
        service.log(
            AuditAction.IMPORT_BATCH_CREATED,
            target_type="import_batch",
            target_id=f"batch{i}",
            actor="ops"
        )
    session.commit()
    
    # 最初の3件
    result1 = service.search_audit_logs(
        AuditLogSearchFilter(limit=3, offset=0)
    )
    assert len(result1.logs) == 3
    assert result1.total_count == 10
    assert result1.has_more is True
    
    # 次の3件
    result2 = service.search_audit_logs(
        AuditLogSearchFilter(limit=3, offset=3)
    )
    assert len(result2.logs) == 3
    assert result2.has_more is True
    
    # 最後
    result3 = service.search_audit_logs(
        AuditLogSearchFilter(limit=3, offset=9)
    )
    assert len(result3.logs) == 1
    assert result3.has_more is False


def test_search_audit_logs_combined_filters(session):
    """複数フィルタを組み合わせて検索できること"""
    service = AuditService(session)
    
    # admin による1月の締め操作
    log1 = service.log(
        AuditAction.CLOSING_HARD_CLOSED,
        target_type="closing",
        target_id="202601",
        actor="admin"
    )
    log1.created_at = datetime(2026, 1, 31, 23, 59, 0, tzinfo=timezone.utc)
    
    # ops による1月のCSV取り込み
    log2 = service.log(
        AuditAction.IMPORT_BATCH_COMPLETED,
        target_type="import_batch",
        target_id="batch1",
        actor="ops"
    )
    log2.created_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    # admin による2月のCSV取り込み
    log3 = service.log(
        AuditAction.IMPORT_BATCH_COMPLETED,
        target_type="import_batch",
        target_id="batch2",
        actor="admin"
    )
    log3.created_at = datetime(2026, 2, 10, 10, 0, 0, tzinfo=timezone.utc)
    
    session.commit()
    
    # admin + 1月 で検索
    result = service.search_audit_logs(
        AuditLogSearchFilter(
            actor="admin",
            period_key="202601"
        )
    )
    
    assert result.total_count == 1
    assert result.logs[0].action == AuditAction.CLOSING_HARD_CLOSED.value
    assert result.logs[0].actor == "admin"


def test_search_audit_logs_empty_result(session):
    """該当なしの場合は空リストが返ること"""
    service = AuditService(session)
    
    result = service.search_audit_logs(
        AuditLogSearchFilter(actor="nonexistent")
    )
    
    assert result.total_count == 0
    assert result.logs == []
    assert result.has_more is False
