"""
Audit log service
仕様参照: DESIGN_SPEC_v0.3 セクション16（監査ログ）

必須ログ:
- 単価ルール変更（前/後、理由）
- 実績取り込み（import_batch、件数、差分サマリ）
- replace_scope 実行（scope、superseded件数）
- Soft Close / Hard Close
- Soft Close解除（理由、回数、再締め期限、二者承認の有無）
- 訂正/再発行（理由、差分）
"""
from datetime import datetime, timezone, date
from typing import Any, Optional, List
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from src.models.base import generate_ulid
from src.models.transaction import AuditLog
from src.models.enums import AuditAction


TARGET_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "actual": ("actual", "actuals"),
    "assignment": ("assignment", "assignments"),
    "closing": ("closing", "closings"),
    "expense": ("expense", "expenses"),
    "import_batch": ("import_batch", "import_batches"),
    "invoice": ("invoice", "invoices"),
    "payout": ("payout", "payouts"),
    "price_outsource": ("price_outsource",),
    "price_sales": ("price_sales",),
    "price_rule": ("price_rule", "price_rules"),
    "project": ("project", "projects"),
    "shift_slot": ("shift_slot", "shift_slots"),
    "user": ("user", "users"),
}


def _resolve_target_type_aliases(target_type: str) -> tuple[str, ...]:
    normalized = target_type.strip().lower()
    return TARGET_TYPE_ALIASES.get(normalized, (normalized,))


@dataclass
class AuditLogSearchFilter:
    """監査ログ検索フィルタ"""
    period_key: Optional[str] = None  # YYYYMM形式
    project_id: Optional[str] = None
    action_type: Optional[AuditAction | str] = None
    action_group: Optional[str] = None
    actor: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = 100
    offset: int = 0


@dataclass
class AuditLogSearchResult:
    """監査ログ検索結果"""
    logs: List[AuditLog]
    total_count: int
    has_more: bool


