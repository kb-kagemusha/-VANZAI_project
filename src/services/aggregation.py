"""集計サービス (DESIGN_SPEC_v0.3 セクション13章)

予定/確定集計:
- 予定: Assignment (status != canceled)
- 確定: Actual (status = valid)
- 売上 / 外注 / 粗利
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.enums import ActualStatus, AssignmentStatus
from src.models.transaction import Actual, Assignment, Project, ShiftSlot
from src.services.price_resolver import resolve_sales_price, resolve_outsource_price


@dataclass
class AggregatedResult:
    """集計結果"""
    period_key: str
    project_id: Optional[str]
    project_name: Optional[str]
    client_id: Optional[str]
    client_name: Optional[str]
    
    # 予定 (Assignment ベース)
    planned_hours: Decimal
    planned_sales: Decimal
    planned_cost: Decimal
    planned_profit: Decimal
    planned_profit_rate: Optional[Decimal]
    
    # 確定 (Actual ベース)
    confirmed_hours: Decimal
    confirmed_sales: Decimal
    confirmed_cost: Decimal
    confirmed_profit: Decimal
    confirmed_profit_rate: Optional[Decimal]
    
    # 差分
    delta_hours: Decimal
    delta_sales: Decimal
    delta_cost: Decimal
    delta_profit: Decimal


def aggregate_by_period(
    session: Session,
    period_key: str,
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> AggregatedResult:
    """期間別に集計する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
        project_id: プロジェクトID (指定時は案件別集計)
        client_id: クライアントID (指定時はクライアント別集計)
    
    Returns:
        集計結果
    """
    # 予定集計 (Assignment)
    planned_result = _aggregate_planned(session, period_key, project_id, client_id)
    
    # 確定集計 (Actual)
    confirmed_result = _aggregate_confirmed(session, period_key, project_id, client_id)
    
    # 差分計算
    delta_hours = confirmed_result["hours"] - planned_result["hours"]
    delta_sales = confirmed_result["sales"] - planned_result["sales"]
    delta_cost = confirmed_result["cost"] - planned_result["cost"]
    delta_profit = confirmed_result["profit"] - planned_result["profit"]
    
    return AggregatedResult(
        period_key=period_key,
        project_id=project_id,
        project_name=planned_result.get("project_name"),
        client_id=client_id,
        client_name=planned_result.get("client_name"),
        
        planned_hours=planned_result["hours"],
        planned_sales=planned_result["sales"],
        planned_cost=planned_result["cost"],
        planned_profit=planned_result["profit"],
        planned_profit_rate=planned_result.get("profit_rate"),
        
        confirmed_hours=confirmed_result["hours"],
        confirmed_sales=confirmed_result["sales"],
        confirmed_cost=confirmed_result["cost"],
        confirmed_profit=confirmed_result["profit"],
        confirmed_profit_rate=confirmed_result.get("profit_rate"),
        
        delta_hours=delta_hours,
        delta_sales=delta_sales,
        delta_cost=delta_cost,
        delta_profit=delta_profit,
    )


def aggregate_by_project(
    session: Session,
    period_key: str,
) -> List[AggregatedResult]:
    """案件別に集計する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        案件別集計結果のリスト
    """
    # すべてのプロジェクトIDを取得（期間内のシフトから）
    stmt = (
        select(ShiftSlot.project_id)
        .join(Assignment)
        .where(
            func.strftime('%Y%m', ShiftSlot.work_date) == period_key
        )
        .distinct()
    )
    project_ids = session.execute(stmt).scalars().all()
    
    results = []
    for project_id in project_ids:
        result = aggregate_by_period(session, period_key, project_id=project_id)
        results.append(result)
    
    return results


def aggregate_by_client(
    session: Session,
    period_key: str,
) -> List[AggregatedResult]:
    """クライアント別に集計する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        クライアント別集計結果のリスト
    """
    # すべてのクライアントIDを取得（期間内のシフト→プロジェクト→クライアント）
    stmt = (
        select(Project.client_id)
        .join(ShiftSlot)
        .join(Assignment)
        .where(
            func.strftime('%Y%m', ShiftSlot.work_date) == period_key
        )
        .distinct()
    )
    client_ids = session.execute(stmt).scalars().all()
    
    results = []
    for client_id in client_ids:
        result = aggregate_by_period(session, period_key, client_id=client_id)
        results.append(result)
    
    return results


def _aggregate_planned(
    session: Session,
    period_key: str,
    project_id: Optional[str],
    client_id: Optional[str],
) -> dict:
    """予定を集計 (Assignment ベース)"""
    stmt = (
        select(Assignment)
        .join(ShiftSlot)
        .where(
            func.strftime('%Y%m', ShiftSlot.work_date) == period_key,
            Assignment.status != AssignmentStatus.CANCELED,
        )
    )
    
    if project_id:
        stmt = stmt.where(ShiftSlot.project_id == project_id)
    
    if client_id:
        stmt = stmt.join(Project).where(Project.client_id == client_id)
    
    assignments = session.execute(stmt).scalars().all()
    
    total_hours = Decimal("0")
    total_sales = Decimal("0")
    total_cost = Decimal("0")
    
    project_name = None
    client_name = None
    
    for assignment in assignments:
        # 予定時間をShiftSlotから計算
        shift_slot = assignment.shift_slot
        if shift_slot and shift_slot.start_time and shift_slot.end_time:
            # 時刻から分数を計算
            start_minutes = shift_slot.start_time.hour * 60 + shift_slot.start_time.minute
            end_minutes = shift_slot.end_time.hour * 60 + shift_slot.end_time.minute
            
            # 日跨ぎ対応
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            total_minutes = end_minutes - start_minutes
            hours = Decimal(total_minutes) / Decimal("60")
        else:
            hours = Decimal("0")
        
        total_hours += hours
        
        # 売上単価（ShiftSlotのwork_dateを使用）
        work_date = shift_slot.work_date if shift_slot else date.today()
        sales_price = resolve_sales_price(session, assignment, work_date)
        if sales_price:
            total_sales += sales_price * hours
        
        # 外注単価
        cost_price = resolve_outsource_price(session, assignment, work_date)
        if cost_price:
            total_cost += cost_price * hours
        
        # プロジェクト名とクライアント名を保持（ShiftSlot経由）
        if shift_slot and shift_slot.project:
            if not project_name:
                project_name = shift_slot.project.name
            if not client_name and shift_slot.project.client:
                client_name = shift_slot.project.client.name
    
    profit = total_sales - total_cost
    profit_rate = None
    if total_sales > 0:
        profit_rate = (profit / total_sales * Decimal("100")).quantize(
            Decimal("0.01"), rounding="ROUND_HALF_UP"
        )
    
    return {
        "hours": total_hours,
        "sales": total_sales,
        "cost": total_cost,
        "profit": profit,
        "profit_rate": profit_rate,
        "project_name": project_name,
        "client_name": client_name,
    }


def _aggregate_confirmed(
    session: Session,
    period_key: str,
    project_id: Optional[str],
    client_id: Optional[str],
) -> dict:
    """確定を集計 (Actual ベース)"""
    stmt = (
        select(Actual)
        .where(
            Actual.period_key == period_key,
            Actual.status == ActualStatus.ACTIVE,
        )
    )
    
    if project_id:
        stmt = stmt.where(Actual.project_id == project_id)
    
    if client_id:
        stmt = stmt.join(Project).where(Project.client_id == client_id)
    
    actuals = session.execute(stmt).scalars().all()
    
    total_hours = Decimal("0")
    total_sales = Decimal("0")
    total_cost = Decimal("0")
    
    for actual in actuals:
        # 確定時間（calc_minutes_billableを使用）
        hours = Decimal(actual.calc_minutes_billable) / Decimal("60")
        total_hours += hours
        
        # 売上単価（applied_price_sales を使用）
        if actual.applied_price_sales:
            total_sales += actual.applied_price_sales * hours
        
        # 外注単価（applied_price_outsource を使用）
        if actual.applied_price_outsource:
            total_cost += actual.applied_price_outsource * hours
    
    profit = total_sales - total_cost
    profit_rate = None
    if total_sales > 0:
        profit_rate = (profit / total_sales * Decimal("100")).quantize(
            Decimal("0.01"), rounding="ROUND_HALF_UP"
        )
    
    return {
        "hours": total_hours,
        "sales": total_sales,
        "cost": total_cost,
        "profit": profit,
        "profit_rate": profit_rate,
    }
