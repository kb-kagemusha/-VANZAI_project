"""締め機能 (DESIGN_SPEC_v0.3 セクション12章)

Soft Close:
- 実績確定後、請求書・支払明細生成前に実施
- 解除は 2 回まで、7 営業日以内に再締め必須

Hard Close:
- 請求書発行・支払承認完了後に実施
- 解除不可（例外対応は監査ログで記録）
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.models.enums import AuditAction, ClosingStatus
from src.models.transaction import Closing
from src.services.audit import log
from src.exceptions import ClosingViolationException, RecordNotFoundException


# 定数
MAX_RELEASE_COUNT = 2  # 解除上限回数
RECLOSE_DEADLINE_DAYS = 7  # 再締め期限（営業日）


def soft_close(
    session: Session,
    project_id: str,
    period_key: str,
    user_id: str,
    notes: Optional[str] = None,
) -> Closing:
    """Soft Close を実施する
    
    Args:
        session: DB セッション
        project_id: プロジェクトID
        period_key: 対象月 (YYYYMM)
        user_id: 実行ユーザー
        notes: 備考
    
    Returns:
        締めレコード
    """
    # 既存の締めレコードを検索
    stmt = select(Closing).where(
        Closing.project_id == project_id,
        Closing.period_key == period_key,
    )
    closing = session.execute(stmt).scalars().first()
    
    if closing:
        # 既に締められている場合
        if closing.status == ClosingStatus.SOFT_CLOSED.value:
            raise ClosingViolationException(
                f"Already soft closed: {project_id} {period_key}",
                details={"project_id": project_id, "period_key": period_key, "status": closing.status}
            )
        if closing.status == ClosingStatus.HARD_CLOSED.value:
            raise ClosingViolationException(
                f"Already hard closed: {project_id} {period_key}",
                details={"project_id": project_id, "period_key": period_key, "status": closing.status}
            )
    else:
        # 新規作成
        closing = Closing(
            project_id=project_id,
            period_key=period_key,
            status=ClosingStatus.OPEN.value,
            release_count=0,
        )
        session.add(closing)
        session.flush()
    
    # Soft Close 実施
    closing.status = ClosingStatus.SOFT_CLOSED.value
    closing.soft_closed_at = datetime.now()
    closing.soft_closed_by = user_id
    if notes:
        closing.notes = notes
    
    log(
        session,
        action=AuditAction.CLOSING_SOFT_CLOSED,
        table_name="closings",
        record_id=closing.id,
        user_id=user_id,
        extra_metadata={
            "project_id": project_id,
            "period_key": period_key,
            "release_count": closing.release_count,
        },
    )
    
    return closing


def hard_close(
    session: Session,
    project_id: str,
    period_key: str,
    user_id: str,
    approver_id: str,
    notes: Optional[str] = None,
) -> Closing:
    """Hard Close を実施する
    
    Args:
        session: DB セッション
        project_id: プロジェクトID
        period_key: 対象月 (YYYYMM)
        user_id: 実行ユーザー
        approver_id: 承認者
        notes: 備考
    
    Returns:
        締めレコード
    """
    # 既存の締めレコードを検索
    stmt = select(Closing).where(
        Closing.project_id == project_id,
        Closing.period_key == period_key,
    )
    closing = session.execute(stmt).scalars().first()
    
    if not closing:
        raise RecordNotFoundException("Closing", f"{project_id}_{period_key}")
    
    if closing.status != ClosingStatus.SOFT_CLOSED.value:
        raise ClosingViolationException(
            f"Already hard closed: {project_id} {period_key}",
            details={"project_id": project_id, "period_key": period_key, "status": closing.status}
        )

    if user_id == approver_id:
        raise ClosingViolationException(
            "User and approver must be different",
            details={"user_id": user_id, "approver_id": approver_id}
        )
    
    # Hard Close 実施
    closing.status = ClosingStatus.HARD_CLOSED.value
    closing.hard_closed_at = datetime.now()
    closing.hard_closed_by = user_id
    if notes:
        closing.notes = notes
    
    log(
        session,
        action=AuditAction.CLOSING_HARD_CLOSED,
        table_name="closings",
        record_id=closing.id,
        user_id=user_id,
        extra_metadata={
            "project_id": project_id,
            "period_key": period_key,
            "release_count": closing.release_count,
            "approver_id": approver_id,
        },
    )
    
    return closing


def release_soft_close(
    session: Session,
    project_id: str,
    period_key: str,
    user_id: str,
    approver_id: str,
    reason: str,
) -> Closing:
    """Soft Close を解除する（ガードレール付き）
    
    Args:
        session: DB セッション
        project_id: プロジェクトID
        period_key: 対象月 (YYYYMM)
        user_id: 実行ユーザー
        approver_id: 承認者（二者承認）
        reason: 解除理由
    
    Returns:
        締めレコード
    
    Raises:
        ValueError: ガードレール違反時
    """
    # 既存の締めレコードを検索
    stmt = select(Closing).where(
        Closing.project_id == project_id,
        Closing.period_key == period_key,
    )
    closing = session.execute(stmt).scalars().first()
    
    if not closing:
        raise RecordNotFoundException("Closing", f"{project_id}_{period_key}")
    
    if closing.status != ClosingStatus.SOFT_CLOSED.value:
        raise ClosingViolationException(
            f"Not soft closed: {project_id} {period_key}",
            details={"project_id": project_id, "period_key": period_key, "status": closing.status}
        )
    
    # ガードレール 1: 解除回数上限
    if closing.release_count >= MAX_RELEASE_COUNT:
        raise ClosingViolationException(
            f"Release count exceeded: {closing.release_count} >= {MAX_RELEASE_COUNT}",
            details={
                "project_id": project_id,
                "period_key": period_key,
                "current_count": closing.release_count,
                "max_count": MAX_RELEASE_COUNT
            }
        )
    
    # ガードレール 2: 二者承認
    if user_id == approver_id:
        raise ClosingViolationException(
            "User and approver must be different",
            details={"user_id": user_id, "approver_id": approver_id}
        )
    
    # ガードレール 3: 再締め期限チェック（前回解除からの経過日数）
    if closing.last_released_at and closing.reclose_deadline:
        if datetime.now() > closing.reclose_deadline:
            raise ClosingViolationException(
                f"Reclose deadline exceeded: {closing.reclose_deadline}",
                details={
                    "project_id": project_id,
                    "period_key": period_key,
                    "deadline": closing.reclose_deadline.isoformat()
                }
            )
    
    # Soft Close 解除
    closing.status = ClosingStatus.OPEN.value
    closing.release_count += 1
    closing.last_released_at = datetime.now()
    closing.last_released_by = f"{user_id} (approved by {approver_id})"
    closing.last_release_reason = reason
    
    # 再締め期限を設定（営業日カウント簡易版：7日後）
    closing.reclose_deadline = datetime.now() + timedelta(days=RECLOSE_DEADLINE_DAYS)
    
    log(
        session,
        action=AuditAction.CLOSING_SOFT_RELEASED,
        table_name="closings",
        record_id=closing.id,
        user_id=user_id,
        extra_metadata={
            "project_id": project_id,
            "period_key": period_key,
            "release_count": closing.release_count,
            "approver_id": approver_id,
            "reason": reason,
            "reclose_deadline": closing.reclose_deadline.isoformat(),
        },
    )
    
    return closing


def release_hard_close(
    session: Session,
    project_id: str,
    period_key: str,
    user_id: str,
    approver_id: str,
    reason: str,
) -> Closing:
    """Hard Close を解除する（例外対応、監査ログ記録）
    
    Args:
        session: DB セッション
        project_id: プロジェクトID
        period_key: 対象月 (YYYYMM)
        user_id: 実行ユーザー
        approver_id: 承認者（二者承認）
        reason: 解除理由
    
    Returns:
        締めレコード
    
    Raises:
        ValueError: 二者承認なし
    """
    # 既存の締めレコードを検索
    stmt = select(Closing).where(
        Closing.project_id == project_id,
        Closing.period_key == period_key,
    )
    closing = session.execute(stmt).scalars().first()
    
    if not closing:
        raise RecordNotFoundException("Closing", f"{project_id}_{period_key}")
    
    if closing.status != ClosingStatus.HARD_CLOSED.value:
        raise ClosingViolationException(
            f"Not hard closed: {project_id} {period_key}",
            details={"project_id": project_id, "period_key": period_key, "status": closing.status}
        )
    
    # ガードレール: 二者承認
    if user_id == approver_id:
        raise ClosingViolationException(
            "User and approver must be different",
            details={"user_id": user_id, "approver_id": approver_id}
        )
    
    # Hard Close 解除（例外対応）
    closing.status = ClosingStatus.SOFT_CLOSED.value
    closing.release_count += 1
    closing.last_released_at = datetime.now()
    closing.last_released_by = f"{user_id} (approved by {approver_id})"
    closing.last_release_reason = f"HARD_CLOSE_RELEASE: {reason}"
    
    # 再締め期限を設定
    closing.reclose_deadline = datetime.now() + timedelta(days=3)  # Hard Close 解除は 3 日以内
    
    log(
        session,
        action=AuditAction.CLOSING_HARD_RELEASED,
        table_name="closings",
        record_id=closing.id,
        user_id=user_id,
        extra_metadata={
            "project_id": project_id,
            "period_key": period_key,
            "release_count": closing.release_count,
            "approver_id": approver_id,
            "reason": reason,
            "reclose_deadline": closing.reclose_deadline.isoformat(),
            "warning": "HARD_CLOSE_RELEASE_EXCEPTION",
        },
    )
    
    return closing


def get_closing_status(
    session: Session,
    project_id: str,
    period_key: str,
) -> Closing:
    """締め状態を取得する
    
    Args:
        session: DB セッション
        project_id: プロジェクトID
        period_key: 対象月 (YYYYMM)
    
    Returns:
        締めレコード（存在しない場合はOPEN状態を返す）
    """
    stmt = select(Closing).where(
        Closing.project_id == project_id,
        Closing.period_key == period_key,
    )
    closing = session.execute(stmt).scalars().first()
    
    if closing is None:
        # レコードが存在しない場合、デフォルトの OPEN 状態を返す
        closing = Closing(
            project_id=project_id,
            period_key=period_key,
            status=ClosingStatus.OPEN,
            release_count=0,
        )
    
    return closing