class AuditService:
    """
    監査ログサービス
    
    AGENTS.md: 監査ログは必須のガード
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def log(
        self,
        action: AuditAction | str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor: str | None = None,
        actor_role: str | None = None,
        before_value: dict | None = None,
        after_value: dict | None = None,
        reason: str | None = None,
        extra_metadata: dict | None = None,
    ) -> AuditLog:
        """
        監査ログを記録する
        
        Args:
            action: アクション種別（AuditAction enum または文字列）
            target_type: 対象エンティティ種別（例: "actual", "import_batch"）
            target_id: 対象エンティティID
            actor: 実行者
            actor_role: 実行者のロール
            before_value: 変更前の値（JSON）
            after_value: 変更後の値（JSON）
            reason: 理由
            extra_metadata: 追加メタデータ（JSON）
        
        Returns:
            作成されたAuditLogインスタンス
        """
        action_str = action.value if isinstance(action, AuditAction) else action
        
        audit_log = AuditLog(
            id=generate_ulid(),
            action=action_str,
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            actor_role=actor_role,
            before_value=before_value,
            after_value=after_value,
            reason=reason,
            extra_metadata=extra_metadata,
            created_at=datetime.now(timezone.utc),
        )
        
        self.session.add(audit_log)
        return audit_log
    
    def log_import_batch_created(
        self,
        batch_id: str,
        file_name: str,
        mode: str,
        scope_type: str | None,
        project_id: str | None,
        period_key: str,
        actor: str | None = None,
    ) -> AuditLog:
        """
        CSV取り込みバッチ作成をログ
        仕様参照: 16章「実績取り込み（import_batch、件数、差分サマリ）」
        """
        return self.log(
            AuditAction.IMPORT_BATCH_CREATED,
            target_type="import_batch",
            target_id=batch_id,
            actor=actor,
            after_value={
                "file_name": file_name,
                "mode": mode,
                "scope_type": scope_type,
                "project_id": project_id,
                "period_key": period_key,
            },
        )
    
    def log_import_batch_completed(
        self,
        batch_id: str,
        count_success: int,
        count_error: int,
        count_skip: int,
        count_superseded: int,
        has_warnings: bool = False,
        actor: str | None = None,
    ) -> AuditLog:
        """
        CSV取り込み完了をログ
        仕様参照: 16章「実績取り込み（import_batch、件数、差分サマリ）」
        """
        return self.log(
            AuditAction.IMPORT_BATCH_COMPLETED,
            target_type="import_batch",
            target_id=batch_id,
            actor=actor,
            after_value={
                "count_success": count_success,
                "count_error": count_error,
                "count_skip": count_skip,
                "count_superseded": count_superseded,
                "has_warnings": has_warnings,
            },
        )
    
    def log_replace_scope_executed(
        self,
        batch_id: str,
        scope_type: str,
        project_id: str | None,
        period_key: str,
        superseded_count: int,
        superseded_ids: list[str] | None = None,
        actor: str | None = None,
    ) -> AuditLog:
        """
        replace_scope実行をログ
        仕様参照: 16章「replace_scope 実行（scope、superseded件数）」
        """
        return self.log(
            AuditAction.REPLACE_SCOPE_EXECUTED,
            target_type="import_batch",
            target_id=batch_id,
            actor=actor,
            after_value={
                "scope_type": scope_type,
                "project_id": project_id,
                "period_key": period_key,
                "superseded_count": superseded_count,
            },
            extra_metadata={
                "superseded_ids": superseded_ids[:100] if superseded_ids else None,  # 最大100件
            },
        )
    
    def log_actual_invalidated(
        self,
        actual_id: str,
        reason: str,
        assignment_id: str | None = None,
        actor: str | None = None,
    ) -> AuditLog:
        """
        実績無効化をログ
        仕様参照: 10.2「取消＋actual invalid化」
        """
        return self.log(
            AuditAction.ACTUAL_INVALIDATED,
            target_type="actual",
            target_id=actual_id,
            actor=actor,
            reason=reason,
            extra_metadata={
                "assignment_id": assignment_id,
            },
        )
    
    def log_assignment_canceled(
        self,
        assignment_id: str,
        reason: str,
        actuals_invalidated: list[str] | None = None,
        actor: str | None = None,
    ) -> AuditLog:
        """
        アサインキャンセルをログ
        仕様参照: 10.2
        """
        return self.log(
            AuditAction.ASSIGNMENT_CANCELED,
            target_type="assignment",
            target_id=assignment_id,
            actor=actor,
            reason=reason,
            extra_metadata={
                "actuals_invalidated": actuals_invalidated,
            },
        )
    
    def search_audit_logs(
        self,
        filter: AuditLogSearchFilter,
    ) -> AuditLogSearchResult:
        """
        監査ログを検索する
        
        Args:
            filter: 検索フィルタ
        
        Returns:
            検索結果（ログリスト、総数、次ページ有無）
        
        仕様参照: 
            - AGENTS.md: 監査ログと権限
            - 推奨タスク: 監査ログの充実（検索API実装）
        
        Examples:
            # 特定期間のCSV取り込みログ
            result = service.search_audit_logs(
                AuditLogSearchFilter(
                    period_key="202601",
                    action_type=AuditAction.IMPORT_BATCH_COMPLETED,
                    limit=50
                )
            )
            
            # 特定ユーザーの締め操作ログ
            result = service.search_audit_logs(
                AuditLogSearchFilter(
                    actor="admin",
                    action_type=AuditAction.CLOSING_HARD_EXECUTED,
                    date_from=date(2026, 1, 1),
                    date_to=date(2026, 1, 31)
                )
            )
        """
        # 条件構築
        conditions = []
        
        if filter.period_key:
            # period_key は extra_metadata や before_value/after_value に含まれる可能性がある
            # JSON検索は重いので、created_at でおおよそフィルタ
            # 2026-01 なら 2026-01-01 ~ 2026-01-31 の範囲
            year = int(filter.period_key[:4])
            month = int(filter.period_key[4:6])
            from datetime import date as dt_date
            try:
                start_date = dt_date(year, month, 1)
                # 翌月の1日（末日を計算しなくてよい）
                if month == 12:
                    end_date = dt_date(year + 1, 1, 1)
                else:
                    end_date = dt_date(year, month + 1, 1)
                conditions.append(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time(), timezone.utc))
                conditions.append(AuditLog.created_at < datetime.combine(end_date, datetime.min.time(), timezone.utc))
            except ValueError:
                pass  # 不正なperiod_keyは無視
        
        if filter.action_type:
            action_str = filter.action_type.value if isinstance(filter.action_type, AuditAction) else filter.action_type
            conditions.append(AuditLog.action == action_str)

        if filter.action_group:
            if filter.action_group == "closing_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.CLOSING_SOFT_CLOSED.value,
                    AuditAction.CLOSING_HARD_CLOSED.value,
                    AuditAction.CLOSING_SOFT_RELEASED.value,
                    AuditAction.CLOSING_HARD_RELEASED.value,
                ]))
            elif filter.action_group == "closing_execute":
                conditions.append(AuditLog.action.in_([
                    AuditAction.CLOSING_SOFT_CLOSED.value,
                    AuditAction.CLOSING_HARD_CLOSED.value,
                ]))
            elif filter.action_group == "closing_release":
                conditions.append(AuditLog.action.in_([
                    AuditAction.CLOSING_SOFT_RELEASED.value,
                    AuditAction.CLOSING_HARD_RELEASED.value,
                ]))
            elif filter.action_group == "invoice_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.INVOICE_CREATED.value,
                    AuditAction.INVOICE_ISSUED.value,
                    AuditAction.INVOICE_CORRECTED.value,
                    AuditAction.INVOICE_REISSUED.value,
                ]))
            elif filter.action_group == "payout_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.PAYOUT_CREATED.value,
                    AuditAction.PAYOUT_APPROVED.value,
                    AuditAction.PAYOUT_PAID.value,
                    AuditAction.PAYOUT_CORRECTED.value,
                ]))
            elif filter.action_group == "import_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.IMPORT_BATCH_CREATED.value,
                    AuditAction.IMPORT_BATCH_COMPLETED.value,
                    AuditAction.REPLACE_SCOPE_EXECUTED.value,
                ]))
            elif filter.action_group == "actual_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.ACTUAL_SUPERSEDED.value,
                    AuditAction.ACTUAL_INVALIDATED.value,
                ]))
            elif filter.action_group == "assignment_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.ASSIGNMENT_CANCELED.value,
                    AuditAction.ASSIGNMENT_STATUS_CHANGED.value,
                ]))
            elif filter.action_group == "price_all":
                conditions.append(AuditLog.action.in_([
                    AuditAction.PRICE_RULE_CHANGED.value,
                    AuditAction.PRICE_RESOLVED.value,
                ]))
        
        if filter.actor:
            conditions.append(AuditLog.actor == filter.actor)

        if filter.project_id:
            conditions.append(or_(
                AuditLog.extra_metadata["project_id"].as_string() == filter.project_id,
                AuditLog.after_value["project_id"].as_string() == filter.project_id,
                AuditLog.before_value["project_id"].as_string() == filter.project_id,
                and_(AuditLog.target_type.in_(["project", "projects"]), AuditLog.target_id == filter.project_id),
            ))
        
        if filter.target_type:
            conditions.append(AuditLog.target_type.in_(_resolve_target_type_aliases(filter.target_type)))
        
        if filter.target_id:
            conditions.append(AuditLog.target_id == filter.target_id)
        
        if filter.date_from:
            conditions.append(AuditLog.created_at >= datetime.combine(filter.date_from, datetime.min.time(), timezone.utc))
        
        if filter.date_to:
            # date_to は含むので翌日未満で検索
            from datetime import timedelta
            end_dt = datetime.combine(filter.date_to + timedelta(days=1), datetime.min.time(), timezone.utc)
            conditions.append(AuditLog.created_at < end_dt)
        
        # クエリ構築
        stmt = select(AuditLog)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # 総数取得
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(AuditLog)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_count = self.session.execute(count_stmt).scalar_one()
        
        # ソート（新しい順）
        stmt = stmt.order_by(AuditLog.created_at.desc())
        
        # ページング
        stmt = stmt.limit(filter.limit).offset(filter.offset)
        
        logs = list(self.session.execute(stmt).scalars().all())
        
        has_more = (filter.offset + len(logs)) < total_count
        
        return AuditLogSearchResult(
            logs=logs,
            total_count=total_count,
            has_more=has_more,
        )


# モジュールレベルのヘルパー関数（他のサービスから簡易に使える）
def log(
    session: Session,
    action: AuditAction | str,
    table_name: str,
    record_id: str,
    user_id: str | None = None,
    extra_metadata: dict | None = None,
) -> AuditLog:
    """
    簡易監査ログ記録関数
    
    Args:
        session: DB セッション
        action: アクション種別
        table_name: 対象テーブル名
        record_id: 対象レコードID
        user_id: 実行ユーザー
        extra_metadata: 追加メタデータ
    
    Returns:
        AuditLog
    """
    service = AuditService(session)
    return service.log(
        action=action,
        target_type=table_name,
        target_id=record_id,
        actor=user_id,
        extra_metadata=extra_metadata,
    )
