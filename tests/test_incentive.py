"""
インセンティブ管理サービスのテスト
仕様参照: DESIGN_SPEC_v0.3.md セクション18
"""
import pytest
from datetime import date, time
from decimal import Decimal
import json

from src.models.enums import UserRole, IncentiveStatus
from src.models.master import User, Client, Site, Worker, IncentiveRule, Role
from src.models.transaction import Project, Incentive, Actual, Assignment, ImportBatch, ShiftSlot
from src.services.incentive_service import IncentiveService, IncentiveCreateInput


def test_create_incentive(session):
    """インセンティブ作成のテスト"""
    # ユーザー作成
    user = User(
        username="ops_user",
        email="ops@test.com",
        role=UserRole.OPS,
        is_active=True
    )
    session.add(user)
    
    # 必要なマスタデータ作成
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    session.add_all([client, site, worker])
    session.flush()    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31))
    session.add(project)
    session.flush()
    
    # インセンティブルール作成
    rule = IncentiveRule(
        name="皆勤賞",
        condition_type="attendance",
        condition_json=json.dumps({"required_days": 20}),
        incentive_amount=Decimal("10000"),
        is_for_invoice=False,
        is_for_payout=True,
        valid_from=date(2025, 1, 1),
        is_active=True
    )
    session.add(rule)
    session.flush()
    
    # インセンティブ作成
    service = IncentiveService(session)
    input_data = IncentiveCreateInput(
        incentive_rule_id=rule.id,
        worker_id=worker.id,
        project_id=project.id,
        period_key="2025-01",
        amount=Decimal("10000"),
        calculation_json=json.dumps({"days": 22})
    )
    
    incentive = service.create_incentive(user, input_data)
    
    assert incentive.id is not None
    assert incentive.status == IncentiveStatus.PENDING
    assert incentive.amount == Decimal("10000")
    assert incentive.period_key == "2025-01"


def test_approve_incentive(session):
    """インセンティブ承認のテスト"""
    # ユーザーとマスタデータ準備
    ops_user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    accounting_user = User(username="accounting", email="acc@test.com", role=UserRole.ACCOUNTING, is_active=True)
    session.add_all([ops_user, accounting_user])
    
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    session.add_all([client, site, worker])
    session.flush()    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31))
    session.add(project)
    
    rule = IncentiveRule(
        name="皆勤賞",
        condition_type="attendance",
        condition_json=json.dumps({"required_days": 20}),
        incentive_amount=Decimal("10000"),
        is_for_invoice=False,
        is_for_payout=True,
        valid_from=date(2025, 1, 1),
        is_active=True
    )
    session.add(rule)
    session.flush()
    
    # インセンティブ作成
    service = IncentiveService(session)
    input_data = IncentiveCreateInput(
        incentive_rule_id=rule.id,
        worker_id=worker.id,
        project_id=project.id,
        period_key="2025-01",
        amount=Decimal("10000"),
        calculation_json=json.dumps({"days": 22})
    )
    incentive = service.create_incentive(ops_user, input_data)
    session.commit()
    
    # 承認
    result = service.approve_incentive(accounting_user, incentive.id)
    
    assert result.success is True
    assert result.incentive.status == IncentiveStatus.APPROVED
    assert result.incentive.approved_by == accounting_user.id


