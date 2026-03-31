"""
インセンティブ管理サービス
仕様参照: DESIGN_SPEC_v0.3.md セクション18（インセンティブ管理）
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..models.enums import Permission, IncentiveStatus, AuditAction
from ..models.master import User, IncentiveRule, Worker
from ..models.transaction import Incentive, Project, Actual
from .audit import AuditService
from .auth import require_permission


@dataclass
class IncentiveCreateInput:
    """インセンティブ作成入力"""
    incentive_rule_id: str
    worker_id: str
    project_id: Optional[str]
    period_key: str  # YYYY-MM
    amount: Decimal
    calculation_json: str  # 計算根拠をJSON文字列で保存


@dataclass
class IncentiveApprovalResult:
    """インセンティブ承認結果"""
    success: bool
    incentive: Optional[Incentive]
    message: str


@dataclass
class RuleMatchResult:
    """ルールマッチング結果"""
    matched: bool
    rule: Optional[IncentiveRule]
    amount: Decimal
    calculation_details: dict


class IncentiveService:
    """
    インセンティブ管理サービス
    仕様参照: 18.2, 18.3, 18.4
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    @require_permission(Permission.INCENTIVE_CALCULATE)
    def create_incentive(
        self,
        user: User,
        input_data: IncentiveCreateInput
    ) -> Incentive:
        """
        インセンティブを作成する（仕様18.3）
        
        Args:
            user: 実行ユーザー
            input_data: インセンティブ作成データ
            
        Returns:
            作成されたインセンティブレコード
        """
        # ルールと稼働者の存在確認
        rule = self.session.get(IncentiveRule, input_data.incentive_rule_id)
        if not rule or not rule.is_active:
            raise RecordNotFoundException(
                message="IncentiveRule not found or inactive",
                details={"incentive_rule_id": input_data.incentive_rule_id}
            )
        
        worker = self.session.get(Worker, input_data.worker_id)
        if not worker:
            raise RecordNotFoundException(
                message="Worker not found",
                details={"worker_id": input_data.worker_id}
            )
        
        if input_data.project_id:
            project = self.session.get(Project, input_data.project_id)
            if not project:
                raise RecordNotFoundException(
                    message="Project not found",
                    details={"project_id": input_data.project_id}
                )
        
        # インセンティブレコード作成
        incentive = Incentive(
            incentive_rule_id=input_data.incentive_rule_id,
            worker_id=input_data.worker_id,
            project_id=input_data.project_id,
            period_key=input_data.period_key,
            amount=input_data.amount,
            status=IncentiveStatus.PENDING,
        )
        
        self.session.add(incentive)
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.IMPORT_BATCH_CREATED,
            target_type="Incentive",
            target_id=incentive.id,
            actor=user.username,
            actor_role=user.role.value,
            extra_metadata={
                "rule_id": input_data.incentive_rule_id,
                "worker_id": input_data.worker_id,
                "period_key": input_data.period_key,
                "amount": str(input_data.amount),
            }
        )
        
        return incentive
    
    @require_permission(Permission.INCENTIVE_APPROVE)
    def approve_incentive(
        self,
        user: User,
        incentive_id: str
    ) -> IncentiveApprovalResult:
        """
        インセンティブを承認する（仕様18.3）
        
        Args:
            user: 承認者
            incentive_id: インセンティブID
            
        Returns:
            承認結果
        """
        incentive = self.session.get(Incentive, incentive_id)
        if not incentive:
            return IncentiveApprovalResult(
                success=False,
                incentive=None,
                message=f"Incentive not found: {incentive_id}"
            )
        
        if incentive.status != IncentiveStatus.PENDING:
            return IncentiveApprovalResult(
                success=False,
                incentive=incentive,
                message=f"Incentive is not pending: {incentive.status}"
            )
        
        # 承認処理
        incentive.status = IncentiveStatus.APPROVED
        incentive.approved_by = user.id
        incentive.approved_at = datetime.now(timezone.utc)
        
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.IMPORT_BATCH_COMPLETED,
            target_type="Incentive",
            target_id=incentive.id,
            actor=user.username,
            actor_role=user.role,
            extra_metadata={
                "amount": str(incentive.amount),
                "period_key": incentive.period_key,
            }
        )
        
        return IncentiveApprovalResult(
            success=True,
            incentive=incentive,
            message="Incentive approved successfully"
        )
    
    @require_permission(Permission.INCENTIVE_APPROVE)
    def reject_incentive(
        self,
        user: User,
        incentive_id: str,
        rejection_reason: str
    ) -> IncentiveApprovalResult:
        """
        インセンティブを却下する（仕様18.3）
        
        Args:
            user: 却下者
            incentive_id: インセンティブID
            rejection_reason: 却下理由
            
        Returns:
            却下結果
        """
        incentive = self.session.get(Incentive, incentive_id)
        if not incentive:
            return IncentiveApprovalResult(
                success=False,
                incentive=None,
                message=f"Incentive not found: {incentive_id}"
            )
        
        if incentive.status != IncentiveStatus.PENDING:
            return IncentiveApprovalResult(
                success=False,
                incentive=incentive,
                message=f"Incentive is not pending: {incentive.status}"
            )
        
        # 却下処理
        incentive.status = IncentiveStatus.REJECTED
        incentive.approved_by = user.id
        incentive.approved_at = datetime.utcnow()
        incentive.rejection_reason = rejection_reason
        
        self.session.flush()
        
        # 監査ログ
        audit_service = AuditService(self.session)
        audit_service.log(
            action=AuditAction.ACTUAL_INVALIDATED,
            target_type="Incentive",
            target_id=incentive.id,
            actor=user.username,
            actor_role=user.role.value,
            reason=rejection_reason,
            extra_metadata={
                "amount": str(incentive.amount),
                "period_key": incentive.period_key,
            }
        )
        
        return IncentiveApprovalResult(
            success=True,
            incentive=incentive,
            message="Incentive rejected successfully"
        )
    
    def match_attendance_incentive(
        self,
        worker_id: str,
        period_key: str,
        project_id: Optional[str] = None
    ) -> RuleMatchResult:
        """
        皆勤インセンティブのルールマッチング（仕様18.2: condition_type='attendance'）
        
        Args:
            worker_id: 稼働者ID
            period_key: 期間キー (YYYY-MM)
            project_id: プロジェクトID（プロジェクト限定ルールの場合）
            
        Returns:
            マッチング結果
        """
        # 該当ルールを検索
        query = self.session.query(IncentiveRule).filter(
            and_(
                IncentiveRule.is_active == True,
                IncentiveRule.condition_type == "attendance",
            )
        )
        
        if project_id:
            # プロジェクト指定時: そのプロジェクト限定ルール、または全プロジェクト対象ルール（project_id=None）
            query = query.filter(
                (IncentiveRule.project_id == project_id) | (IncentiveRule.project_id == None)
            )
        
        rule = query.first()
        
        if not rule:
            return RuleMatchResult(
                matched=False,
                rule=None,
                amount=Decimal("0"),
                calculation_details={"reason": "No matching rule found"}
            )
        
        # 実績データで皆勤判定
        # period_keyフォーマット: "YYYYMM" または "YYYY-MM"
        if "-" in period_key:
            year, month = period_key.split("-")
            date_filter = func.strftime('%Y-%m', Actual.work_date) == period_key
        else:
            # "YYYYMM" 形式の場合
            year = period_key[:4]
            month = period_key[4:6]
            date_filter = func.strftime('%Y%m', Actual.work_date) == period_key
        
        actuals = self.session.query(Actual).filter(
            and_(
                Actual.worker_id == worker_id,
                date_filter,
                Actual.status == "valid",
            )
        )
        
        if project_id:
            actuals = actuals.filter(Actual.project_id == project_id)
        
        actual_count = actuals.count()
        
        # ルールの条件をパース（例: {"required_days": 20}）
        condition = json.loads(rule.condition_json)
        required_days = condition.get("required_days", 0)
        
        if actual_count >= required_days:
            return RuleMatchResult(
                matched=True,
                rule=rule,
                amount=rule.incentive_amount,
                calculation_details={
                    "condition": "attendance",
                    "required_days": required_days,
                    "actual_days": actual_count,
                    "period_key": period_key,
                }
            )
        else:
            return RuleMatchResult(
                matched=False,
                rule=rule,
                amount=Decimal("0"),
                calculation_details={
                    "condition": "attendance",
                    "required_days": required_days,
                    "actual_days": actual_count,
                    "reason": "Not enough attendance days",
                }
            )
    
    def get_incentives_for_project_period(
        self,
        project_id: str,
        period_key: str,
        status: Optional[IncentiveStatus] = None
    ) -> List[Incentive]:
        """
        プロジェクト×期間のインセンティブリストを取得（仕様18.4で請求書生成時に使用）
        
        Args:
            project_id: プロジェクトID
            period_key: 期間キー (YYYY-MM)
            status: ステータスフィルタ
            
        Returns:
            インセンティブリスト
        """
        query = self.session.query(Incentive).filter(
            and_(
                Incentive.project_id == project_id,
                Incentive.period_key == period_key,
            )
        )
        
        if status:
            query = query.filter(Incentive.status == status)
        
        return query.all()
    
    def get_incentives_for_worker_period(
        self,
        worker_id: str,
        period_key: str,
        status: Optional[IncentiveStatus] = None
    ) -> List[Incentive]:
        """
        稼働者×期間のインセンティブリストを取得（仕様18.4で支払明細生成時に使用）
        
        Args:
            worker_id: 稼働者ID
            period_key: 期間キー (YYYY-MM)
            status: ステータスフィルタ
            
        Returns:
            インセンティブリスト
        """
        query = self.session.query(Incentive).filter(
            and_(
                Incentive.worker_id == worker_id,
                Incentive.period_key == period_key,
            )
        )
        
        if status:
            query = query.filter(Incentive.status == status)
        
        return query.all()
