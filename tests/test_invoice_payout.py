"""
Invoice/Payout生成、版管理、訂正のテスト

仕様参照:
- E5: 請求書生成・再発行・PDF化
- E6: 支払明細生成・訂正
- 11章: 請求書・支払明細の詳細仕様
"""
from datetime import date, time, datetime
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.enums import (
    ActualStatus,
    AssignmentStatus,
    ClosingStatus,
    InvoiceStatus,
    PayoutStatus,
    ImportBatchStatus,
)
from src.models.master import Client, ProjectType, Role, Site, Worker
from src.models.transaction import (
    Actual,
    Assignment,
    Closing,
    Invoice,
    InvoiceLine,
    ImportBatch,
    Payout,
    PayoutLine,
    Project,
    ShiftSlot,
)
from src.services import invoice_service, payout_service


class TestInvoiceGeneration:
    """請求書生成のテスト（E5）"""
    
    def test_generate_invoice_basic(self, db_session: Session):
        """基本的な請求書生成ができる"""
        # Arrange: マスターデータ作成
        client = Client(id=generate_ulid(), name="Test Client")
        site = Site(id=generate_ulid(), name="Test Site")
        project_type = ProjectType(id=generate_ulid(), name="警備")
        role = Role(id=generate_ulid(), name="警備員")
        worker = Worker(id=generate_ulid(), name="Worker A")
        
        db_session.add_all([client, site, project_type, role, worker])
        db_session.flush()
        
        # ImportBatch作成
        import_batch = ImportBatch(
            id=generate_ulid(),
            file_name="test_invoice.csv",
            file_hash="hash_invoice001",
            status=ImportBatchStatus.COMPLETED,
            period_key="202601",
            submitted_by="test_user",
            errors_json=None
        )
        db_session.add(import_batch)
        db_session.flush()
        
        # Project作成
        project = Project(
            id=generate_ulid(),
            name="Test Project",
            client_id=client.id,
            site_id=site.id,
            project_type_id=project_type.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db_session.add(project)
        db_session.flush()
        
        # ShiftSlot + Assignment + Actual を作成
        shift_slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project.id,
            work_date=date(2026, 1, 10),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
        )
        actual = Actual(
            id=generate_ulid(),
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2026, 1, 10),
            period_key="202601",
            start_time=time(9, 0),
            end_time=time(18, 0),
            calc_minutes_total=480,            calc_minutes_break=0,            calc_minutes_billable=480,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1200"),
            status=ActualStatus.ACTIVE.value,
        )
        db_session.add_all([shift_slot, assignment, actual])
        db_session.commit()
        
        # Act: 請求書生成
        invoice = invoice_service.generate_invoice(
            session=db_session,
            client_id=client.id,
            project_id=project.id,
            period_key="202601",
            billing_date=date(2026, 2, 1),
            user_id="test_user",
        )
        
        # Assert
        assert invoice is not None
        assert invoice.client_id == client.id
        assert invoice.project_id == project.id
        assert invoice.period_key == "202601"
        assert invoice.status == InvoiceStatus.PREPARING.value
        assert invoice.version == 1
    
    def test_reissue_invoice_creates_new_version(self, db_session: Session):
        """請求書再発行で新版が作成される（E5.2）"""
        # Arrange: 既存請求書を作成
        client = Client(id=generate_ulid(), name="Test Client")
        db_session.add(client)
        db_session.flush()
        
        original_invoice = Invoice(
            id=generate_ulid(),
            client_id=client.id,
            period_key="202601",
            billing_date=date(2026, 2, 1),
            version=1,
            status=InvoiceStatus.ISSUED.value,
            subtotal=Decimal("36000"),
            tax_amount=Decimal("3600"),
            total_amount=Decimal("39600"),
        )
        db_session.add(original_invoice)
        db_session.commit()
        
        # Act: 再発行
        new_invoice = invoice_service.reissue_invoice(
            session=db_session,
            invoice_id=original_invoice.id,
            user_id="test_user",
        )
        
        # Assert
        db_session.refresh(original_invoice)
        # 元の請求書がCLOSEDになることを確認
        assert original_invoice.status == InvoiceStatus.CLOSED.value
        
        # 新版は再発行済み
        assert new_invoice.status == InvoiceStatus.ISSUED.value


class TestPayoutGeneration:
    """支払明細生成のテスト（E6）"""
    
    def test_generate_payout_basic(self, db_session: Session):
        """基本的な支払明細生成ができる"""
        # Arrange
        worker = Worker(id=generate_ulid(), name="Worker A")
        role = Role(id=generate_ulid(), name="警備員")
        client = Client(id=generate_ulid(), name="Test Client")
        site = Site(id=generate_ulid(), name="Test Site")
        project_type = ProjectType(id=generate_ulid(), name="警備")
        project = Project(
            id=generate_ulid(),
            name="Test Project",
            client_id=client.id,
            site_id=site.id,
            project_type_id=project_type.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db_session.add_all([worker, role, client, site, project_type, project])
        db_session.flush()
        
        # ImportBatch作成
        import_batch = ImportBatch(
            id=generate_ulid(),
            file_name="test_payout.csv",
            file_hash="hash_payout001",
            status=ImportBatchStatus.COMPLETED,
            period_key="202601",
            submitted_by="test_user",
            errors_json=None
        )
        db_session.add(import_batch)
        db_session.flush()
        
        # Actual作成
        shift_slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project.id,
            work_date=date(2026, 1, 10),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
        )
        actual = Actual(
            id=generate_ulid(),
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2026, 1, 10),
            period_key="202601",
            start_time=time(9, 0),
            end_time=time(18, 0),
            calc_minutes_total=480,
            calc_minutes_break=0,
            calc_minutes_billable=480,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1200"),
            status=ActualStatus.ACTIVE.value,
        )
        db_session.add_all([shift_slot, assignment, actual])
        db_session.commit()
        
        # Act: 支払明細生成
        payout = payout_service.generate_payout(
            session=db_session,
            worker_id=worker.id,
            project_id=project.id,
            period_key="202601",
            payment_date=date(2026, 2, 10),
            user_id="test_user",
        )
        
        # Assert
        assert payout is not None
        assert payout.worker_id == worker.id
        assert payout.period_key == "202601"
        assert payout.status == PayoutStatus.PREPARING.value
        assert payout.version == 1
    
    def test_correct_payout_creates_new_version(self, db_session: Session):
        """支払明細訂正で新版が作成される（E6.2）"""
        # Arrange: 既存支払明細
        worker = Worker(id=generate_ulid(), name="Worker A")
        db_session.add(worker)
        db_session.flush()
        
        original_payout = Payout(
            id=generate_ulid(),
            worker_id=worker.id,
            period_key="202601",
            payment_date=date(2026, 2, 10),
            version=1,
            status=PayoutStatus.APPROVED.value,
            total_amount=Decimal("19200"),
        )
        db_session.add(original_payout)
        db_session.commit()
        
        # Act: 訂正
        correction_lines = [{"description": "時間修正", "line_amount": Decimal("1000")}]
        new_payout = payout_service.correct_payout(
            session=db_session,
            original_payout_id=original_payout.id,
            correction_lines=correction_lines,
            user_id="test_user",
        )
        
        # Assert
        db_session.refresh(original_payout)
        # 元の支払明細がCLOSEDになることを確認
        assert original_payout.status == PayoutStatus.CLOSED.value
        
        # 新版はversion=2でparent_payout_idが設定される
        assert new_payout.version == 2
        assert new_payout.parent_payout_id == original_payout.id