def test_match_attendance_incentive(session):
    """皆勤インセンティブのルールマッチングテスト"""
    # マスタデータ準備
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    session.add_all([client, site, worker])
    session.flush()    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31))
    session.add(project)
    
    rule = IncentiveRule(
        name="皆勤賞",
        condition_type="attendance",
        condition_json=json.dumps({"required_days": 20}),
        incentive_amount=Decimal("10000"),
        is_for_invoice=False,
        is_for_payout=True,
        valid_from=date(2025, 1, 1),
        is_active=True
    )
    session.add(rule)
    session.flush()
    
    # インポートバッチ作成
    import_batch = ImportBatch(
        file_name="test_batch_001.csv",
        file_hash="hash001",
        submitted_by="admin",
        submit_channel="web",
        project_id=project.id,
        period_key="202501",
        mode="append",
        status="completed",
        count_success=22,
        count_error=0
    )
    session.add(import_batch)
    session.flush()
    
    # ロール作成
    role = Role(
        name="一般作業員",
        description="Standard worker role"
    )
    session.add(role)
    session.flush()
    
    # アサインメント作成
    shift_slot = ShiftSlot(
        project_id=project.id,
        work_date=date(2025, 1, 1),
        start_time=time(9, 0),
        end_time=time(17, 0),
        required_count=1
    )
    session.add(shift_slot)
    session.flush()
    
    assignment = Assignment(
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status="confirmed"
    )
    session.add(assignment)
    session.flush()
    
    # 22日分の実績を作成
    for day in range(1, 23):
        actual = Actual(
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2025, 1, day),
            period_key="202501",
            status="valid",
            calc_minutes_total=480,
            calc_minutes_billable=480,
            calc_minutes_break=0,
            applied_price_sales=Decimal("0"),
            applied_price_outsource=Decimal("0"),
        )
        session.add(actual)
    
    session.commit()
    
    # ルールマッチング
    service = IncentiveService(session)
    result = service.match_attendance_incentive(
        worker_id=worker.id,
        period_key="202501",
        project_id=project.id
    )
    
    assert result.matched is True
    assert result.amount == Decimal("10000")
    assert result.calculation_details["actual_days"] == 22
    assert result.calculation_details["required_days"] == 20


def test_match_attendance_incentive_not_enough(session):
    """皆勤インセンティブ：日数不足のテスト"""
    # マスタデータ準備
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    session.add_all([client, site, worker])
    session.flush()    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31))
    session.add(project)
    
    rule = IncentiveRule(
        name="皆勤賞",
        condition_type="attendance",
        condition_json=json.dumps({"required_days": 20}),
        incentive_amount=Decimal("10000"),
        is_for_invoice=False,
        is_for_payout=True,
        valid_from=date(2025, 1, 1),
        is_active=True
    )
    session.add(rule)
    session.flush()
    
    # インポートバッチ作成
    import_batch = ImportBatch(
        file_name="test_batch_002.csv",
        file_hash="hash002",
        submitted_by="admin",
        submit_channel="web",
        project_id=project.id,
        period_key="202501",
        mode="append",
        status="completed",
        count_success=15,
        count_error=0
    )
    session.add(import_batch)
    session.flush()
    
    # ロール作成
    role = Role(
        name="一般作業員",
        description="Standard worker role"
    )
    session.add(role)
    session.flush()
    
    # アサインメント作成
    shift_slot = ShiftSlot(
        project_id=project.id,
        work_date=date(2025, 1, 1),
        start_time=time(9, 0),
        end_time=time(17, 0),
        required_count=1
    )
    session.add(shift_slot)
    session.flush()
    
    assignment = Assignment(
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status="confirmed"
    )
    session.add(assignment)
    session.flush()
    
    # 15日分の実績のみ
    for day in range(1, 16):
        actual = Actual(
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2025, 1, day),
            period_key="202501",
            status="valid",
            calc_minutes_total=480,
            calc_minutes_billable=480,
            calc_minutes_break=0,
            applied_price_sales=Decimal("0"),
            applied_price_outsource=Decimal("0"),
        )
        session.add(actual)
    
    session.commit()
    
    # ルールマッチング
    service = IncentiveService(session)
    result = service.match_attendance_incentive(
        worker_id=worker.id,
        period_key="202501",
        project_id=project.id
    )
    
    assert result.matched is False
    assert result.amount == Decimal("0")
    assert result.calculation_details["actual_days"] == 15
    assert result.calculation_details["reason"] == "Not enough attendance days"
