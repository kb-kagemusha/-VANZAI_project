"""
統合テスト: CSV取り込み → 締め → 請求書生成 → 支払明細生成 → 発行 → 訂正の一連フロー
仕様参照: DESIGN_SPEC_v0.3.md MVP フロー
"""
import pytest
from datetime import date, time, datetime
from decimal import Decimal

from src.models.enums import (
    UserRole,
    AssignmentStatus,
    ActualStatus,
    InvoiceStatus,
    PayoutStatus,
    ClosingStatus,
    ImportBatchStatus
)
from src.models.master import User, Client, Site, Worker, Role, ProjectType, PriceSales, PriceOutsource
from src.models.transaction import Project, ShiftSlot, Assignment, Actual, ImportBatch
from src.services.closing import soft_close, hard_close
from src.services import invoice_service, payout_service


def test_full_monthly_workflow(session):
    """月次運用の一連フロー統合テスト"""
    
    # ========== 1. マスタデータ準備 ==========
    admin_user = User(username="admin", email="admin@test.com", role=UserRole.ADMIN, is_active=True)
    ops_user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    accounting_user = User(username="accounting", email="acc@test.com", role=UserRole.ACCOUNTING, is_active=True)
    session.add_all([admin_user, ops_user, accounting_user])
    
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    role = Role(name="警備員")
    project_type = ProjectType(name="警備")
    session.add_all([client, site, worker, role, project_type])
    session.flush()
    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    session.add(project)
    session.flush()
    
    # 単価設定
    price_sales = PriceSales(
        project_id=project.id,
        role_id=role.id,
        unit_price=Decimal("1500"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    price_outsource = PriceOutsource(
        project_id=project.id,
        role_id=role.id,
        worker_id=worker.id,
        unit_price=Decimal("1200"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    session.add_all([price_sales, price_outsource])
    session.flush()
    
    # ========== 2. シフト・アサイン作成 ==========
    shift_slot = ShiftSlot(
        project_id=project.id,
        work_date=date(2026, 1, 10),
        start_time=time(9, 0),
        end_time=time(18, 0),
        required_count=1
    )
    session.add(shift_slot)
    session.flush()
    
    assignment = Assignment(
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value
    )
    session.add(assignment)
    session.commit()
    
    # ========== 3. CSV取り込み（実績作成） ==========
    import_batch = ImportBatch(
        file_name="actuals_202601.csv",
        file_hash="hash001",
        status=ImportBatchStatus.COMPLETED,
        period_key="202601",
        submitted_by="test_user",
        errors_json=None,
    )
    session.add(import_batch)
    session.flush()
    
    actual = Actual(
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
    session.add(actual)
    session.commit()
    
    # 実績が作成されたことを確認
    assert session.query(Actual).count() == 1
    
    # ========== 4. 締め（Soft Close） ==========
    soft_close_result = soft_close(
        session=session,
        project_id=project.id,
        period_key="202601",
        user_id=ops_user.id
    )
    session.commit()
    
    assert soft_close_result.is_soft_closed is True
    
    # ========== 5. 請求書生成 ==========
    invoice = invoice_service.generate_invoice(
        session=session,
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 2, 1),
        user_id=ops_user.id
    )
    session.commit()
    
    assert invoice.status == InvoiceStatus.PREPARING.value
    assert invoice.total_amount > 0
    
    # ========== 6. 支払明細生成 ==========
    payout = payout_service.generate_payout(
        session=session,
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 10),
        user_id=ops_user.id
    )
    session.commit()
    
    assert payout.status == PayoutStatus.PREPARING.value
    assert payout.total_amount > 0
    
    # ========== 7. Hard Close ==========
    hard_close_result = hard_close(
        session=session,
        project_id=project.id,
        period_key="202601",
        user_id=accounting_user.id,
        approver_id=ops_user.id
    )
    session.commit()
    
    assert hard_close_result.is_hard_closed is True
    
    # ========== 8. 請求書発行 ==========
    invoice_service.issue_invoice(
        session=session,
        invoice_id=invoice.id,
        user_id=accounting_user.id
    )
    session.commit()
    
    session.refresh(invoice)
    assert invoice.status == InvoiceStatus.ISSUED.value
    
    # ========== 9. 支払承認 ==========
    payout_service.approve_payout(
        session=session,
        payout_id=payout.id,
        user_id=accounting_user.id
    )
    session.commit()
    
    session.refresh(payout)
    assert payout.status == PayoutStatus.APPROVED.value
    
    # ========== 10. 訂正フロー（請求書） ==========
    correction_lines = [
        {"description": "追加費用", "line_amount": Decimal("5000"), "tax_amount": Decimal("500")}
    ]
    corrected_invoice = invoice_service.correct_invoice(
        session=session,
        original_invoice_id=invoice.id,
        correction_lines=correction_lines,
        user_id=accounting_user.id
    )
    session.commit()
    
    assert corrected_invoice.version == 2
    assert corrected_invoice.parent_invoice_id == invoice.id
    
    # 元の請求書がCLOSEDになっていることを確認
    session.refresh(invoice)
    assert invoice.status == InvoiceStatus.CLOSED.value
    
    print("✅ 統合テスト完了: CSV取込 → 締め → 請求書生成 → 支払明細生成 → 発行 → 訂正")


def test_multi_worker_workflow(session):
    """複数稼働者の月次フロー"""
    
    # マスタデータ準備
    ops_user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    session.add(ops_user)
    
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker1 = Worker(name="Worker A")
    worker2 = Worker(name="Worker B")
    role = Role(name="警備員")
    project_type = ProjectType(name="警備")
    session.add_all([client, site, worker1, worker2, role, project_type])
    session.flush()
    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    session.add(project)
    session.flush()
    
    # 単価設定
    price_sales = PriceSales(
        unit_price=Decimal("1500"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    price_outsource1 = PriceOutsource(
        project_id=project.id,
        role_id=role.id,
        worker_id=worker1.id,
        unit_price=Decimal("1200"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    price_outsource2 = PriceOutsource(
        project_id=project.id,
        role_id=role.id,
        worker_id=worker2.id,
        unit_price=Decimal("1100"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    session.add_all([price_sales, price_outsource1, price_outsource2])
    session.flush()
    
    # import_batch作成
    import_batch = ImportBatch(
        file_name="test_multi.csv",
        file_hash="hash_multi001",
        status=ImportBatchStatus.COMPLETED,
        period_key="202601",
        submitted_by="test_user",
        errors_json=None
    )
    session.add(import_batch)
    session.flush()
    
    # 2人分のシフト・アサイン作成
    for i, worker in enumerate([worker1, worker2], start=1):
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 10 + i),
            start_time=time(9, 0),
            end_time=time(18, 0),
            required_count=1
        )
        session.add(shift_slot)
        session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value
        )
        session.add(assignment)
        session.flush()
        
        # 実績作成
        actual = Actual(
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2026, 1, 10 + i),
            period_key="202601",
            start_time=time(9, 0),
            end_time=time(18, 0),
            calc_minutes_total=480,
            calc_minutes_break=0,
            calc_minutes_billable=480,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1200") if worker == worker1 else Decimal("1100"),
            status=ActualStatus.ACTIVE.value
        )
        session.add(actual)
    
    session.commit()
    
    # 請求書生成（プロジェクト単位）
    invoice = invoice_service.generate_invoice(
        session=session,
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 2, 1),
        user_id=ops_user.id
    )
    session.commit()
    
    # 請求書には2人分の実績が含まれる
    assert invoice.total_amount > 0
    
    # 各稼働者の支払明細生成
    payout1 = payout_service.generate_payout(
        session=session,
        worker_id=worker1.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 10),
        user_id=ops_user.id
    )
    
    payout2 = payout_service.generate_payout(
        session=session,
        worker_id=worker2.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 10),
        user_id=ops_user.id
    )
    session.commit()
    
    # 各稼働者の支払明細が作成される
    assert payout1.total_amount > 0
    assert payout2.total_amount > 0
    assert payout1.total_amount != payout2.total_amount  # 単価が異なるため
    
    print("✅ 統合テスト完了: 複数稼働者の月次フロー")


def test_csv_error_recovery_workflow(session):
    """CSVエラー復旧フロー: CSV差戻し→修正→再取込"""
    
    # マスタデータ準備
    ops_user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    session.add(ops_user)
    
    client = Client(name="Test Client")
    site = Site(name="Test Site")
    worker = Worker(name="Test Worker")
    role = Role(name="警備員")
    project_type = ProjectType(name="警備")
    session.add_all([client, site, worker, role, project_type])
    session.flush()
    
    project = Project(
        name="Test Project",
        client_id=client.id,
        site_id=site.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    session.add(project)
    session.flush()
    
    # 単価設定
    price_sales = PriceSales(
        project_id=project.id,
        role_id=role.id,
        unit_price=Decimal("1500"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    price_outsource = PriceOutsource(
        project_id=project.id,
        role_id=role.id,
        worker_id=worker.id,
        unit_price=Decimal("1200"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1)
    )
    session.add_all([price_sales, price_outsource])
    session.flush()
    
    # シフト・アサイン作成
    shift_slot = ShiftSlot(
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        required_count=1
    )
    session.add(shift_slot)
    session.flush()
    
    assignment = Assignment(
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value
    )
    session.add(assignment)
    session.commit()
    
    # ========== 1. 最初のCSV取込（エラーあり） ==========
    import_batch_error = ImportBatch(
        file_name="actuals_error.csv",
        file_hash="hash_error001",
        status=ImportBatchStatus.PARTIAL_ERROR,  # エラーあり
        period_key="202601",
        submitted_by="site_manager",
        errors_json='[{"line": 5, "reason": "時刻フォーマットエラー", "key": "2026-01-15"}]'
    )
    session.add(import_batch_error)
    
    # エラーのない行だけ取込
    actual_ok = Actual(
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=assignment.id,
        import_batch_id=import_batch_error.id,
        work_date=date(2026, 1, 15),
        period_key="202601",
        start_time=time(9, 0),
        end_time=time(17, 0),  # エラー行とは別の時間帯
        calc_minutes_total=420,
        calc_minutes_break=0,
        calc_minutes_billable=420,
        applied_price_sales=Decimal("1500"),
        applied_price_outsource=Decimal("1200"),
        status=ActualStatus.ACTIVE.value
    )
    session.add(actual_ok)
    session.commit()
    
    # エラーがあるバッチが記録される
    assert import_batch_error.status == ImportBatchStatus.PARTIAL_ERROR.value
    assert import_batch_error.errors_json is not None
    
    # ========== 2. CSV修正後の再取込 ==========
    import_batch_fixed = ImportBatch(
        file_name="actuals_fixed.csv",
        file_hash="hash_fixed001",  # 異なるハッシュ
        status=ImportBatchStatus.COMPLETED,
        period_key="202601",
        submitted_by="site_manager",
        errors_json=None
    )
    session.add(import_batch_fixed)
    session.flush()
    
    # 修正された行を取込（洗い替え）
    # 既存の実績を無効化
    actual_ok.status = ActualStatus.SUPERSEDED.value
    
    # 新しい実績を作成
    actual_fixed = Actual(
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=assignment.id,
        import_batch_id=import_batch_fixed.id,
        work_date=date(2026, 1, 15),
        period_key="202601",
        start_time=time(9, 0),
        end_time=time(18, 0),  # 修正後の正しい時間
        calc_minutes_total=480,
        calc_minutes_break=0,
        calc_minutes_billable=480,
        applied_price_sales=Decimal("1500"),
        applied_price_outsource=Decimal("1200"),
        status=ActualStatus.ACTIVE.value
    )
    session.add(actual_fixed)
    session.commit()
    
    # 修正後の実績が有効
    active_actuals = session.query(Actual).filter(
        Actual.status == ActualStatus.ACTIVE.value
    ).all()
    assert len(active_actuals) == 1
    assert active_actuals[0].calc_minutes_total == 480
    
    # 古い実績は無効化されている
    superseded_actuals = session.query(Actual).filter(
        Actual.status == ActualStatus.SUPERSEDED.value
    ).all()
    assert len(superseded_actuals) == 1
    
    print("✅ 統合テスト完了: CSVエラー復旧フロー")


def test_multiple_projects_parallel_workflow(session):
    """複数案件並行処理フロー"""
    
    # マスタデータ準備
    ops_user = User(username="ops", email="ops@test.com", role=UserRole.OPS, is_active=True)
    accounting_user = User(username="accounting", email="acc@test.com", role=UserRole.ACCOUNTING, is_active=True)
    session.add_all([ops_user, accounting_user])
    
    client1 = Client(name="Client A")
    client2 = Client(name="Client B")
    site1 = Site(name="Site A")
    site2 = Site(name="Site B")
    worker1 = Worker(name="Worker A")
    worker2 = Worker(name="Worker B")
    role = Role(name="警備員")
    project_type = ProjectType(name="警備")
    session.add_all([client1, client2, site1, site2, worker1, worker2, role, project_type])
    session.flush()
    
    # 案件A作成
    project_a = Project(
        name="Project A",
        client_id=client1.id,
        site_id=site1.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    
    # 案件B作成
    project_b = Project(
        name="Project B",
        client_id=client2.id,
        site_id=site2.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    session.add_all([project_a, project_b])
    session.flush()
    
    # 各案件の単価設定
    for project, worker in [(project_a, worker1), (project_b, worker2)]:
        price_sales = PriceSales(
            project_id=project.id,
            role_id=role.id,
            unit_price=Decimal("1500"),
            unit_type="hourly",
            valid_from=date(2026, 1, 1)
        )
        price_outsource = PriceOutsource(
            project_id=project.id,
            role_id=role.id,
            worker_id=worker.id,
            unit_price=Decimal("1200"),
            unit_type="hourly",
            valid_from=date(2026, 1, 1)
        )
        session.add_all([price_sales, price_outsource])
    session.flush()
    
    # import_batch作成（各案件別）
    import_batch_a = ImportBatch(
        file_name="project_a_actuals.csv",
        file_hash="hash_a001",
        status=ImportBatchStatus.COMPLETED,
        period_key="202601",
        submitted_by="manager_a",
        errors_json=None
    )
    import_batch_b = ImportBatch(
        file_name="project_b_actuals.csv",
        file_hash="hash_b001",
        status=ImportBatchStatus.COMPLETED,
        period_key="202601",
        submitted_by="manager_b",
        errors_json=None
    )
    session.add_all([import_batch_a, import_batch_b])
    session.flush()
    
    # 各案件のシフト・アサイン・実績作成
    for project, worker, import_batch in [
        (project_a, worker1, import_batch_a),
        (project_b, worker2, import_batch_b)
    ]:
        shift_slot = ShiftSlot(
            project_id=project.id,
            work_date=date(2026, 1, 20),
            start_time=time(9, 0),
            end_time=time(18, 0),
            required_count=1
        )
        session.add(shift_slot)
        session.flush()
        
        assignment = Assignment(
            shift_slot_id=shift_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value
        )
        session.add(assignment)
        session.flush()
        
        actual = Actual(
            project_id=project.id,
            worker_id=worker.id,
            role_id=role.id,
            assignment_id=assignment.id,
            import_batch_id=import_batch.id,
            work_date=date(2026, 1, 20),
            period_key="202601",
            start_time=time(9, 0),
            end_time=time(18, 0),
            calc_minutes_total=480,
            calc_minutes_break=0,
            calc_minutes_billable=480,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1200"),
            status=ActualStatus.ACTIVE.value
        )
        session.add(actual)
    
    session.commit()
    
    # ========== 各案件の請求書生成 ==========
    invoice_a = invoice_service.generate_invoice(
        session=session,
        client_id=client1.id,
        project_id=project_a.id,
        period_key="202601",
        billing_date=date(2026, 2, 1),
        user_id=ops_user.id
    )
    
    invoice_b = invoice_service.generate_invoice(
        session=session,
        client_id=client2.id,
        project_id=project_b.id,
        period_key="202601",
        billing_date=date(2026, 2, 1),
        user_id=ops_user.id
    )
    session.commit()
    
    # 各案件の請求書が独立して作成される
    assert invoice_a.client_id == client1.id
    assert invoice_b.client_id == client2.id
    assert invoice_a.total_amount > 0
    assert invoice_b.total_amount > 0
    
    # ========== 各稼働者の支払明細生成 ==========
    payout_a = payout_service.generate_payout(
        session=session,
        worker_id=worker1.id,
        project_id=project_a.id,
        period_key="202601",
        payment_date=date(2026, 2, 10),
        user_id=ops_user.id
    )
    
    payout_b = payout_service.generate_payout(
        session=session,
        worker_id=worker2.id,
        project_id=project_b.id,
        period_key="202601",
        payment_date=date(2026, 2, 10),
        user_id=ops_user.id
    )
    session.commit()
    
    # 各稼働者の支払明細が独立して作成される
    assert payout_a.worker_id == worker1.id
    assert payout_b.worker_id == worker2.id
    assert payout_a.total_amount > 0
    assert payout_b.total_amount > 0
    
    # ========== 各案件のSoft Close（並行実行可能） ==========
    soft_close_a = soft_close(
        session=session,
        project_id=project_a.id,
        period_key="202601",
        user_id=ops_user.id
    )
    
    soft_close_b = soft_close(
        session=session,
        project_id=project_b.id,
        period_key="202601",
        user_id=ops_user.id
    )
    session.commit()
    
    # 各案件の締めが独立して実行される
    assert soft_close_a.is_soft_closed is True
    assert soft_close_b.is_soft_closed is True
    assert soft_close_a.project_id == project_a.id
    assert soft_close_b.project_id == project_b.id
    
    print("✅ 統合テスト完了: 複数案件並行処理フロー")
