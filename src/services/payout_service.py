"""支払明細生成サービス (DESIGN_SPEC_v0.3 セクション11章)

版管理:
- 訂正時は parent_payout_id を設定
- version は自動インクリメント
- 旧版は status=closed になる
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.models.enums import ActualStatus, PayoutStatus, AuditAction, ExpenseStatus, IncentiveStatus
from src.models.transaction import (
    Actual,
    Assignment,
    Payout,
    PayoutLine,
    ShiftSlot,
)
from src.services.audit import log
from src.services.price_resolver import resolve_outsource_price
from src.exceptions import (
    PayoutAlreadyPaidException,
    RecordNotFoundException,
    ValidationException,
)


def generate_payout(
    session: Session,
    worker_id: str,
    project_id: Optional[str],
    period_key: str,
    payment_date: date,
    user_id: str,
) -> Payout:
    """支払明細を生成する
    
    Args:
        session: DB セッション
        worker_id: 稼働者ID
        project_id: プロジェクトID (指定時は案件別支払明細)
        period_key: 対象月 (YYYYMM)
        payment_date: 支払日
        user_id: 実行ユーザー
    
    Returns:
        生成された Payout
    """
    # 1. 既存の preparing 支払明細があれば削除
    _delete_preparing_payouts(session, worker_id, project_id, period_key)
    
    # 2. 対象 Actual を抽出 (status=valid のみ)
    actuals = _fetch_actuals_for_payout(session, worker_id, project_id, period_key)
    
    # 3. Payout 作成
    payout = Payout(
        worker_id=worker_id,
        project_id=project_id,
        period_key=period_key,
        payment_date=payment_date,
        status=PayoutStatus.PREPARING,
        version=1,
        total_amount=Decimal("0"),
    )
    session.add(payout)
    session.flush()
    
    # 4. PayoutLine を生成
    line_number = 1
    total_amount = Decimal("0")
    for actual in actuals:
        # 単価取得（applied_price_outsource が既にあればそれを使用、なければ解決）
        if actual.applied_price_outsource is not None:
            price = actual.applied_price_outsource
        else:
            price = resolve_outsource_price(session, actual.assignment, actual.work_date)
        
        if price is None:
            # 単価が解決できない場合はスキップまたはエラー
            log(
                session,
                action=AuditAction.PAYOUT_CREATED,
                table_name="actuals",
                record_id=actual.id,
                user_id=user_id,
                extra_metadata={
                    "error": "price_not_resolved",
                    "work_date": str(actual.work_date),
                },
            )
            continue
        
        # 数量 (時間を h 単位で計算)
        quantity = Decimal(actual.calc_minutes_total) / Decimal("60")
        line_amount = price * quantity
        
        line = PayoutLine(
            payout_id=payout.id,
            line_number=line_number,
            description=f"{actual.work_date} {actual.assignment.shift_slot.project.name}",
            actual_id=actual.id,
            unit_price_snapshot=price,
            quantity_snapshot=quantity,
            unit_type="hourly",
            line_amount=line_amount,
            is_correction=False,
        )
        session.add(line)
        total_amount += line_amount
        line_number += 1
    
    # 4.5. 経費・インセンティブ行を追加（承認済みのみ）
    if project_id:  # プロジェクト指定時のみ
        from src.services.expense_service import ExpenseService
        from src.services.incentive_service import IncentiveService
        
        expense_service = ExpenseService(session)
        incentive_service = IncentiveService(session)
        
        # 期間キーから日付範囲を算出 (YYYYMM → YYYY-MM-01 ~ YYYY-MM-31)
        year = int(period_key[:4])
        month = int(period_key[4:6])
        from calendar import monthrange
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        
        # 承認済み経費を取得
        expenses = expense_service.get_expenses_for_worker_period(
            worker_id=worker_id,
            start_date=start_date,
            end_date=end_date,
            status=ExpenseStatus.APPROVED
        )
        
        for expense in expenses:
            if expense.target_payout:  # 支払明細に計上する経費のみ
                line = PayoutLine(
                    payout_id=payout.id,
                    line_number=line_number,
                    description=f"経費: {expense.category} - {expense.description or ''}",
                    line_type="expense",
                    expense_id=expense.id,
                    unit_price_snapshot=expense.amount,
                    quantity_snapshot=Decimal("1"),
                    unit_type="lumpsum",
                    line_amount=expense.amount,
                    is_correction=False,
                )
                session.add(line)
                total_amount += expense.amount
                line_number += 1
                
                # 経費に支払明細IDを設定
                expense.target_payout_id = payout.id
        
        # 承認済みインセンティブを取得
        incentives = incentive_service.get_incentives_for_worker_period(
            worker_id=worker_id,
            period_key=period_key,
            status=IncentiveStatus.APPROVED
        )
        
        for incentive in incentives:
            # インセンティブは支払明細に計上（target_payout_idがNoneの場合のみ追加）
            if incentive.target_payout_id is None:
                line = PayoutLine(
                    payout_id=payout.id,
                    line_number=line_number,
                    description=f"インセンティブ: {incentive.incentive_rule.name if incentive.incentive_rule else 'その他'}",
                    line_type="incentive",
                    incentive_id=incentive.id,
                    unit_price_snapshot=incentive.amount,
                    quantity_snapshot=Decimal("1"),
                    unit_type="lumpsum",
                    line_amount=incentive.amount,
                    is_correction=False,
                )
                session.add(line)
                total_amount += incentive.amount
                line_number += 1
                
                # インセンティブに支払明細IDを設定
                incentive.target_payout_id = payout.id
    
    # 5. 合計を設定
    payout.total_amount = total_amount
    
    session.flush()
    
    log(
        session,
        action=AuditAction.PAYOUT_CREATED,
        table_name="payouts",
        record_id=payout.id,
        user_id=user_id,
        extra_metadata={
            "worker_id": worker_id,
            "project_id": project_id,
            "period_key": period_key,
            "line_count": line_number - 1,
            "total": float(total_amount),
        },
    )
    
    return payout


def approve_payout(
    session: Session,
    payout_id: str,
    user_id: str,
) -> Payout:
    """支払明細を承認する (status を approved に変更)
    
    Args:
        session: DB セッション
        payout_id: 支払明細ID
        user_id: 承認者
    
    Returns:
        承認された Payout
    """
    payout = session.get(Payout, payout_id)
    if not payout:
        raise RecordNotFoundException("Payout", payout_id)
    
    if payout.status != PayoutStatus.PREPARING:
        raise PayoutAlreadyPaidException(
            f"Payout already approved: {payout_id}",
            details={"payout_id": payout_id, "status": payout.status.value}
        )
    
    payout.status = PayoutStatus.APPROVED
    payout.approved_at = datetime.now()
    
    log(
        session,
        action=AuditAction.PAYOUT_APPROVED,
        table_name="payouts",
        record_id=payout.id,
        user_id=user_id,
        extra_metadata={
            "period_key": payout.period_key,
            "total": float(payout.total_amount),
        },
    )
    
    return payout


def mark_payout_paid(
    session: Session,
    payout_id: str,
    user_id: str,
) -> Payout:
    """支払明細を支払済みにする (status を paid に変更)
    
    Args:
        session: DB セッション
        payout_id: 支払明細ID
        user_id: 実行ユーザー
    
    Returns:
        支払済みの Payout
    """
    payout = session.get(Payout, payout_id)
    if not payout:
        raise RecordNotFoundException("Payout", payout_id)
    
    if payout.status != PayoutStatus.APPROVED:
        raise ValidationException(
            f"Payout not approved: {payout_id}",
            details={"payout_id": payout_id, "status": payout.status.value}
        )
    
    payout.status = PayoutStatus.PAID
    payout.paid_at = datetime.now()
    
    log(
        session,
        action=AuditAction.PAYOUT_PAID,
        table_name="payouts",
        record_id=payout.id,
        user_id=user_id,
        extra_metadata={
            "period_key": payout.period_key,
            "total": float(payout.total_amount),
        },
    )
    
    return payout


def correct_payout(
    session: Session,
    original_payout_id: str,
    correction_lines: List[dict],
    user_id: str,
) -> Payout:
    """支払明細を訂正する (新しい版を作成)
    
    Args:
        session: DB セッション
        original_payout_id: 元の支払明細ID
        correction_lines: 訂正明細リスト
            例: [{"description": "訂正理由", "line_amount": Decimal("-1000")}]
        user_id: 実行ユーザー
    
    Returns:
        新しい版の Payout
    """
    original = session.get(Payout, original_payout_id)
    if not original:
        raise RecordNotFoundException("Payout", original_payout_id)
    
    if original.status == PayoutStatus.PREPARING:
        raise ValidationException(
            "Cannot correct preparing payout",
            details={"payout_id": original_payout_id, "status": original.status.value}
        )
    
    # 元の支払明細を closed にする
    original.status = PayoutStatus.CLOSED
    original.closed_at = datetime.now()
    
    # 新しい版を作成
    new_payout = Payout(
        worker_id=original.worker_id,
        project_id=original.project_id,
        period_key=original.period_key,
        payment_date=original.payment_date,
        status=PayoutStatus.PREPARING,
        version=original.version + 1,
        parent_payout_id=original.id,
        total_amount=original.total_amount,
    )
    session.add(new_payout)
    session.flush()
    
    # 元の明細をコピー
    original_lines = (
        session.execute(
            select(PayoutLine).where(PayoutLine.payout_id == original.id)
        )
        .scalars()
        .all()
    )
    
    line_number = 1
    for orig_line in original_lines:
        line = PayoutLine(
            payout_id=new_payout.id,
            line_number=line_number,
            description=orig_line.description,
            actual_id=orig_line.actual_id,
            unit_price_snapshot=orig_line.unit_price_snapshot,
            quantity_snapshot=orig_line.quantity_snapshot,
            unit_type=orig_line.unit_type,
            line_amount=orig_line.line_amount,
            is_correction=False,
        )
        session.add(line)
        line_number += 1
    
    # 訂正明細を追加
    total_delta = Decimal("0")
    for corr in correction_lines:
        line = PayoutLine(
            payout_id=new_payout.id,
            line_number=line_number,
            description=corr["description"],
            actual_id=None,
            unit_price_snapshot=Decimal("0"),
            quantity_snapshot=Decimal("0"),
            unit_type="correction",
            line_amount=Decimal(corr["line_amount"]),
            is_correction=True,
        )
        session.add(line)
        total_delta += Decimal(corr["line_amount"])
        line_number += 1
    
    # 合計を再計算
    new_total = new_payout.total_amount + total_delta
    new_payout.total_amount = new_total
    
    session.flush()
    
    log(
        session,
        action=AuditAction.PAYOUT_CORRECTED,
        table_name="payouts",
        record_id=new_payout.id,
        user_id=user_id,
        extra_metadata={
            "original_payout_id": original.id,
            "original_version": original.version,
            "new_version": new_payout.version,
            "correction_lines": len(correction_lines),
            "delta": float(total_delta),
        },
    )
    
    return new_payout


def _delete_preparing_payouts(
    session: Session,
    worker_id: str,
    project_id: Optional[str],
    period_key: str,
) -> None:
    """preparing 状態の支払明細を削除 (再生成前のクリーンアップ)"""
    stmt = select(Payout).where(
        Payout.worker_id == worker_id,
        Payout.period_key == period_key,
        Payout.status == PayoutStatus.PREPARING,
    )
    if project_id:
        stmt = stmt.where(Payout.project_id == project_id)
    
    payouts = session.execute(stmt).scalars().all()
    for pyt in payouts:
        session.delete(pyt)


def _fetch_actuals_for_payout(
    session: Session,
    worker_id: str,
    project_id: Optional[str],
    period_key: str,
) -> List[Actual]:
    """支払明細対象の Actual を取得 (status=valid のみ)
    
    N+1クエリ対策: joinedloadで関連オブジェクトを一括取得
    推奨タスク: N+1クエリ解消（joinedload）
    """
    from sqlalchemy.orm import joinedload
    
    stmt = (
        select(Actual)
        .join(Assignment, Actual.assignment_id == Assignment.id)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .options(
            joinedload(Actual.assignment)
            .joinedload(Assignment.shift_slot)
            .joinedload(ShiftSlot.project)
        )
        .where(
            Actual.status == ActualStatus.ACTIVE,
            Actual.period_key == period_key,
            Assignment.worker_id == worker_id,
        )
    )
    
    if project_id:
        stmt = stmt.where(ShiftSlot.project_id == project_id)
    
    # unique() を使用してjoinedloadによる重複行を除去
    return list(session.execute(stmt).unique().scalars().all())


def generate_supplier_payout(
    session: Session,
    supplier_id: str,
    period_key: str,
    payment_date: date,
    user_id: str,
) -> Payout:
    """下請け（紹介者）向けの支払明細を生成する
    
    drv案件の下請け支払いに対応。
    - 紹介者配下の稼働者の実績を集計
    - 日額単価（例: 16,000円/日、16,500円/日）で支払金額を計算
    - 人工単位で集計（unit_type=days）
    
    Args:
        session: DB セッション
        supplier_id: 紹介者ID
        period_key: 対象月 (YYYYMM)
        payment_date: 支払日
        user_id: 実行ユーザー
    
    Returns:
        生成された Payout
    """
    from src.models.master import Supplier, Worker
    
    # 1. Supplier取得
    supplier = session.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.deleted_at == None
    ).first()
    
    if not supplier:
        raise RecordNotFoundException(f"Supplier not found: {supplier_id}")
    
    # 2. 既存の preparing 支払明細があれば削除
    stmt = select(Payout).where(
        Payout.supplier_id == supplier_id,
        Payout.period_key == period_key,
        Payout.status == PayoutStatus.PREPARING,
    )
    existing_payouts = session.execute(stmt).scalars().all()
    for pyt in existing_payouts:
        session.delete(pyt)
    
    # 3. 紹介者配下の稼働者を取得
    workers = session.query(Worker).filter(
        Worker.introducer_supplier_id == supplier_id,
        Worker.deleted_at == None
    ).all()
    
    if not workers:
        raise ValidationException(f"No workers found for supplier: {supplier.name}")
    
    worker_ids = [w.id for w in workers]
    
    # 4. 対象 Actual を抽出 (status=valid のみ)
    from sqlalchemy.orm import joinedload
    
    stmt = (
        select(Actual)
        .join(Assignment, Actual.assignment_id == Assignment.id)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .options(
            joinedload(Actual.assignment)
            .joinedload(Assignment.shift_slot)
            .joinedload(ShiftSlot.project)
        )
        .where(
            Actual.status == ActualStatus.ACTIVE,
            Actual.period_key == period_key,
            Assignment.worker_id.in_(worker_ids),
        )
    )
    
    actuals = list(session.execute(stmt).unique().scalars().all())
    
    if not actuals:
        raise ValidationException(f"No actuals found for supplier {supplier.name} in period {period_key}")
    
    # 5. Payout 作成
    payout = Payout(
        supplier_id=supplier_id,
        worker_id=None,  # supplier向けの場合はNULL
        project_id=None,  # 複数案件をまとめて支払う
        period_key=period_key,
        payment_date=payment_date,
        status=PayoutStatus.PREPARING,
        version=1,
        total_amount=Decimal("0"),
    )
    session.add(payout)
    session.flush()
    
    # 6. PayoutLine を生成（日額単位で集計）
    # 人工単位: (worker_id, work_date, project_id) のユニーク数
    line_number = 1
    total_amount = Decimal("0")
    
    # 実績を (worker_id, work_date, project_id) でグループ化
    man_days = {}
    for actual in actuals:
        key = (actual.assignment.worker_id, actual.work_date, actual.assignment.shift_slot.project_id)
        if key not in man_days:
            man_days[key] = {
                "worker_id": actual.assignment.worker_id,
                "worker_name": actual.assignment.worker.name,
                "work_date": actual.work_date,
                "project_id": actual.assignment.shift_slot.project_id,
                "project_name": actual.assignment.shift_slot.project.name,
                "actuals": []
            }
        man_days[key]["actuals"].append(actual)
    
    # 日額単価を取得（supplierのdefault_daily_price、なければ16,000円）
    daily_price = supplier.default_daily_price or Decimal("16000")
    
    # PayoutLine を作成
    for key, data in man_days.items():
        description = f"{data['worker_name']} - {data['project_name']} ({data['work_date']})"
        line_amount = daily_price  # 1人工あたりの金額
        
        line = PayoutLine(
            payout_id=payout.id,
            line_number=line_number,
            description=description,
            actual_id=data["actuals"][0].id if data["actuals"] else None,  # 代表実績ID
            unit_price_snapshot=daily_price,
            quantity_snapshot=Decimal("1"),  # 1人工
            unit_type="days",
            line_amount=line_amount,
        )
        session.add(line)
        total_amount += line_amount
        line_number += 1
    
    # 7. 合計金額を設定
    payout.total_amount = total_amount
    session.flush()
    
    log(
        session,
        action=AuditAction.PAYOUT_CREATED,
        table_name="payouts",
        record_id=payout.id,
        user_id=user_id,
        extra_metadata={
            "supplier_id": supplier_id,
            "supplier_name": supplier.name,
            "period_key": period_key,
            "man_days": len(man_days),
            "total_amount": float(total_amount),
        },
    )
    
    return payout
