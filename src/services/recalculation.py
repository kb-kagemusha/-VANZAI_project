"""
再計算サービス
仕様参照: DESIGN_SPEC_v0.3 セクション7.4（再計算のガードレール）

主要機能:
- 範囲指定による再計算（project_id, period_key, date_range）
- 影響件数と金額差のプレビュー
- Hard Close後の再計算拒否
- 監査ログ出力
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.models.enums import ActualStatus, ClosingStatus, AuditAction, InvoiceStatus, PayoutStatus, NightCalcMode
from src.models.transaction import Actual, Assignment, Closing, Invoice, Payout, Project
from src.services.audit import log
from src.services.price_resolver import resolve_sales_price, resolve_outsource_price
from src.services.time_calc import calculate_time
from dataclasses import field


@dataclass
class RecalcPreview:
    """再計算プレビュー結果"""
    target_count: int  # 対象件数
    current_total_sales: Decimal  # 現在の売上合計
    current_total_outsource: Decimal  # 現在の外注費合計
    estimated_total_sales: Decimal  # 再計算後の売上合計（見込み）
    estimated_total_outsource: Decimal  # 再計算後の外注費合計（見込み）
    blocked_count: int = 0  # 再計算不可件数（Hard Close済み等）
    warnings: list[str] = field(default_factory=list)  # 警告メッセージ
    sales_diff: Decimal = field(init=False)  # 売上差分（__post_init__で計算）
    outsource_diff: Decimal = field(init=False)  # 外注費差分（__post_init__で計算）
    
    def __post_init__(self):
        self.sales_diff = self.estimated_total_sales - self.current_total_sales
        self.outsource_diff = self.estimated_total_outsource - self.current_total_outsource


@dataclass
class RecalcResult:
    """再計算実行結果"""
    recalculated_count: int  # 再計算した件数
    skipped_count: int  # スキップした件数
    error_count: int  # エラー件数
    total_sales_before: Decimal  # 再計算前の売上合計
    total_sales_after: Decimal  # 再計算後の売上合計
    total_outsource_before: Decimal  # 再計算前の外注費合計
    total_outsource_after: Decimal  # 再計算後の外注費合計
    errors: list[str] = field(default_factory=list)  # エラーメッセージ


class RecalculationService:
    """
    再計算サービス
    
    仕様参照: 7.4 再計算のガードレール
    AGENTS.md: 金額と時間は必ず再現可能にする
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def preview_recalculation(
        self,
        *,
        project_id: Optional[str] = None,
        period_key: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        worker_id: Optional[str] = None,
    ) -> RecalcPreview:
        """
        再計算の影響をプレビューする
        
        Args:
            project_id: 案件ID（指定時は案件単位で再計算）
            period_key: 期間キー（YYYYMM）
            date_from: 開始日
            date_to: 終了日
            worker_id: 稼働者ID（指定時は稼働者単位で再計算）
        
        Returns:
            RecalcPreview
        """
        # 対象のActualを取得
        actuals = self._fetch_target_actuals(
            project_id=project_id,
            period_key=period_key,
            date_from=date_from,
            date_to=date_to,
            worker_id=worker_id,
        )
        
        # 現在の合計を計算
        current_total_sales = Decimal("0")
        current_total_outsource = Decimal("0")
        estimated_total_sales = Decimal("0")
        estimated_total_outsource = Decimal("0")
        blocked_count = 0
        warnings = []
        
        for actual in actuals:
            # Hard Close済みかチェック
            if self._is_hard_closed(actual):
                blocked_count += 1
                continue
            
            # 発行済み請求・支払に紐づいているかチェック
            if self._is_in_issued_invoice_or_payout(actual):
                warnings.append(
                    f"Actual {actual.id} is in issued invoice or approved payout"
                )
            
            # 現在の金額
            if actual.applied_price_sales:
                hours = Decimal(actual.calc_minutes_billable or actual.calc_minutes_total) / Decimal("60")
                current_total_sales += actual.applied_price_sales * hours
            
            if actual.applied_price_outsource:
                hours = Decimal(actual.calc_minutes_billable or actual.calc_minutes_total) / Decimal("60")
                current_total_outsource += actual.applied_price_outsource * hours
            
            # 再計算後の見込み金額
            new_sales_price = resolve_sales_price(self.session, actual.assignment, actual.work_date)
            new_outsource_price = resolve_outsource_price(self.session, actual.assignment, actual.work_date)
            
            # 時間も再計算（簡易版：既存の calc_minutes_billable を使用）
            hours = Decimal(actual.calc_minutes_billable or actual.calc_minutes_total) / Decimal("60")
            
            if new_sales_price:
                estimated_total_sales += new_sales_price * hours
            
            if new_outsource_price:
                estimated_total_outsource += new_outsource_price * hours
        
        target_count = len(actuals) - blocked_count
        
        return RecalcPreview(
            target_count=target_count,
            current_total_sales=current_total_sales,
            current_total_outsource=current_total_outsource,
            estimated_total_sales=estimated_total_sales,
            estimated_total_outsource=estimated_total_outsource,
            blocked_count=blocked_count,
            warnings=warnings,
        )
    
    def recalculate(
        self,
        user_id: str,
        *,
        project_id: Optional[str] = None,
        period_key: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        worker_id: Optional[str] = None,
        force: bool = False,
    ) -> RecalcResult:
        """
        再計算を実行する
        
        仕様参照: 7.4
        - Hard Close済みは再計算対象から除外
        - 発行済み請求・支払に紐づくactualは原則再計算対象から除外（force=Trueで許可）
        
        Args:
            user_id: 実行ユーザー
            project_id: 案件ID
            period_key: 期間キー（YYYYMM）
            date_from: 開始日
            date_to: 終了日
            worker_id: 稼働者ID
            force: 強制実行（発行済みも再計算）
        
        Returns:
            RecalcResult
        """
        # 対象のActualを取得
        actuals = self._fetch_target_actuals(
            project_id=project_id,
            period_key=period_key,
            date_from=date_from,
            date_to=date_to,
            worker_id=worker_id,
        )
        
        recalculated_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        total_sales_before = Decimal("0")
        total_sales_after = Decimal("0")
        total_outsource_before = Decimal("0")
        total_outsource_after = Decimal("0")
        
        for actual in actuals:
            try:
                # Hard Close済みはスキップ（強制実行でも不可）
                if self._is_hard_closed(actual):
                    skipped_count += 1
                    continue
                
                # 発行済み請求・支払チェック
                if not force and self._is_in_issued_invoice_or_payout(actual):
                    skipped_count += 1
                    continue
                
                # 現在の金額を記録
                hours = Decimal(actual.calc_minutes_billable or actual.calc_minutes_total) / Decimal("60")
                if actual.applied_price_sales:
                    total_sales_before += actual.applied_price_sales * hours
                if actual.applied_price_outsource:
                    total_outsource_before += actual.applied_price_outsource * hours
                
                # 単価を再解決
                new_sales_price = resolve_sales_price(self.session, actual.assignment, actual.work_date)
                new_outsource_price = resolve_outsource_price(self.session, actual.assignment, actual.work_date)
                
                # 単価が解決できない場合は既存の単価を保持
                if new_sales_price is None:
                    new_sales_price = actual.applied_price_sales
                if new_outsource_price is None:
                    new_outsource_price = actual.applied_price_outsource
                
                # 時間計算を再実行（時間計算ルールが変わった場合に対応）
                project = actual.assignment.shift_slot.project
                if actual.start_time and actual.end_time:
                    time_result = calculate_time(
                        start_time=actual.start_time,
                        end_time=actual.end_time,
                        break_minutes_input=actual.break_minutes_input,
                        hours_input=actual.hours_input,
                        rounding_unit=project.rounding_unit_minutes,
                        rounding_method=project.rounding_method,
                        break_rule=project.break_deduction_rule,
                        time_calc_mode=project.time_calc_mode,
                        night_window_start=project.night_window_start,
                        night_window_end=project.night_window_end,
                        store_night_minutes=(project.night_calc_mode == NightCalcMode.STORE_MINUTES.value),
                    )
                    
                    # 時間計算結果を更新
                    actual.calc_minutes_total = time_result.minutes_total
                    actual.calc_minutes_billable = time_result.minutes_billable
                    actual.calc_minutes_break = time_result.minutes_break
                    actual.calc_minutes_night = time_result.minutes_night
                    actual.calc_rounding_unit = time_result.rounding_unit
                    actual.calc_rounding_method = time_result.rounding_method
                    actual.calc_break_rule = time_result.break_rule
                
                # 単価を更新
                actual.applied_price_sales = new_sales_price
                actual.applied_price_outsource = new_outsource_price
                
                # 新しい金額を記録
                hours = Decimal(actual.calc_minutes_billable or actual.calc_minutes_total) / Decimal("60")
                if new_sales_price:
                    total_sales_after += new_sales_price * hours
                if new_outsource_price:
                    total_outsource_after += new_outsource_price * hours
                
                recalculated_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Actual {actual.id}: {str(e)}")
        
        # 監査ログ
        log(
            self.session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="actuals",
            record_id=None,
            user_id=user_id,
            extra_metadata={
                "action": "recalculate",
                "project_id": project_id,
                "period_key": period_key,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
                "worker_id": worker_id,
                "recalculated_count": recalculated_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "sales_before": float(total_sales_before),
                "sales_after": float(total_sales_after),
                "outsource_before": float(total_outsource_before),
                "outsource_after": float(total_outsource_after),
            },
        )
        
        self.session.flush()
        
        return RecalcResult(
            recalculated_count=recalculated_count,
            skipped_count=skipped_count,
            error_count=error_count,
            total_sales_before=total_sales_before,
            total_sales_after=total_sales_after,
            total_outsource_before=total_outsource_before,
            total_outsource_after=total_outsource_after,
            errors=errors,
        )
    
    def _fetch_target_actuals(
        self,
        project_id: Optional[str] = None,
        period_key: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        worker_id: Optional[str] = None,
    ) -> list[Actual]:
        """
        再計算対象のActualを取得
        
        Args:
            project_id: 案件ID
            period_key: 期間キー
            date_from: 開始日
            date_to: 終了日
            worker_id: 稼働者ID
        
        Returns:
            Actual のリスト
        """
        stmt = select(Actual).where(
            Actual.status == ActualStatus.ACTIVE
        )
        
        if project_id:
            stmt = stmt.where(
                Actual.assignment.has(
                    Assignment.shift_slot.has(project_id=project_id)
                )
            )
        
        if period_key:
            stmt = stmt.where(Actual.period_key == period_key)
        
        if date_from:
            stmt = stmt.where(Actual.work_date >= date_from)
        
        if date_to:
            stmt = stmt.where(Actual.work_date <= date_to)
        
        if worker_id:
            stmt = stmt.where(Actual.worker_id == worker_id)
        
        return list(self.session.execute(stmt).scalars().all())
    
    def _is_hard_closed(self, actual: Actual) -> bool:
        """
        ActualがHard Close済みかチェック
        
        Args:
            actual: Actual
        
        Returns:
            True: Hard Close済み, False: 未締め
        """
        project_id = actual.assignment.shift_slot.project_id
        period_key = actual.period_key
        
        stmt = select(Closing).where(
            and_(
                Closing.project_id == project_id,
                Closing.period_key == period_key,
                Closing.status == ClosingStatus.HARD_CLOSED,
            )
        )
        closing = self.session.execute(stmt).scalars().first()
        return closing is not None
    
    def _is_in_issued_invoice_or_payout(self, actual: Actual) -> bool:
        """
        Actualが発行済み請求または承認済み支払に含まれているかチェック
        
        Args:
            actual: Actual
        
        Returns:
            True: 発行済み, False: 未発行
        """
        # 請求書チェック
        from src.models.transaction import InvoiceLine
        stmt = select(InvoiceLine).where(
            and_(
                InvoiceLine.actual_id == actual.id,
                InvoiceLine.invoice.has(
                    Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.CLOSED])
                )
            )
        )
        invoice_line = self.session.execute(stmt).scalars().first()
        if invoice_line:
            return True
        
        # 支払明細チェック
        from src.models.transaction import PayoutLine
        stmt = select(PayoutLine).where(
            and_(
                PayoutLine.actual_id == actual.id,
                PayoutLine.payout.has(
                    Payout.status.in_([PayoutStatus.APPROVED, PayoutStatus.PAID, PayoutStatus.CLOSED])
                )
            )
        )
        payout_line = self.session.execute(stmt).scalars().first()
        return payout_line is not None
