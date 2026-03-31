"""
経費精算サービス
仕様参照: DESIGN_SPEC_v0.3.md セクション17（経費精算）
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models.enums import Permission, ExpenseStatus, AuditAction
from ..models.master import User, Worker
from ..models.transaction import Expense, Project
from .audit import AuditService
from .auth import require_permission


@dataclass
class ExpenseCreateInput:
    """経費作成入力"""
    project_id: str
    worker_id: str
    expense_date: date
    category: str
    amount: Decimal
    description: Optional[str] = None
    receipt_file_key: Optional[str] = None
    target_invoice: bool = False
    target_payout: bool = True


@dataclass
class ExpenseApprovalResult:
    """経費承認結果"""
    success: bool
    expense: Optional[Expense]
    message: str


class ExpenseService:
    """
    経費精算サービス
    仕様参照: 17.2, 17.3, 17.4
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    @require_permission(Permission.EXPENSE_SUBMIT)
    def create_expense(
        self,
        user: User,
        input_data: ExpenseCreateInput
    ) -> Expense:
        """
        経費を作成する（仕様17.2）
        
        Args:
            user: 実行ユーザー
            input_data: 経費作成データ
            
        Returns:
            作成された経費レコード
        """
        # プロジェクトと稼働者の存在確認
        project = self.session.get(Project, input_data.project_id)
        if not project:
            raise RecordNotFoundException(
                message="Project not found",
                details={"project_id": input_data.project_id}
            )
        
        worker = self.session.get(Worker, input_data.worker_id)
        if not worker:
            raise RecordNotFoundException(
                message="Worker not found",
                details={"worker_id": input_data.worker_id}
            )
        
        # 経費レコード作成
        expense = Expense(
            project_id=input_data.project_id,
            worker_id=input_data.worker_id,
            expense_date=input_data.expense_date,
            category=input_data.category,
            amount=input_data.amount,
            description=input_data.description,
            receipt_file_key=input_data.receipt_file_key,
            status=ExpenseStatus.PENDING,
            target_invoice=input_data.target_invoice,
            target_payout=input_data.target_payout,
        )
        
        self.session.add(expense)
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.IMPORT_BATCH_CREATED,  # 暫定的にこのActionを使用
            target_type="Expense",
            target_id=expense.id,
            actor=user.username,
            actor_role=user.role,
            extra_metadata={
                "project_id": input_data.project_id,
                "worker_id": input_data.worker_id,
                "amount": str(input_data.amount),
                "category": input_data.category,
            }
        )
        
        return expense
    
    @require_permission(Permission.EXPENSE_APPROVE)
    def approve_expense(
        self,
        user: User,
        expense_id: str
    ) -> ExpenseApprovalResult:
        """
        経費を承認する（仕様17.2）
        
        Args:
            user: 承認者
            expense_id: 経費ID
            
        Returns:
            承認結果
        """
        expense = self.session.get(Expense, expense_id)
        if not expense:
            return ExpenseApprovalResult(
                success=False,
                expense=None,
                message=f"Expense not found: {expense_id}"
            )
        
        if expense.status != ExpenseStatus.PENDING:
            return ExpenseApprovalResult(
                success=False,
                expense=expense,
                message=f"Expense is not pending: {expense.status}"
            )
        
        # 承認処理
        expense.status = ExpenseStatus.APPROVED
        expense.approved_by = user.id
        expense.approved_at = datetime.now(timezone.utc)
        
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.IMPORT_BATCH_COMPLETED,  # 暫定
            target_type="Expense",
            target_id=expense.id,
            actor=user.username,
            actor_role=user.role,
            extra_metadata={
                "amount": str(expense.amount),
                "category": expense.category,
            }
        )
        
        return ExpenseApprovalResult(
            success=True,
            expense=expense,
            message="Expense approved successfully"
        )
    
    @require_permission(Permission.EXPENSE_APPROVE)
    def reject_expense(
        self,
        user: User,
        expense_id: str,
        rejection_reason: str
    ) -> ExpenseApprovalResult:
        """
        経費を却下する（仕様17.2）
        
        Args:
            user: 却下者
            expense_id: 経費ID
            rejection_reason: 却下理由
            
        Returns:
            却下結果
        """
        expense = self.session.get(Expense, expense_id)
        if not expense:
            return ExpenseApprovalResult(
                success=False,
                expense=None,
                message=f"Expense not found: {expense_id}"
            )
        
        if expense.status != ExpenseStatus.PENDING:
            return ExpenseApprovalResult(
                success=False,
                expense=expense,
                message=f"Expense is not pending: {expense.status}"
            )
        
        # 却下処理
        expense.status = ExpenseStatus.REJECTED
        expense.approved_by = user.id
        expense.approved_at = datetime.now(timezone.utc)
        expense.rejection_reason = rejection_reason
        
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.ACTUAL_INVALIDATED,  # 暫定
            target_type="Expense",
            target_id=expense.id,
            actor=user.username,
            actor_role=user.role,
            reason=rejection_reason,
            extra_metadata={
                "amount": str(expense.amount),
                "category": expense.category,
            }
        )
        
        return ExpenseApprovalResult(
            success=True,
            expense=expense,
            message="Expense rejected successfully"
        )
    
    def get_expenses_for_project_period(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
        status: Optional[ExpenseStatus] = None
    ) -> List[Expense]:
        """
        プロジェクト×期間の経費リストを取得（仕様17.3で請求書生成時に使用）
        
        Args:
            project_id: プロジェクトID
            start_date: 開始日
            end_date: 終了日
            status: ステータスフィルタ（Noneなら全て）
            
        Returns:
            経費リスト
        """
        query = self.session.query(Expense).filter(
            and_(
                Expense.project_id == project_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
        )
        
        if status:
            query = query.filter(Expense.status == status)
        
        return query.order_by(Expense.expense_date).all()
    
    def get_expenses_for_worker_period(
        self,
        worker_id: str,
        start_date: date,
        end_date: date,
        status: Optional[ExpenseStatus] = None
    ) -> List[Expense]:
        """
        稼働者×期間の経費リストを取得（仕様17.4で支払明細生成時に使用）
        
        Args:
            worker_id: 稼働者ID
            start_date: 開始日
            end_date: 終了日
            status: ステータスフィルタ
            
        Returns:
            経費リスト
        """
        query = self.session.query(Expense).filter(
            and_(
                Expense.worker_id == worker_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
        )
        
        if status:
            query = query.filter(Expense.status == status)
        
        return query.order_by(Expense.expense_date).all()
