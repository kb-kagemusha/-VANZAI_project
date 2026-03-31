"""単価解決サービスのテスト (price_resolver.py)

DESIGN_SPEC_v0.3 セクション7.2: 単価解決の優先順位とエッジケース
"""
import pytest
from datetime import date, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.master import Client, Role, ProjectType, PriceSales, PriceOutsource, PriceRule
from src.models.transaction import ShiftSlot, Assignment, Project
from src.models.enums import AssignmentStatus
from src.services.price_resolver import (
    resolve_sales_price,
    resolve_outsource_price,
)


@pytest.fixture
def minimal_data(session: Session):
    """最小限のテストデータを作成"""
    # クライアント
    client = Client(code="C001", name="クライアントA")
    session.add(client)
    
    # 役割
    role = Role(code="R001", name="警備員")
    session.add(role)
    
    # プロジェクトタイプ
    project_type = ProjectType(code="PT001", name="警備")
    session.add(project_type)
    
    session.flush()
    
    # プロジェクト
    project = Project(
        code="P001",
        name="本社警備案件",
        client_id=client.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    session.add(project)
    session.flush()
    
    # シフトスロット
    shift_slot = ShiftSlot(
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        required_count=1,
    )
    session.add(shift_slot)
    session.flush()
    
    # アサインメント
    assignment = Assignment(
        shift_slot_id=shift_slot.id,
        worker_id="W001",
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED,
    )
    session.add(assignment)
    session.flush()
    
    return {
        "client": client,
        "role": role,
        "project_type": project_type,
        "project": project,
        "shift_slot": shift_slot,
        "assignment": assignment,
    }


class TestResolveSalesPrice:
    """売上単価解決のテスト"""
    
    def test_locked_price_has_highest_priority(self, session: Session, minimal_data):
        """locked_price_sales が最優先されること"""
        assignment = minimal_data["assignment"]
        assignment.locked_price_sales = Decimal("15000.00")
        
        # プロジェクト単価も設定
        price_sales = PriceSales(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("12000.00"),
            unit_type="daily",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        session.add(price_sales)
        session.flush()
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result == Decimal("15000.00")
    
    def test_project_price_second_priority(self, session: Session, minimal_data):
        """プロジェクト単価が2番目の優先度であること"""
        assignment = minimal_data["assignment"]
        
        # プロジェクト単価を設定
        price_sales = PriceSales(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("12000.00"),
            unit_type="daily",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        session.add(price_sales)
        session.flush()
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result == Decimal("12000.00")
    
    def test_no_price_found_returns_none(self, session: Session, minimal_data):
        """単価が見つからない場合はNoneを返すこと"""
        assignment = minimal_data["assignment"]
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result is None
    
    def test_price_valid_from_boundary(self, session: Session, minimal_data):
        """valid_fromの境界値でも解決できること"""
        assignment = minimal_data["assignment"]
        
        price_sales = PriceSales(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("12000.00"),
            unit_type="daily",
            valid_from=date(2026, 1, 15),  # 境界値
            valid_to=date(2026, 12, 31),
        )
        session.add(price_sales)
        session.flush()
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result == Decimal("12000.00")
    
    def test_price_valid_to_boundary(self, session: Session, minimal_data):
        """valid_toの境界値でも解決できること"""
        assignment = minimal_data["assignment"]
        
        price_sales = PriceSales(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("12000.00"),
            unit_type="daily",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 1, 15),  # 境界値
        )
        session.add(price_sales)
        session.flush()
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result == Decimal("12000.00")
    
    def test_price_outside_valid_range(self, session: Session, minimal_data):
        """有効期間外の単価は無視されること"""
        assignment = minimal_data["assignment"]
        
        price_sales = PriceSales(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("12000.00"),
            unit_type="daily",
            valid_from=date(2026, 2, 1),
            valid_to=date(2026, 12, 31),
        )
        session.add(price_sales)
        session.flush()
        
        result = resolve_sales_price(session, assignment, date(2026, 1, 15))
        assert result is None


class TestResolveOutsourcePrice:
    """外注単価解決のテスト"""
    
    def test_locked_price_has_highest_priority(self, session: Session, minimal_data):
        """locked_price_outsource が最優先されること"""
        assignment = minimal_data["assignment"]
        assignment.locked_price_outsource = Decimal("8000.00")
        
        # プロジェクト単価も設定
        price_outsource = PriceOutsource(
            project_id=minimal_data["project"].id,
            role_id=minimal_data["role"].id,
            unit_price=Decimal("7000.00"),
            unit_type="daily",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        session.add(price_outsource)
        session.flush()
        
        result = resolve_outsource_price(session, assignment, date(2026, 1, 15))
        assert result == Decimal("8000.00")
    
    def test_no_price_found_returns_none(self, session: Session, minimal_data):
        """外注単価が見つからない場合はNoneを返すこと"""
        assignment = minimal_data["assignment"]
        
        result = resolve_outsource_price(session, assignment, date(2026, 1, 15))
        assert result is None

