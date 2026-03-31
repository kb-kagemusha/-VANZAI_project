"""単価解決サービス (DESIGN_SPEC_v0.3 セクション7.2)

優先順位:
1. Assignment.locked_price (個別ロック)
2. Project 紐付き単価 (PriceSales/PriceOutsource)
3. PriceRule によるマッチング (条件 + priority)
4. デフォルト単価 (is_default=True)
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.models.enums import AuditAction
from src.models.master import PriceSales, PriceOutsource, PriceRule
from src.models.transaction import Assignment
from src.services.audit import log


def resolve_sales_price(
    session: Session,
    assignment: Assignment,
    target_date: date,
) -> Optional[Decimal]:
    """売上単価を解決する
    
    Args:
        session: DB セッション
        assignment: アサインメント
        target_date: 基準日
    
    Returns:
        解決された売上単価 (Decimal) または None
    """
    # Assignment の shift_slot から project_id を取得
    project_id = assignment.shift_slot.project_id if assignment.shift_slot else None
    
    # 1. locked_price_sales があればそれを返す
    if assignment.locked_price_sales is not None:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="assignments",
            record_id=assignment.id,
            extra_metadata={
                "method": "locked_price_sales",
                "price": float(assignment.locked_price_sales),
                "target_date": str(target_date),
            },
        )
        return assignment.locked_price_sales
    
    # 2. Project 紐付き単価 (PriceSales)
    project_price = _find_project_sales_price(
        session,
        project_id=project_id,
        role_id=assignment.role_id,
        client_id=None,  # Assignmentからclientは直接取得できないので後で拡張
        target_date=target_date,
    )
    if project_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_sales",
            record_id=project_price.id,
            extra_metadata={
                "method": "project_price",
                "price": float(project_price.unit_price),
                "target_date": str(target_date),
            },
        )
        return project_price.unit_price
    
    # 3. PriceRule によるマッチング
    rule_price = _find_rule_sales_price(
        session,
        assignment=assignment,
        target_date=target_date,
    )
    if rule_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_rules",
            record_id=rule_price.id,
            extra_metadata={
                "method": "price_rule",
                "price": float(rule_price.sales_price),
                "target_date": str(target_date),
            },
        )
        return rule_price.sales_price
    
    # 4. デフォルト単価
    default_price = _find_default_sales_price(session, target_date)
    if default_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_sales",
            record_id=default_price.id,
            extra_metadata={
                "method": "default",
                "price": float(default_price.unit_price),
                "target_date": str(target_date),
            },
        )
        return default_price.unit_price
    
    # 解決できなかった場合
    log(
        session,
        action=AuditAction.PRICE_RESOLVED,
        table_name="assignments",
        record_id=assignment.id,
        extra_metadata={
            "method": "not_found",
            "target_date": str(target_date),
        },
    )
    return None


def resolve_outsource_price(
    session: Session,
    assignment: Assignment,
    target_date: date,
) -> Optional[Decimal]:
    """外注単価を解決する
    
    Args:
        session: DB セッション
        assignment: アサインメント
        target_date: 基準日
    
    Returns:
        解決された外注単価 (Decimal) または None
    """
    # Assignment の shift_slot から project_id を取得
    project_id = assignment.shift_slot.project_id if assignment.shift_slot else None
    
    # 1. locked_price_outsource があればそれを返す
    if assignment.locked_price_outsource is not None:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="assignments",
            record_id=assignment.id,
            extra_metadata={
                "method": "locked_price_outsource",
                "price": float(assignment.locked_price_outsource),
                "target_date": str(target_date),
                "price_type": "outsource",
            },
        )
        return assignment.locked_price_outsource
    
    # 2. Project 紐付き外注単価
    project_price = _find_project_outsource_price(
        session,
        project_id=project_id,
        worker_id=assignment.worker_id,
        role_id=assignment.role_id,
        target_date=target_date,
    )
    if project_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_outsource",
            record_id=project_price.id,
            extra_metadata={
                "method": "project_price",
                "price": float(project_price.unit_price),
                "target_date": str(target_date),
                "price_type": "outsource",
            },
        )
        return project_price.unit_price
    
    # 3. PriceRule によるマッチング
    rule_price = _find_rule_outsource_price(
        session,
        assignment=assignment,
        target_date=target_date,
    )
    if rule_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_rules",
            record_id=rule_price.id,
            extra_metadata={
                "method": "price_rule",
                "price": float(rule_price.outsource_price),
                "target_date": str(target_date),
                "price_type": "outsource",
            },
        )
        return rule_price.outsource_price
    
    # 4. デフォルト単価
    default_price = _find_default_outsource_price(session, target_date)
    if default_price:
        log(
            session,
            action=AuditAction.PRICE_RESOLVED,
            table_name="price_outsource",
            record_id=default_price.id,
            extra_metadata={
                "method": "default",
                "price": float(default_price.unit_price),
                "target_date": str(target_date),
                "price_type": "outsource",
            },
        )
        return default_price.unit_price
    
    # 解決できなかった場合
    log(
        session,
        action=AuditAction.PRICE_RESOLVED,
        table_name="assignments",
        record_id=assignment.id,
        extra_metadata={
            "method": "not_found",
            "target_date": str(target_date),
            "price_type": "outsource",
        },
    )
    return None


def _find_project_sales_price(
    session: Session,
    project_id: str,
    role_id: Optional[str],
    client_id: Optional[str],
    target_date: date,
) -> Optional[PriceSales]:
    """プロジェクト紐付き売上単価を検索"""
    stmt = (
        select(PriceSales)
        .where(
            PriceSales.deleted_at.is_(None),
            or_(
                PriceSales.valid_from.is_(None),
                PriceSales.valid_from <= target_date,
            ),
            or_(
                PriceSales.valid_to.is_(None),
                PriceSales.valid_to >= target_date,
            ),
        )
    )
    
    # project_id が指定されている場合は必須条件として追加
    if project_id:
        stmt = stmt.where(PriceSales.project_id == project_id)
    
    # role_id, client_id は追加の絞り込み条件（オプション）
    if role_id:
        stmt = stmt.where(or_(
            PriceSales.role_id == role_id,
            PriceSales.role_id.is_(None)
        ))
    if client_id:
        stmt = stmt.where(or_(
            PriceSales.client_id == client_id,
            PriceSales.client_id.is_(None)
        ))
    
    # 条件が多い方を優先
    stmt = stmt.order_by(
        (PriceSales.role_id.isnot(None)).desc(),
        (PriceSales.client_id.isnot(None)).desc(),
    )
    
    return session.execute(stmt).scalars().first()


def _find_project_outsource_price(
    session: Session,
    project_id: str,
    worker_id: str,
    role_id: Optional[str],
    target_date: date,
) -> Optional[PriceOutsource]:
    """プロジェクト紐付き外注単価を検索"""
    stmt = (
        select(PriceOutsource)
        .where(
            PriceOutsource.deleted_at.is_(None),
            or_(
                PriceOutsource.valid_from.is_(None),
                PriceOutsource.valid_from <= target_date,
            ),
            or_(
                PriceOutsource.valid_to.is_(None),
                PriceOutsource.valid_to >= target_date,
            ),
        )
    )
    
    # project_id が指定されている場合は必須条件として追加
    if project_id:
        stmt = stmt.where(PriceOutsource.project_id == project_id)
    
    # worker_id, role_id は追加の絞り込み条件（オプション）
    if worker_id:
        stmt = stmt.where(or_(
            PriceOutsource.worker_id == worker_id,
            PriceOutsource.worker_id.is_(None)
        ))
    if role_id:
        stmt = stmt.where(or_(
            PriceOutsource.role_id == role_id,
            PriceOutsource.role_id.is_(None)
        ))
    
    # worker_id 指定が最優先、次に role_id
    stmt = stmt.order_by(
        (PriceOutsource.worker_id.isnot(None)).desc(),
        (PriceOutsource.role_id.isnot(None)).desc(),
    )
    
    return session.execute(stmt).scalars().first()

def _find_rule_sales_price(
    session: Session,
    assignment: Assignment,
    target_date: date,
) -> Optional[PriceRule]:
    """ルールベース売上単価を検索 (優先順位順)"""
    stmt = (
        select(PriceRule)
        .where(
            PriceRule.deleted_at.is_(None),
            PriceRule.is_active.is_(True),
            PriceRule.sales_price.isnot(None),
            or_(
                PriceRule.valid_from.is_(None),
                PriceRule.valid_from <= target_date,
            ),
            or_(
                PriceRule.valid_to.is_(None),
                PriceRule.valid_to >= target_date,
            ),
        )
        .order_by(PriceRule.priority.asc())
    )
    
    rules = session.execute(stmt).scalars().all()
    for rule in rules:
        if _match_rule_conditions(rule.conditions, assignment):
            return rule
    return None


def _find_rule_outsource_price(
    session: Session,
    assignment: Assignment,
    target_date: date,
) -> Optional[PriceRule]:
    """ルールベース外注単価を検索 (優先順位順)"""
    stmt = (
        select(PriceRule)
        .where(
            PriceRule.deleted_at.is_(None),
            PriceRule.is_active.is_(True),
            PriceRule.outsource_price.isnot(None),
            or_(
                PriceRule.valid_from.is_(None),
                PriceRule.valid_from <= target_date,
            ),
            or_(
                PriceRule.valid_to.is_(None),
                PriceRule.valid_to >= target_date,
            ),
        )
        .order_by(PriceRule.priority.asc())
    )
    
    rules = session.execute(stmt).scalars().all()
    for rule in rules:
        if _match_rule_conditions(rule.conditions, assignment):
            return rule
    return None


def _find_default_sales_price(
    session: Session,
    target_date: date,
) -> Optional[PriceSales]:
    """デフォルト売上単価を検索"""
    stmt = (
        select(PriceSales)
        .where(
            PriceSales.deleted_at.is_(None),
            PriceSales.is_default.is_(True),
            or_(
                PriceSales.valid_from.is_(None),
                PriceSales.valid_from <= target_date,
            ),
            or_(
                PriceSales.valid_to.is_(None),
                PriceSales.valid_to >= target_date,
            ),
        )
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def _find_default_outsource_price(
    session: Session,
    target_date: date,
) -> Optional[PriceOutsource]:
    """デフォルト外注単価を検索"""
    stmt = (
        select(PriceOutsource)
        .where(
            PriceOutsource.deleted_at.is_(None),
            PriceOutsource.is_default.is_(True),
            or_(
                PriceOutsource.valid_from.is_(None),
                PriceOutsource.valid_from <= target_date,
            ),
            or_(
                PriceOutsource.valid_to.is_(None),
                PriceOutsource.valid_to >= target_date,
            ),
        )
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def _match_rule_conditions(conditions: dict, assignment: Assignment) -> bool:
    """PriceRule の条件にマッチするかチェック
    
    Args:
        conditions: ルール条件 (例: {"role_id": "xxx", "project_type": "yyy"})
        assignment: チェック対象のアサインメント
    
    Returns:
        すべての条件にマッチすれば True
    """
    project_id = assignment.shift_slot.project_id if assignment.shift_slot else None
    
    for key, value in conditions.items():
        if key == "role_id" and assignment.role_id != value:
            return False
        if key == "project_id" and project_id != value:
            return False
        if key == "worker_id" and assignment.worker_id != value:
            return False
        # 他の条件は必要に応じて追加
    return True
