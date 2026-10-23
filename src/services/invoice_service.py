"""請求書生成サービス (DESIGN_SPEC_v0.3 セクション11章)

版管理:
- 訂正時は parent_invoice_id を設定
- version は自動インクリメント
- 旧版は status=closed になる
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.models.enums import ActualStatus, InvoiceStatus, AuditAction, ExpenseStatus, IncentiveStatus
from src.models.transaction import (
    Actual,
    Assignment,
    Invoice,
    InvoiceLine,
    Project,
    ShiftSlot,
)
from src.services.financial_guards import lock_client_projects, ensure_unallocated, archive_drafts, copy_lines, ancestor_ids, ensure_components_unallocated
from src.services.audit import log
from src.services.company_profile import current_profile
from src.services.price_resolver import resolve_sales_price
from src.exceptions import (
    InvoiceAlreadyIssuedException,
    RecordNotFoundException,
    ValidationException,
)


def generate_invoice(
    session: Session,
    client_id: str,
    project_id: Optional[str],
    period_key: str,
    billing_date: date,
    user_id: str,
    *,
    document_type: str = "invoice",
    subject: str | None = None,
    addressee_company_name: str | None = None,
    addressee_name: str | None = None,
    addressee_email: str | None = None,
    addressee_address: str | None = None,
    fixed_office_fee_amount: Decimal | None = None,
) -> Invoice:
    """請求書を生成する
    
    Args:
        session: DB セッション
        client_id: クライアントID
        project_id: プロジェクトID (指定時は案件別請求書)
        period_key: 対象月 (YYYYMM)
        billing_date: 請求日
        user_id: 実行ユーザー
    
    Returns:
        生成された Invoice
    """
    from src.models.master import Client
    from src.models.order_billing import OrderBillingInvoice
    session.execute(select(Client).where(Client.id == client_id).with_for_update()).scalars().all()
    if document_type == "invoice" and session.query(OrderBillingInvoice.id).filter(
            OrderBillingInvoice.client_id == client_id, OrderBillingInvoice.billing_month == period_key,
            OrderBillingInvoice.status.in_(["draft", "issued"])).first():
        raise ValidationException("同じ請求先・請求月に依頼書から作成した請求書があります。二重請求を防ぐため、請求経路を確認してください")
    lock_client_projects(session, client_id)
    actuals = _fetch_actuals_for_invoice(session, client_id, project_id, period_key)
    ensure_unallocated(session, [row.id for row in actuals], "invoice")
    _delete_preparing_invoices(session, client_id, project_id, period_key)
    
    # 3. Invoice 作成
    invoice = Invoice(
        client_id=client_id,
        project_id=project_id,
        period_key=period_key,
        billing_date=billing_date,
        document_type=document_type,
        invoice_subject=subject,
        addressee_company_name=addressee_company_name,
        addressee_name=addressee_name,
        addressee_email=addressee_email,
        addressee_address=addressee_address,
        fixed_office_fee_amount=fixed_office_fee_amount,
        status=InvoiceStatus.PREPARING,
        version=1,
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("0"),
    )
    session.add(invoice)
    session.flush()
    
    # 4. InvoiceLine を生成
    line_number = 1
    subtotal = Decimal("0")
    for actual in actuals:
        # 単価取得（applied_price_sales が既にあればそれを使用、なければ解決）
        if actual.applied_price_sales is not None:
            price = actual.applied_price_sales
        else:
            price = resolve_sales_price(session, actual.assignment, actual.work_date)
        
        if price is None:
            # 単価が解決できない場合はスキップまたはエラー
            log(
                session,
                action=AuditAction.INVOICE_CREATED,
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
        quantity = Decimal(actual.calc_minutes_billable) / Decimal("60")
        line_amount = price * quantity
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            line_number=line_number,
            description=f"{actual.work_date} {actual.assignment.worker.name}",
            actual_id=actual.id,
            unit_price_snapshot=price,
            quantity_snapshot=quantity,
            unit_type="hourly",
            line_amount=line_amount,
            tax_amount=Decimal("0"),  # 消費税は後で計算
            is_correction=False,
        )
        session.add(line)
        subtotal += line_amount
        line_number += 1

    fixed_office_fee = Decimal(str(fixed_office_fee_amount or 0))
    if fixed_office_fee > 0:
        session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                line_number=line_number,
                description="固定事務局費",
                line_type="office_fee",
                unit_price_snapshot=fixed_office_fee,
                quantity_snapshot=Decimal("1"),
                unit_type="lumpsum",
                line_amount=fixed_office_fee,
                tax_amount=Decimal("0"),
                is_correction=False,
            )
        )
        subtotal += fixed_office_fee
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
        expenses = expense_service.get_expenses_for_project_period(
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
            status=ExpenseStatus.APPROVED
        )
        
        for expense in expenses:
            if expense.target_invoice:  # 請求書に計上する経費のみ
                line = InvoiceLine(
                    invoice_id=invoice.id,
                    line_number=line_number,
                    description=f"経費: {expense.category} - {expense.description or ''}",
                    line_type="expense",
                    expense_id=expense.id,
                    unit_price_snapshot=expense.amount,
                    quantity_snapshot=Decimal("1"),
                    unit_type="lumpsum",
                    line_amount=expense.amount,
                    tax_amount=Decimal("0"),
                    is_correction=False,
                )
                session.add(line)
                subtotal += expense.amount
                line_number += 1
                
                # 経費に請求書IDを設定
                expense.target_invoice_id = invoice.id
        
        # 承認済みインセンティブを取得
        incentives = incentive_service.get_incentives_for_project_period(
            project_id=project_id,
            period_key=period_key,
            status=IncentiveStatus.APPROVED
        )
        
        for incentive in incentives:
            # インセンティブは請求書に計上（target_invoice_idがNoneの場合のみ追加）
            if incentive.target_invoice_id is None:
                line = InvoiceLine(
                    invoice_id=invoice.id,
                    line_number=line_number,
                    description=f"インセンティブ: {incentive.incentive_rule.name if incentive.incentive_rule else 'その他'}",
                    line_type="incentive",
                    incentive_id=incentive.id,
                    unit_price_snapshot=incentive.amount,
                    quantity_snapshot=Decimal("1"),
                    unit_type="lumpsum",
                    line_amount=incentive.amount,
                    tax_amount=Decimal("0"),
                    is_correction=False,
                )
                session.add(line)
                subtotal += incentive.amount
                line_number += 1
                
                # インセンティブに請求書IDを設定
                incentive.target_invoice_id = invoice.id
    
    # 5. 合計を計算
    tax_amount = subtotal * Decimal("0.10")  # 10%
    total_amount = subtotal + tax_amount
    
    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount
    invoice.total_amount = total_amount
    
    session.flush()
    
    log(
        session,
        action=AuditAction.INVOICE_CREATED,
        table_name="invoices",
        record_id=invoice.id,
        user_id=user_id,
        extra_metadata={
            "client_id": client_id,
            "project_id": project_id,
            "period_key": period_key,
            "document_type": document_type,
            "subject": subject,
            "fixed_office_fee_amount": float(fixed_office_fee),
            "line_count": line_number - 1,
            "subtotal": float(subtotal),
            "total": float(total_amount),
        },
    )
    
    return invoice


def issue_invoice(
    session: Session,
    invoice_id: str,
    user_id: str,
) -> Invoice:
    """請求書を発行する (status を issued に変更)
    
    Args:
        session: DB セッション
        invoice_id: 請求書ID
        user_id: 実行ユーザー
    
    Returns:
        発行された Invoice
    """
    invoice = session.get(Invoice, invoice_id)
    if invoice:
        lock_client_projects(session, invoice.client_id)
        session.refresh(invoice)
    if not invoice:
        raise RecordNotFoundException("Invoice", invoice_id)
    
    if invoice.status != InvoiceStatus.PREPARING:
        raise InvoiceAlreadyIssuedException(
            f"Invoice already issued: {invoice_id}",
            details={"invoice_id": invoice_id, "status": getattr(invoice.status, "value", invoice.status)}
        )
    
    if invoice.deleted_at is not None:
        raise ValidationException("置き換え済みの下書きは発行できません")
    ensure_unallocated(session, [line.actual_id for line in invoice.lines if line.actual_id], "invoice", ancestor_ids(session, invoice, Invoice, "parent_invoice_id"))
    ensure_components_unallocated(session, invoice, "invoice")
    invoice.status = InvoiceStatus.ISSUED
    invoice.issued_at = datetime.now()
    # 発行した時点の会社情報を保存する（0.49.8、DEC-082）
    invoice.issuer_snapshot = current_profile(session)
    
    log(
        session,
        action=AuditAction.INVOICE_ISSUED,
        table_name="invoices",
        record_id=invoice.id,
        user_id=user_id,
        extra_metadata={
            "period_key": invoice.period_key,
            "total": float(invoice.total_amount),
        },
    )
    
    return invoice


def correct_invoice(
    session: Session,
    original_invoice_id: str,
    correction_lines: List[dict],
    user_id: str,
) -> Invoice:
    """請求書を訂正する (新しい版を作成)
    
    Args:
        session: DB セッション
        original_invoice_id: 元の請求書ID
        correction_lines: 訂正明細リスト
            例: [{"description": "訂正理由", "line_amount": Decimal("-1000")}]
        user_id: 実行ユーザー
    
    Returns:
        新しい版の Invoice
    """
    original = session.get(Invoice, original_invoice_id)
    if not original:
        raise RecordNotFoundException("Invoice", original_invoice_id)
    
    if original.status == InvoiceStatus.PREPARING:
        raise ValidationException(
            "Cannot correct preparing invoice",
            details={"invoice_id": original_invoice_id, "status": getattr(original.status, "value", original.status)}
        )
    
    # 元の請求書を closed にする
    original.status = InvoiceStatus.CLOSED
    original.closed_at = datetime.now()
    
    # 新しい版を作成
    new_invoice = Invoice(
        client_id=original.client_id,
        project_id=original.project_id,
        period_key=original.period_key,
        billing_date=original.billing_date,
        status=InvoiceStatus.PREPARING,
        version=original.version + 1,
        parent_invoice_id=original.id,
        document_type=original.document_type, invoice_subject=original.invoice_subject,
        addressee_company_name=original.addressee_company_name, addressee_name=original.addressee_name,
        addressee_email=original.addressee_email, addressee_address=original.addressee_address,
        fixed_office_fee_amount=original.fixed_office_fee_amount,
        subtotal=original.subtotal,
        tax_amount=original.tax_amount,
        total_amount=original.total_amount,
    )
    session.add(new_invoice)
    session.flush()
    
    # 元の明細をコピー
    original_lines = (
        session.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == original.id)
        )
        .scalars()
        .all()
    )
    
    copy_lines(session, InvoiceLine, original.id, new_invoice.id, "invoice_id")
    line_number = len(original_lines) + 1

    # 訂正明細を追加
    subtotal_delta = Decimal("0")
    for corr in correction_lines:
        line = InvoiceLine(
            invoice_id=new_invoice.id,
            line_number=line_number,
            description=corr["description"],
            actual_id=None,
            unit_price_snapshot=Decimal("0"),
            quantity_snapshot=Decimal("0"),
            unit_type="correction",
            line_amount=Decimal(corr["line_amount"]),
            tax_amount=Decimal("0"),
            is_correction=True,
        )
        session.add(line)
        subtotal_delta += Decimal(corr["line_amount"])
        line_number += 1
    
    # 合計を再計算
    new_subtotal = new_invoice.subtotal + subtotal_delta
    new_tax = new_subtotal * Decimal("0.10")
    new_total = new_subtotal + new_tax
    
    new_invoice.subtotal = new_subtotal
    new_invoice.tax_amount = new_tax
    new_invoice.total_amount = new_total
    
    session.flush()
    
    log(
        session,
        action=AuditAction.INVOICE_CORRECTED,
        table_name="invoices",
        record_id=new_invoice.id,
        user_id=user_id,
        extra_metadata={
            "original_invoice_id": original.id,
            "original_version": original.version,
            "new_version": new_invoice.version,
            "correction_lines": len(correction_lines),
            "delta": float(subtotal_delta),
        },
    )
    
    return new_invoice


def reissue_invoice(
    session: Session,
    invoice_id: str,
    user_id: str,
) -> Invoice:
    """請求書を再発行する (ISSUED状態の請求書をCLOSEDにして新版を作成)
    
    Args:
        session: DB セッション
        invoice_id: 請求書ID (既存のISSUED請求書)
        user_id: 実行ユーザー
    
    Returns:
        再発行された新版Invoice
    """
    original_invoice = session.get(Invoice, invoice_id)
    if original_invoice:
        lock_client_projects(session, original_invoice.client_id)
        session.refresh(original_invoice)
    if not original_invoice:
        raise RecordNotFoundException("Invoice", invoice_id)
    
    if original_invoice.status != InvoiceStatus.ISSUED:
        raise ValidationException(
            f"Invoice is not issued: {invoice_id}",
            details={"invoice_id": invoice_id, "status": getattr(original_invoice.status, "value", original_invoice.status)}
        )
    
    # 元の請求書をCLOSEDにする
    original_invoice.status = InvoiceStatus.CLOSED
    session.flush()
    
    # 新しい請求書を作成（version + 1）
    new_invoice = Invoice(
        client_id=original_invoice.client_id,
        project_id=original_invoice.project_id,
        period_key=original_invoice.period_key,
        billing_date=original_invoice.billing_date,
        version=original_invoice.version + 1,
        parent_invoice_id=original_invoice.id,
        status=InvoiceStatus.ISSUED,
        subtotal=original_invoice.subtotal,
        tax_amount=original_invoice.tax_amount,
        total_amount=original_invoice.total_amount,
        issued_at=datetime.now(),
        document_type=original_invoice.document_type,
        invoice_subject=original_invoice.invoice_subject,
        addressee_company_name=original_invoice.addressee_company_name,
        addressee_name=original_invoice.addressee_name,
        addressee_email=original_invoice.addressee_email,
        addressee_address=original_invoice.addressee_address,
        fixed_office_fee_amount=original_invoice.fixed_office_fee_amount,
        notes=original_invoice.notes,
        # 再発行は新しい発行なので、今の会社情報を保存する（0.49.8、DEC-082）
        issuer_snapshot=current_profile(session),
    )
    session.add(new_invoice)
    session.flush()
    copy_lines(session, InvoiceLine, original_invoice.id, new_invoice.id, "invoice_id")
    session.flush()
    log(
        session,
        action=AuditAction.INVOICE_REISSUED,
        table_name="invoices",
        record_id=new_invoice.id,
        user_id=user_id,
        extra_metadata={
            "version": new_invoice.version,
            "parent_invoice_id": original_invoice.id,
            "total": float(new_invoice.total_amount),
        },
    )
    
    return new_invoice


def _delete_preparing_invoices(
    session: Session,
    client_id: str,
    project_id: Optional[str],
    period_key: str,
) -> None:
    """preparing 状態の請求書を削除 (再生成前のクリーンアップ)"""
    stmt = select(Invoice).where(
        Invoice.client_id == client_id,
        Invoice.period_key == period_key,
        Invoice.status == InvoiceStatus.PREPARING,
        Invoice.deleted_at.is_(None),
    )
    stmt = stmt.where(Invoice.project_id == project_id) if project_id else stmt.where(Invoice.project_id.is_(None))
    invoices = session.execute(stmt).scalars().all()
    archive_drafts(session, invoices, "invoice")


def _fetch_actuals_for_invoice(
    session: Session,
    client_id: str,
    project_id: Optional[str],
    period_key: str,
) -> List[Actual]:
    """請求書対象の Actual を取得 (status=valid のみ)
    
    N+1クエリ対策: joinedloadで関連オブジェクトを一括取得
    推奨タスク: N+1クエリ解消（joinedload）
    """
    from sqlalchemy.orm import joinedload
    
    stmt = (
        select(Actual)
        .join(Assignment, Actual.assignment_id == Assignment.id)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .options(
            joinedload(Actual.assignment)
            .joinedload(Assignment.worker),
            joinedload(Actual.assignment)
            .joinedload(Assignment.shift_slot)
            .joinedload(ShiftSlot.project)
        )
        .where(
            Actual.status == ActualStatus.ACTIVE,
            Actual.period_key == period_key,
            Project.client_id == client_id,
        )
    )
    
    if project_id:
        stmt = stmt.where(Project.id == project_id)
    
    # unique() を使用してjoinedloadによる重複行を除去
    return list(session.execute(stmt).unique().scalars().all())
