"""ダッシュボードサービス (DESIGN_SPEC_v0.3 セクション13章)

未処理一覧:
- 予定と実績の差分（未入力、過剰入力）
- 単価未設定
- 未発行請求書
- 未承認支払明細
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.enums import (
    ActualStatus,
    AssignmentStatus,
    InvoiceStatus,
    PayoutStatus,
    ClosingStatus,
)
from src.models.transaction import (
    Actual,
    Assignment,
    Invoice,
    Payout,
    Closing,
    Project,
    ShiftSlot,
)
from src.services.price_resolver import resolve_sales_price, resolve_outsource_price


def _period_bounds(period_key: str) -> tuple[date, date]:
    year = int(period_key[:4])
    month = int(period_key[4:6])
    period_start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    period_end = next_month - timedelta(days=1)
    return period_start, period_end


def get_projects_for_period(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[Project]:
    """対象月に有効な案件一覧を返す"""
    period_start, period_end = _period_bounds(period_key)

    conditions = [
        Project.deleted_at.is_(None),
        (Project.start_date.is_(None) | (Project.start_date <= period_end)),
        (Project.end_date.is_(None) | (Project.end_date >= period_start)),
    ]
    if project_ids is not None:
        conditions.append(Project.id.in_(project_ids))

    stmt = select(Project).where(*conditions)
    return session.execute(stmt).scalars().all()


def get_project_closings_for_period(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[tuple[Project, Closing | None]]:
    """対象月の案件と締めレコードの組を返す"""
    projects = get_projects_for_period(session, period_key, project_ids=project_ids)
    closings = session.execute(
        select(Closing).where(
            Closing.period_key == period_key,
            Closing.project_id.in_([project.id for project in projects]) if projects else False,
        )
    ).scalars().all() if projects else []
    closing_map = {closing.project_id: closing for closing in closings}
    return [(project, closing_map.get(project.id)) for project in projects]


@dataclass
class UnprocessedAssignment:
    """未処理アサインメント"""
    assignment_id: str
    project_id: str
    project_name: str
    worker_name: str
    work_date: date
    expected_minutes: int
    actual_minutes: int
    delta_minutes: int
    status: str
    reason: str


@dataclass
class MissingPriceAlert:
    """単価未設定アラート"""
    assignment_id: str
    project_id: str
    project_name: str
    worker_name: str
    work_date: date
    price_type: str  # 'sales' or 'outsource'
    reason: str


@dataclass
class UnprocessedInvoice:
    """未処理請求書"""
    invoice_id: Optional[str]
    project_id: Optional[str]
    client_name: str
    project_name: Optional[str]
    period_key: str
    status: str
    total_amount: Decimal
    reason: str


@dataclass
class UnprocessedPayout:
    """未処理支払明細"""
    payout_id: Optional[str]
    project_id: Optional[str]
    worker_name: str
    project_name: Optional[str]
    period_key: str
    status: str
    total_amount: Decimal
    reason: str


@dataclass
class DashboardSummary:
    """ダッシュボードサマリー"""
    period_key: str
    
    # 未処理件数
    unprocessed_assignment_count: int
    missing_price_count: int
    unprocessed_invoice_count: int
    unprocessed_payout_count: int
    unclosed_project_count: int
    
    # 詳細リスト
    unprocessed_assignments: List[UnprocessedAssignment]
    missing_prices: List[MissingPriceAlert]
    unprocessed_invoices: List[UnprocessedInvoice]
    unprocessed_payouts: List[UnprocessedPayout]


def get_dashboard_summary(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> DashboardSummary:
    """ダッシュボードサマリーを取得する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        ダッシュボードサマリー
    """
    # 未処理アサインメント
    unprocessed_assignments = get_unprocessed_assignments(session, period_key, project_ids=project_ids)
    
    # 単価未設定
    missing_prices = get_missing_price_alerts(session, period_key, project_ids=project_ids)
    
    # 未処理請求書
    unprocessed_invoices = get_unprocessed_invoices(session, period_key, project_ids=project_ids)
    
    # 未処理支払明細
    unprocessed_payouts = get_unprocessed_payouts(session, period_key, project_ids=project_ids)
    
    # 未締めプロジェクト
    unclosed_project_count = _count_unclosed_projects(session, period_key, project_ids=project_ids)
    
    return DashboardSummary(
        period_key=period_key,
        unprocessed_assignment_count=len(unprocessed_assignments),
        missing_price_count=len(missing_prices),
        unprocessed_invoice_count=len(unprocessed_invoices),
        unprocessed_payout_count=len(unprocessed_payouts),
        unclosed_project_count=unclosed_project_count,
        unprocessed_assignments=unprocessed_assignments,
        missing_prices=missing_prices,
        unprocessed_invoices=unprocessed_invoices,
        unprocessed_payouts=unprocessed_payouts,
    )


def get_unprocessed_assignments(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[UnprocessedAssignment]:
    """未処理アサインメント一覧を取得する（予定と実績の差分）
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        未処理アサインメントのリスト
    """
    # すべてのアサインメントを取得（work_dateでフィルタ）
    # period_key = "YYYYMM" から年月を抽出
    year = int(period_key[:4])
    month = int(period_key[4:6])
    
    conditions = [
        func.extract('year', ShiftSlot.work_date) == year,
        func.extract('month', ShiftSlot.work_date) == month,
        Assignment.status != AssignmentStatus.CANCELED,
    ]
    if project_ids is not None:
        conditions.append(ShiftSlot.project_id.in_(project_ids))

    stmt = (
        select(Assignment)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .where(*conditions)
    )
    assignments = session.execute(stmt).scalars().all()
    
    unprocessed = []
    for assignment in assignments:
        # 実績を取得
        actual_stmt = (
            select(Actual)
            .where(
                Actual.assignment_id == assignment.id,
                Actual.status == ActualStatus.ACTIVE,
            )
        )
        actuals = session.execute(actual_stmt).scalars().all()
        
        # 実績合計（Actual.calc_minutes_totalを使用）
        actual_minutes = sum(a.calc_minutes_total or 0 for a in actuals)
        # ShiftSlotから予定時間を計算
        shift_slot = assignment.shift_slot
        if shift_slot.start_time and shift_slot.end_time:
            from .time_calc import calculate_total_minutes
            expected_minutes = calculate_total_minutes(shift_slot.start_time, shift_slot.end_time)
        else:
            expected_minutes = 0
        delta_minutes = actual_minutes - expected_minutes
        
        # 差分があれば未処理
        if delta_minutes != 0:
            reason = "未入力" if delta_minutes < 0 else "過剰入力"
            # projectはshift_slot経由で取得
            project = assignment.shift_slot.project
            unprocessed.append(
                UnprocessedAssignment(
                    assignment_id=assignment.id,
                    project_id=project.id,
                    project_name=project.name,
                    worker_name=assignment.worker.name,
                    work_date=assignment.shift_slot.work_date,
                    expected_minutes=expected_minutes,
                    actual_minutes=actual_minutes,
                    delta_minutes=delta_minutes,
                    status=assignment.status,
                    reason=reason,
                )
            )
    
    return unprocessed


def get_missing_price_alerts(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[MissingPriceAlert]:
    """単価未設定アラート一覧を取得する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        単価未設定アラートのリスト
    """
    # すべてのアサインメントを取得（work_dateでフィルタ）
    year = int(period_key[:4])
    month = int(period_key[4:6])
    
    conditions = [
        func.extract('year', ShiftSlot.work_date) == year,
        func.extract('month', ShiftSlot.work_date) == month,
        Assignment.status != AssignmentStatus.CANCELED,
    ]
    if project_ids is not None:
        conditions.append(ShiftSlot.project_id.in_(project_ids))

    stmt = (
        select(Assignment)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .where(*conditions)
    )
    assignments = session.execute(stmt).scalars().all()
    
    missing_prices = []
    for assignment in assignments:
        work_date = assignment.shift_slot.work_date
        
        # 売上単価チェック
        sales_price = resolve_sales_price(session, assignment, work_date)
        if sales_price is None:
            project = assignment.shift_slot.project
            missing_prices.append(
                MissingPriceAlert(
                    assignment_id=assignment.id,
                    project_id=project.id,
                    project_name=project.name,
                    worker_name=assignment.worker.name,
                    work_date=work_date,
                    price_type="sales",
                    reason="売上単価が未設定",
                )
            )
        
        # 外注単価チェック
        outsource_price = resolve_outsource_price(session, assignment, work_date)
        if outsource_price is None:
            project = assignment.shift_slot.project
            missing_prices.append(
                MissingPriceAlert(
                    assignment_id=assignment.id,
                    project_id=project.id,
                    project_name=project.name,
                    worker_name=assignment.worker.name,
                    work_date=work_date,
                    price_type="outsource",
                    reason="外注単価が未設定",
                )
            )
    
    return missing_prices


def get_unprocessed_invoices(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[UnprocessedInvoice]:
    """未処理請求書一覧を取得する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        未処理請求書のリスト
    """
    # preparing または issued でない請求書を検索
    conditions = [
        Invoice.period_key == period_key,
        Invoice.status.in_([InvoiceStatus.PREPARING]),
    ]
    if project_ids is not None:
        conditions.append(Invoice.project_id.in_(project_ids))

    stmt = select(Invoice).where(*conditions)
    invoices = session.execute(stmt).scalars().all()
    
    unprocessed = []
    for invoice in invoices:
        unprocessed.append(
            UnprocessedInvoice(
                invoice_id=invoice.id,
                project_id=invoice.project_id,
                client_name=invoice.client.name,
                project_name=invoice.project.name if invoice.project else None,
                period_key=invoice.period_key,
                status=invoice.status,
                total_amount=invoice.total_amount,
                reason="未発行",
            )
        )
    
    return unprocessed


def get_unprocessed_payouts(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[UnprocessedPayout]:
    """未処理支払明細一覧を取得する
    
    Args:
        session: DB セッション
        period_key: 対象月 (YYYYMM)
    
    Returns:
        未処理支払明細のリスト
    """
    # preparing または approved でない支払明細を検索
    conditions = [
        Payout.period_key == period_key,
        Payout.status.in_([PayoutStatus.PREPARING, PayoutStatus.APPROVED]),
    ]
    if project_ids is not None:
        conditions.append(Payout.project_id.in_(project_ids))

    stmt = select(Payout).where(*conditions)
    payouts = session.execute(stmt).scalars().all()
    
    unprocessed = []
    for payout in payouts:
        reason = "未承認" if payout.status == PayoutStatus.PREPARING else "未支払"
        unprocessed.append(
            UnprocessedPayout(
                payout_id=payout.id,
                project_id=payout.project_id,
                worker_name=payout.worker.name,
                project_name=payout.project.name if payout.project else None,
                period_key=payout.period_key,
                status=payout.status,
                total_amount=payout.total_amount,
                reason=reason,
            )
        )
    
    return unprocessed


def _count_unclosed_projects(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> int:
    """未締めプロジェクト数を取得する"""
    rows = get_project_closings_for_period(session, period_key, project_ids=project_ids)
    return sum(1 for _, closing in rows if closing is None or closing.status == ClosingStatus.OPEN)
