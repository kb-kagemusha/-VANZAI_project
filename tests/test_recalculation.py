"""
再計算サービスのテスト
仕様参照: DESIGN_SPEC_v0.3 セクション7.4
"""
import pytest
from datetime import date, time
from decimal import Decimal
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.enums import (
    AssignmentStatus,
    ActualStatus,
    ClosingStatus,
    InvoiceStatus,
    PayoutStatus,
    ImportBatchStatus,
)
from src.models.master import Worker, Client, Site, Role
from src.models.transaction import (
    Project,
    ShiftSlot,
    Assignment,
    Actual,
    Closing,
    Invoice,
    InvoiceLine,
    Payout,
    PayoutLine,
    ImportBatch,
)
from src.services.recalculation import RecalculationService


def create_test_actual(
    db_session: Session,
    assignment: Assignment,
    project: Project,
    worker: Worker,
    role: Role,
    work_date: date,
    calc_minutes: int = 480,
    price_sales: Decimal = Decimal("1000"),
    price_outsource: Decimal = Decimal("800"),
) -> Actual:
    """テスト用のActualを作成"""
    import_batch = ImportBatch(
        file_name="test.csv",
        file_hash=generate_ulid(),  # ユニークにする
        project_id=project.id,
        period_key=work_date.strftime("%Y%m"),
        status=ImportBatchStatus.COMPLETED,
    )
    db_session.add(import_batch)
    db_session.flush()
    
    actual = Actual(
        assignment_id=assignment.id,
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        work_date=work_date,
        start_time=time(9, 0),
        end_time=time(17, 0),
        calc_minutes_total=calc_minutes,
        calc_minutes_break=0,
        calc_minutes_billable=calc_minutes,
        applied_price_sales=price_sales,
        applied_price_outsource=price_outsource,
        status=ActualStatus.ACTIVE,
        period_key=work_date.strftime("%Y%m"),
        import_batch_id=import_batch.id,
    )
    db_session.add(actual)
    db_session.flush()
    return actual


class TestRecalculationPreview:
    """再計算プレビューのテスト"""
    
    def test_preview_basic(self, db_session: Session):
        """基本的なプレビュー"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1500"),
            price_outsource=Decimal("1200"),
        )
        
        # プレビュー実行
        service = RecalculationService(db_session)
        preview = service.preview_recalculation(
            project_id=project.id,
            period_key="202601",
        )
        
        # 検証
        assert preview.target_count == 1
        assert preview.current_total_sales == Decimal("1500") * Decimal("8")  # 8時間
        assert preview.current_total_outsource == Decimal("1200") * Decimal("8")
    
    def test_preview_excludes_hard_closed(self, db_session: Session):
        """Hard Close済みは除外される"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1500"),
            price_outsource=Decimal("1200"),
        )
        
        # Hard Close
        closing = Closing(
            project_id=project.id,
            period_key="202601",
            status=ClosingStatus.HARD_CLOSED,
        )
        db_session.add(closing)
        db_session.flush()
        
        # プレビュー実行
        service = RecalculationService(db_session)
        preview = service.preview_recalculation(
            project_id=project.id,
            period_key="202601",
        )
        
        # 検証: Hard Closed なので blocked
        assert preview.target_count == 0
        assert preview.blocked_count == 1


class TestRecalculationExecution:
    """再計算実行のテスト"""
    
    def test_recalculate_basic(self, db_session: Session):
        """基本的な再計算"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1000"),  # 古い単価
            price_outsource=Decimal("800"),
        )
        
        # 再計算実行
        service = RecalculationService(db_session)
        result = service.recalculate(
            user_id="user_test",
            project_id=project.id,
            period_key="202601",
        )
        
        # 検証
        assert result.recalculated_count == 1
        assert result.skipped_count == 0
        assert result.error_count == 0
    
    def test_recalculate_skips_hard_closed(self, db_session: Session):
        """Hard Close済みはスキップ"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1000"),
            price_outsource=Decimal("800"),
        )
        
        # Hard Close
        closing = Closing(
            project_id=project.id,
            period_key="202601",
            status=ClosingStatus.HARD_CLOSED,
        )
        db_session.add(closing)
        db_session.flush()
        
        # 再計算実行
        service = RecalculationService(db_session)
        result = service.recalculate(
            user_id="user_test",
            project_id=project.id,
            period_key="202601",
        )
        
        # 検証: Hard Closed なのでスキップ
        assert result.recalculated_count == 0
        assert result.skipped_count == 1
    
    def test_recalculate_skips_issued_invoice(self, db_session: Session):
        """発行済み請求に含まれる実績はスキップ"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1000"),
            price_outsource=Decimal("800"),
        )
        
        # 発行済み請求書
        invoice = Invoice(
            client_id=client.id,
            project_id=project.id,
            period_key="202601",
            billing_date=date(2026, 2, 1),
            status=InvoiceStatus.ISSUED,
            version=1,
            subtotal=Decimal("1000"),
            tax_amount=Decimal("100"),
            total_amount=Decimal("1100"),
        )
        db_session.add(invoice)
        db_session.flush()
        
        invoice_line = InvoiceLine(
            invoice_id=invoice.id,
            line_number=1,
            description="Test",
            actual_id=actual.id,
            unit_price_snapshot=Decimal("1000"),
            quantity_snapshot=Decimal("1"),
            unit_type="hourly",
            line_amount=Decimal("1000"),
            tax_amount=Decimal("100"),
        )
        db_session.add(invoice_line)
        db_session.flush()
        
        # 再計算実行
        service = RecalculationService(db_session)
        result = service.recalculate(
            user_id="user_test",
            project_id=project.id,
            period_key="202601",
            force=False,  # 強制しない
        )
        
        # 検証: 発行済みなのでスキップ
        assert result.recalculated_count == 0
        assert result.skipped_count == 1
    
    def test_recalculate_with_force(self, db_session: Session):
        """force=True で発行済みも再計算"""
        # データ準備
        worker = Worker(name="Worker1", email="w1@example.com")
        client = Client(name="Client1")
        site = Site(name="Site1")
        role = Role(name="Role1")
        db_session.add_all([worker, client, site, role])
        db_session.flush()
        
        project = Project(
            name="Project1",
            client_id=client.id,
            site_id=site.id,
        )
        db_session.add(project)
        db_session.flush()
        
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(shift_slot)
        db_session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED,
        )
        db_session.add(assignment)
        db_session.flush()
        
        actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("1000"),
            price_outsource=Decimal("800"),
        )
        
        # 発行済み請求書
        invoice = Invoice(
            client_id=client.id,
            project_id=project.id,
            period_key="202601",
            billing_date=date(2026, 2, 1),
            status=InvoiceStatus.ISSUED,
            version=1,
            subtotal=Decimal("1000"),
            tax_amount=Decimal("100"),
            total_amount=Decimal("1100"),
        )
        db_session.add(invoice)
        db_session.flush()
        
        invoice_line = InvoiceLine(
            invoice_id=invoice.id,
            line_number=1,
            description="Test",
            actual_id=actual.id,
            unit_price_snapshot=Decimal("1000"),
            quantity_snapshot=Decimal("1"),
            unit_type="hourly",
            line_amount=Decimal("1000"),
            tax_amount=Decimal("100"),
        )
        db_session.add(invoice_line)
        db_session.flush()
        
        # 再計算実行（force=True）
        service = RecalculationService(db_session)
        result = service.recalculate(
            user_id="user_test",
            project_id=project.id,
            period_key="202601",
            force=True,  # 強制実行
        )
        
        # 検証: 強制実行で再計算される
        assert result.recalculated_count == 1
        assert result.skipped_count == 0
