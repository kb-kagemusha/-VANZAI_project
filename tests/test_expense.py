"""
経費精算サービスのテスト
仕様参照: DESIGN_SPEC_v0.3.md セクション17
"""
import pytest
from datetime import date
from decimal import Decimal

from src.models.enums import UserRole, ExpenseStatus
from src.models.master import User, Client, Site, Worker
from src.models.transaction import Project, Expense
from src.services.expense_service import ExpenseService, ExpenseCreateInput


def test_create_expense(session):
    """経費作成のテスト"""
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
        end_date=date(2025, 12, 31)
    )
    session.add(project)
    session.flush()
    
    # 経費作成
    service = ExpenseService(session)
    input_data = ExpenseCreateInput(
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2025, 1, 15),
        category="交通費",
        amount=Decimal("5000"),
        description="客先訪問",
        target_payout=True
    )
    
    expense = service.create_expense(user, input_data)
    
    assert expense.id is not None
    assert expense.status == ExpenseStatus.PENDING
    assert expense.amount == Decimal("5000")
    assert expense.category == "交通費"


def test_approve_expense(session):
    """経費承認のテスト"""
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
        end_date=date(2025, 12, 31)
    )
    session.add(project)
    session.flush()
    
    # 経費作成
    service = ExpenseService(session)
    input_data = ExpenseCreateInput(
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2025, 1, 15),
        category="交通費",
        amount=Decimal("3000"),
        target_payout=True
    )
    expense = service.create_expense(ops_user, input_data)
    session.commit()
    
    # 承認
    result = service.approve_expense(accounting_user, expense.id)
    
    assert result.success is True
    assert result.expense.status == ExpenseStatus.APPROVED
    assert result.expense.approved_by == accounting_user.id


def test_reject_expense(session):
    """経費却下のテスト"""
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
        end_date=date(2025, 12, 31)
    )
    session.add(project)
    session.flush()
    
    # 経費作成
    service = ExpenseService(session)
    input_data = ExpenseCreateInput(
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2025, 1, 15),
        category="飲食費",
        amount=Decimal("50000"),
        description="高額",
        target_payout=True
    )
    expense = service.create_expense(ops_user, input_data)
    session.commit()
    
    # 却下
    result = service.reject_expense(accounting_user, expense.id, "金額が高すぎる")
    
    assert result.success is True
    assert result.expense.status == ExpenseStatus.REJECTED
    assert result.expense.rejection_reason == "金額が高すぎる"


def test_get_expenses_for_project_period(session):
    """プロジェクト期間の経費取得テスト"""
    # マスタデータ準備
    user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    session.add(user)
    
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
        end_date=date(2025, 12, 31)
    )
    session.add(project)
    session.flush()
    
    # 複数経費作成
    service = ExpenseService(session)
    for day in [5, 10, 15, 25]:
        input_data = ExpenseCreateInput(
            project_id=project.id,
            worker_id=worker.id,
            expense_date=date(2025, 1, day),
            category="交通費",
            amount=Decimal("1000"),
            target_payout=True
        )
        service.create_expense(user, input_data)
    
    session.commit()
    
    # 期間指定で取得
    expenses = service.get_expenses_for_project_period(
        project.id,
        date(2025, 1, 1),
        date(2025, 1, 20)
    )
    
    # 1/5, 1/10, 1/15 の3件のみ
    assert len(expenses) == 3
