"""集計サービスのテスト (aggregation.py)

DESIGN_SPEC_v0.3 セクション13章: 実績集計（予定/確定の差分、粗利計算）
"""
import pytest
from datetime import date, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.master import Client, Role, ProjectType, PriceSales, PriceOutsource
from src.models.transaction import Project, ShiftSlot, Assignment, Actual
from src.models.enums import AssignmentStatus, ActualStatus
from src.services.aggregation import (
    aggregate_by_period,
    aggregate_by_project,
    aggregate_by_client,
)


@pytest.fixture
def aggregation_test_data(session: Session):
    """集計テスト用データ作成"""
    # クライアント
    client1 = Client(code="C001", name="クライアントA")
    client2 = Client(code="C002", name="クライアントB")
    session.add_all([client1, client2])
    
    # 役割
    role = Role(code="R001", name="警備員")
    session.add(role)
    
    # プロジェクトタイプ
    project_type = ProjectType(code="PT001", name="警備")
    session.add(project_type)
    
    session.flush()
    
    # プロジェクト
    project1 = Project(
        code="P001",
        name="案件A",
        client_id=client1.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    project2 = Project(
        code="P002",
        name="案件B",
        client_id=client2.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    session.add_all([project1, project2])
    session.flush()
    
    # 単価設定（案件A）
    price_sales1 = PriceSales(
        project_id=project1.id,
        role_id=role.id,
        unit_price=Decimal("1500.00"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    price_outsource1 = PriceOutsource(
        project_id=project1.id,
        role_id=role.id,
        unit_price=Decimal("1000.00"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    
    # 単価設定（案件B）
    price_sales2 = PriceSales(
        project_id=project2.id,
        role_id=role.id,
        unit_price=Decimal("2000.00"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    price_outsource2 = PriceOutsource(
        project_id=project2.id,
        role_id=role.id,
        unit_price=Decimal("1200.00"),
        unit_type="hourly",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    session.add_all([price_sales1, price_outsource1, price_sales2, price_outsource2])
    session.flush()
    
    # シフトスロット
    shift_slot1 = ShiftSlot(
        project_id=project1.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        required_count=1,
    )
    shift_slot2 = ShiftSlot(
        project_id=project2.id,
        work_date=date(2026, 1, 16),
        start_time=time(9, 0),
        end_time=time(18, 0),
        required_count=1,
    )
    session.add_all([shift_slot1, shift_slot2])
    session.flush()
    
    # ImportBatch（Actualで必須）
    from src.models.transaction import ImportBatch
    from src.models.enums import ImportMode
    import_batch = ImportBatch(
        file_name="test.csv",
        file_hash="test_hash",
        period_key="202601",
        mode=ImportMode.APPEND.value,
    )
    session.add(import_batch)
    session.flush()
    
    return {
        "client1": client1,
        "client2": client2,
        "role": role,
        "project1": project1,
        "project2": project2,
        "shift_slot1": shift_slot1,
        "shift_slot2": shift_slot2,
        "import_batch": import_batch,
    }


class TestAggregateByPeriod:
    """期間別集計のテスト"""
    
    def test_aggregate_planned_only(self, session: Session, aggregation_test_data):
        """予定のみ（実績なし）の集計"""
        # アサインメント作成（8時間 = 480分）
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 予定: 9時間 × 1500円/時 = 13500円
        assert result.planned_hours == Decimal("9")
        assert result.planned_sales == Decimal("13500.00")
        assert result.planned_cost == Decimal("9000.00")
        assert result.planned_profit == Decimal("4500.00")
        assert result.planned_profit_rate == Decimal("33.33")  # 4500/13500*100
        
        # 確定なし
        assert result.confirmed_hours == Decimal("0")
        assert result.confirmed_sales == Decimal("0")
        assert result.confirmed_cost == Decimal("0")
        
        # 差分 = -予定
        assert result.delta_hours == Decimal("-9")
        assert result.delta_sales == Decimal("-13500.00")
    
    def test_aggregate_confirmed_only(self, session: Session, aggregation_test_data):
        """確定のみ（予定なし削除後）の集計"""
        # アサインメント
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CANCELED,  # キャンセル済み

        )
        session.add(assignment)
        session.flush()
        
        # 実績作成（7時間 = 420分）
        actual = Actual(
            project_id=aggregation_test_data["project1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,
            assignment_id=assignment.id,
            work_date=date(2026, 1, 15),
            period_key="202601",
            import_batch_id=aggregation_test_data["import_batch"].id,
            start_time=time(9, 0),
            end_time=time(16, 0),
            calc_minutes_total=420,
            calc_minutes_break=0,
            calc_minutes_billable=420,
            
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1000"),
            status=ActualStatus.ACTIVE,
        )
        session.add(actual)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 予定なし（canceled除外）
        assert result.planned_hours == Decimal("0")
        assert result.planned_sales == Decimal("0")
        
        # 確定: 7時間 × 1500円/時 = 10500円
        assert result.confirmed_hours == Decimal("7.00")
        assert result.confirmed_sales == Decimal("10500.00")
        assert result.confirmed_cost == Decimal("7000.00")
        assert result.confirmed_profit == Decimal("3500.00")
        
        # 差分 = +確定
        assert result.delta_hours == Decimal("7.00")
        assert result.delta_sales == Decimal("10500.00")
    
    def test_aggregate_planned_vs_confirmed(self, session: Session, aggregation_test_data):
        """予定と確定の差分計算"""
        # アサインメント（予定8時間）
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        # 実績（確定7時間）
        actual = Actual(
            project_id=aggregation_test_data["project1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,
            assignment_id=assignment.id,
            work_date=date(2026, 1, 15),
            period_key="202601",
            import_batch_id=aggregation_test_data["import_batch"].id,
            start_time=time(9, 0),
            end_time=time(16, 0),
            calc_minutes_total=420,
            calc_minutes_break=0,
            calc_minutes_billable=420,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1000"),
            status=ActualStatus.ACTIVE,
        )
        session.add(actual)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 予定: 9時間 × 1500円/時 = 13500円
        assert result.planned_hours == Decimal("9")
        assert result.planned_sales == Decimal("13500.00")
        
        # 確定: 7時間 × 1500円/時 = 10500円
        assert result.confirmed_hours == Decimal("7.00")
        assert result.confirmed_sales == Decimal("10500.00")
        
        # 差分: -2時間，-3000円
        assert result.delta_hours == Decimal("-2.00")
        assert result.delta_sales == Decimal("-3000.00")
        assert result.delta_cost == Decimal("-2000.00")
        assert result.delta_profit == Decimal("-1000.00")
    
    def test_aggregate_canceled_assignment_excluded(self, session: Session, aggregation_test_data):
        """キャンセル済みアサインメントは予定から除外される"""
        # 通常アサインメント
        assignment1 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        # キャンセル済みアサインメント
        assignment2 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W002",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CANCELED,

        )
        session.add_all([assignment1, assignment2])
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # キャンセル除外 → 予定は1件のみ（9時間 × 1500円/時 = 13500円）
        assert result.planned_hours == Decimal("9")
        assert result.planned_sales == Decimal("13500.00")
    
    def test_aggregate_invalid_actual_excluded(self, session: Session, aggregation_test_data):
        """invalid実績は確定から除外される"""
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        # 有効実績
        actual1 = Actual(
            project_id=aggregation_test_data["project1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,
            assignment_id=assignment.id,
            work_date=date(2026, 1, 15),
            period_key="202601",
            import_batch_id=aggregation_test_data["import_batch"].id,
            calc_minutes_total=420,
            calc_minutes_break=0,
            calc_minutes_billable=420,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1000"),
            status=ActualStatus.ACTIVE,
        )
        # 無効実績
        actual2 = Actual(
            project_id=aggregation_test_data["project1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,
            assignment_id=assignment.id,
            work_date=date(2026, 1, 16),
            period_key="202601",
            import_batch_id=aggregation_test_data["import_batch"].id,
            calc_minutes_total=480,
            calc_minutes_break=0,
            calc_minutes_billable=480,
            applied_price_sales=Decimal("1500"),
            applied_price_outsource=Decimal("1000"),
            status=ActualStatus.INVALID,
        )
        session.add_all([actual1, actual2])
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 無効除外 → 確定は1件のみ（7時間 × 1500円/時 = 10500円）
        assert result.confirmed_hours == Decimal("7.00")
        assert result.confirmed_sales == Decimal("10500.00")
    
    def test_aggregate_by_project_filter(self, session: Session, aggregation_test_data):
        """プロジェクト指定で絞り込み"""
        # 案件A
        assignment1 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        # 案件B
        assignment2 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot2"].id,
            worker_id="W002",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add_all([assignment1, assignment2])
        session.flush()
        
        # 案件A のみ集計
        result = aggregate_by_period(
            session, "202601", project_id=aggregation_test_data["project1"].id
        )
        
        assert result.project_id == aggregation_test_data["project1"].id
        assert result.project_name == "案件A"
        assert result.planned_hours == Decimal("9")
        assert result.planned_sales == Decimal("13500.00")
    
    def test_aggregate_zero_division_profit_rate(self, session: Session, aggregation_test_data):
        """売上ゼロ時の粗利率はNone"""
        # 別の役割（単価設定なし）を作成
        role_no_price = Role(code="R999", name="単価なし役割")
        session.add(role_no_price)
        session.flush()
        
        # 単価なしのアサインメント
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=role_no_price.id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 単価がないため売上ゼロ
        assert result.planned_sales == Decimal("0")
        assert result.planned_profit_rate is None  # 0除算回避


class TestAggregateByProject:
    """案件別集計のテスト"""
    
    def test_aggregate_multiple_projects(self, session: Session, aggregation_test_data):
        """複数案件の個別集計"""
        # 案件A
        assignment1 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        # 案件B
        assignment2 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot2"].id,
            worker_id="W002",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add_all([assignment1, assignment2])
        session.flush()
        
        results = aggregate_by_project(session, "202601")
        
        assert len(results) == 2
        
        # 案件A: 9時間 × 1500円/時 = 13500円
        project1_result = [r for r in results if r.project_id == aggregation_test_data["project1"].id][0]
        assert project1_result.planned_sales == Decimal("13500.00")
        assert project1_result.planned_profit == Decimal("4500.00")
        
        # 案件B: 9時間 × 2000円/時 = 18000円
        project2_result = [r for r in results if r.project_id == aggregation_test_data["project2"].id][0]
        assert project2_result.planned_sales == Decimal("18000.00")
        assert project2_result.planned_profit == Decimal("7200.00")


class TestAggregateByClient:
    """クライアント別集計のテスト"""
    
    def test_aggregate_multiple_clients(self, session: Session, aggregation_test_data):
        """複数クライアントの個別集計"""
        # クライアントA（案件A）
        assignment1 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        # クライアントB（案件B）
        assignment2 = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot2"].id,
            worker_id="W002",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add_all([assignment1, assignment2])
        session.flush()
        
        results = aggregate_by_client(session, "202601")
        
        assert len(results) == 2
        
        # クライアントA: 9時間 × 1500円/時 = 13500円
        client1_result = [r for r in results if r.client_id == aggregation_test_data["client1"].id][0]
        assert client1_result.client_name == "クライアントA"
        assert client1_result.planned_sales == Decimal("13500.00")
        
        # クライアントB: 9時間 × 2000円/時 = 18000円
        client2_result = [r for r in results if r.client_id == aggregation_test_data["client2"].id][0]
        assert client2_result.client_name == "クライアントB"
        assert client2_result.planned_sales == Decimal("18000.00")


class TestAggregationPrecision:
    """Decimal精度のテスト"""
    
    def test_decimal_precision_maintained(self, session: Session, aggregation_test_data):
        """Decimal精度が維持されること"""
        # 3.5時間（210分）のShiftSlotを作成：9:00-12:30
        shift_slot_3_5h = ShiftSlot(
            project_id=aggregation_test_data["project1"].id,
            work_date=date(2026, 1, 17),
            start_time=time(9, 0),
            end_time=time(12, 30),
            required_count=1,
        )
        session.add(shift_slot_3_5h)
        session.flush()
        
        # 3.5時間のアサインメント
        assignment = Assignment(
            shift_slot_id=shift_slot_3_5h.id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 3.5時間（正確に維持）
        assert result.planned_hours == Decimal("3.50")
        # 3.5 × 1500円/時 = 5250円
        assert result.planned_sales == Decimal("5250.00")
    
    def test_profit_rate_rounding(self, session: Session, aggregation_test_data):
        """粗利率の小数点丸め"""
        assignment = Assignment(
            shift_slot_id=aggregation_test_data["shift_slot1"].id,
            worker_id="W001",
            role_id=aggregation_test_data["role"].id,


            status=AssignmentStatus.CONFIRMED,

        )
        session.add(assignment)
        session.flush()
        
        result = aggregate_by_period(session, "202601")
        
        # 粗利率: 4500 / 13500 * 100 = 33.333...
        assert result.planned_profit_rate == Decimal("33.33")
