"""ダッシュボードサービス (DESIGN_SPEC_v0.3 セクション13章)

未処理一覧:
- 予定と実績の差分（未入力、過剰入力）
- 単価未設定
- 未発行請求書
- 未承認支払明細
"""
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.models.enums import (
    ActualStatus,
    AssignmentStatus,
    AssignmentWorkerResponseStatus,
    InvoiceStatus,
    PayoutStatus,
    ClosingStatus,
)
from src.models.master import Supplier, Worker
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
class MissingPayoutRecipient:
    """既定送信先未設定の支払明細"""
    payout_id: str
    project_id: Optional[str]
    payee_name: str
    project_name: Optional[str]
    period_key: str
    status: str
    default_recipient_type: str
    reason: str


@dataclass
class PendingAssignmentResponse:
    """未回答の予定確認"""
    assignment_id: str
    project_id: str
    project_name: str
    worker_id: str
    worker_name: str
    worker_email: str | None
    work_date: date
    shift_label: str | None
    worker_response_requested_at: datetime | None
    hours_since_request: int | None
    days_until_work: int
    escalation_level: str
    escalation_reasons: List[str]
    reason: str


def build_assignment_response_monitoring(
    *,
    work_date: date,
    worker_email: str | None,
    worker_response_requested_at: datetime | None,
) -> PendingAssignmentResponse:
    """予定確認の監視状態を計算する"""
    now = datetime.now(timezone.utc)
    today = date.today()
    escalate_days_before_work = _get_non_negative_int_env("ASSIGNMENT_RESPONSE_ESCALATION_DAYS_BEFORE_WORK", 2)
    escalate_hours_since_request = _get_non_negative_int_env("ASSIGNMENT_RESPONSE_ESCALATION_HOURS_SINCE_REQUEST", 72)

    normalized_worker_email = worker_email.strip() if worker_email else None
    requested_at = _normalize_utc_datetime(worker_response_requested_at)
    hours_since_request = None
    if requested_at is not None:
        hours_since_request = max(int((now - requested_at).total_seconds() // 3600), 0)

    days_until_work = (work_date - today).days
    escalation_reasons: List[str] = []
    if not normalized_worker_email:
        escalation_reasons.append("メール送信先未設定")
    if days_until_work < 0:
        escalation_reasons.append("稼働日超過")
    elif days_until_work <= escalate_days_before_work:
        escalation_reasons.append(f"稼働日まで{days_until_work}日")
    if hours_since_request is not None and hours_since_request >= escalate_hours_since_request:
        escalation_reasons.append(f"依頼から{hours_since_request}時間経過")

    escalation_level = "escalate" if escalation_reasons else "watch"
    reason = " / ".join(escalation_reasons) if escalation_reasons else "未回答のため継続確認中"

    return PendingAssignmentResponse(
        assignment_id="",
        project_id="",
        project_name="",
        worker_id="",
        worker_name="",
        worker_email=normalized_worker_email,
        work_date=work_date,
        shift_label=None,
        worker_response_requested_at=requested_at,
        hours_since_request=hours_since_request,
        days_until_work=days_until_work,
        escalation_level=escalation_level,
        escalation_reasons=escalation_reasons,
        reason=reason,
    )


@dataclass
class DashboardSummary:
    """ダッシュボードサマリー"""
    period_key: str
    
    # 未処理件数
    unprocessed_assignment_count: int
    missing_price_count: int
    unprocessed_invoice_count: int
    unprocessed_payout_count: int
    missing_payout_recipient_count: int
    pending_assignment_response_count: int
    escalated_assignment_response_count: int
    unclosed_project_count: int
    
    # 詳細リスト
    unprocessed_assignments: List[UnprocessedAssignment]
    missing_prices: List[MissingPriceAlert]
    unprocessed_invoices: List[UnprocessedInvoice]
    unprocessed_payouts: List[UnprocessedPayout]
    missing_payout_recipients: List[MissingPayoutRecipient]
    pending_assignment_responses: List[PendingAssignmentResponse]


def _get_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return max(int(raw), 0)
    except ValueError:
        return default


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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

    # 支払送信先未設定
    missing_payout_recipients = get_missing_payout_recipients(session, period_key, project_ids=project_ids)

    # 予定確認未回答
    pending_assignment_responses = get_pending_assignment_responses(session, period_key, project_ids=project_ids)
    escalated_assignment_response_count = sum(
        1 for item in pending_assignment_responses if item.escalation_level == "escalate"
    )
    
    # 未締めプロジェクト
    unclosed_project_count = _count_unclosed_projects(session, period_key, project_ids=project_ids)
    
    return DashboardSummary(
        period_key=period_key,
        unprocessed_assignment_count=len(unprocessed_assignments),
        missing_price_count=len(missing_prices),
        unprocessed_invoice_count=len(unprocessed_invoices),
        unprocessed_payout_count=len(unprocessed_payouts),
        missing_payout_recipient_count=len(missing_payout_recipients),
        pending_assignment_response_count=len(pending_assignment_responses),
        escalated_assignment_response_count=escalated_assignment_response_count,
        unclosed_project_count=unclosed_project_count,
        unprocessed_assignments=unprocessed_assignments,
        missing_prices=missing_prices,
        unprocessed_invoices=unprocessed_invoices,
        unprocessed_payouts=unprocessed_payouts,
        missing_payout_recipients=missing_payout_recipients,
        pending_assignment_responses=pending_assignment_responses,
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


def get_missing_payout_recipients(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[MissingPayoutRecipient]:
    """既定送信先が未設定の支払明細一覧を取得する"""
    conditions = [Payout.period_key == period_key]
    if project_ids is not None:
        conditions.append(Payout.project_id.in_(project_ids))

    stmt = (
        select(Payout, Worker.name, Worker.email, Supplier.name, Supplier.contact_email, Project.name)
        .outerjoin(Worker, Payout.worker_id == Worker.id)
        .outerjoin(Supplier, Payout.supplier_id == Supplier.id)
        .outerjoin(Project, Payout.project_id == Project.id)
        .where(
            *conditions,
            and_(
                Payout.worker_id.is_not(None),
                or_(Worker.email.is_(None), func.trim(Worker.email) == ""),
            )
            | and_(
                Payout.supplier_id.is_not(None),
                or_(Supplier.contact_email.is_(None), func.trim(Supplier.contact_email) == ""),
            )
            | and_(Payout.worker_id.is_(None), Payout.supplier_id.is_(None)),
        )
    )

    rows = session.execute(stmt).all()
    items: List[MissingPayoutRecipient] = []
    for payout, worker_name, worker_email, supplier_name, supplier_email, project_name in rows:
        payee_name = worker_name or supplier_name or payout.id
        default_recipient_type = "worker_email" if payout.worker_id else "supplier_email" if payout.supplier_id else "unknown"
        missing_email = worker_email if payout.worker_id else supplier_email if payout.supplier_id else None
        items.append(
            MissingPayoutRecipient(
                payout_id=payout.id,
                project_id=payout.project_id,
                payee_name=payee_name,
                project_name=project_name,
                period_key=payout.period_key,
                status=payout.status,
                default_recipient_type=default_recipient_type,
                reason="既定送信先メールが未設定です" if not missing_email else "既定送信先メールを確認してください",
            )
        )

    return items


def get_pending_assignment_responses(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> List[PendingAssignmentResponse]:
    """未回答の予定確認一覧を取得する"""
    year = int(period_key[:4])
    month = int(period_key[4:6])
    conditions = [
        func.extract('year', ShiftSlot.work_date) == year,
        func.extract('month', ShiftSlot.work_date) == month,
        Assignment.status != AssignmentStatus.CANCELED,
        Assignment.worker_response_status == AssignmentWorkerResponseStatus.PENDING,
    ]
    if project_ids is not None:
        conditions.append(ShiftSlot.project_id.in_(project_ids))

    stmt = (
        select(Assignment)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .where(*conditions)
        .order_by(ShiftSlot.work_date, ShiftSlot.start_time, Assignment.id)
    )
    assignments = session.execute(stmt).scalars().all()

    items: List[PendingAssignmentResponse] = []
    for assignment in assignments:
        monitoring = build_assignment_response_monitoring(
            work_date=assignment.shift_slot.work_date,
            worker_email=assignment.worker.email,
            worker_response_requested_at=assignment.worker_response_requested_at,
        )
        project = assignment.shift_slot.project

        items.append(
            PendingAssignmentResponse(
                assignment_id=assignment.id,
                project_id=project.id,
                project_name=project.name,
                worker_id=assignment.worker_id,
                worker_name=assignment.worker.name,
                worker_email=monitoring.worker_email,
                work_date=assignment.shift_slot.work_date,
                shift_label=assignment.shift_slot.shift_label,
                worker_response_requested_at=monitoring.worker_response_requested_at,
                hours_since_request=monitoring.hours_since_request,
                days_until_work=monitoring.days_until_work,
                escalation_level=monitoring.escalation_level,
                escalation_reasons=monitoring.escalation_reasons,
                reason=monitoring.reason,
            )
        )

    return items


def _count_unclosed_projects(
    session: Session,
    period_key: str,
    project_ids: Optional[List[str]] = None,
) -> int:
    """未締めプロジェクト数を取得する"""
    rows = get_project_closings_for_period(session, period_key, project_ids=project_ids)
    return sum(1 for _, closing in rows if closing is None or closing.status == ClosingStatus.OPEN)
