"""
Master data models
仕様参照: DESIGN_SPEC_v0.3 セクション6.1（マスタ）, 7.1, 7.2（単価）
"""
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, Numeric, Integer, Date, JSON, DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, SoftDeleteMixin, generate_ulid
from src.models.enums import UserRole, NoticeType, NoticeTargetType

if TYPE_CHECKING:
    from src.models.transaction import Project, Assignment, Actual


class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    ユーザー（システムログイン用）
    仕様参照: 5.1, 5.2
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), default=UserRole.WORKER.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Worker と紐付ける場合（オプション）
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )


class Worker(Base, TimestampMixin, SoftDeleteMixin):
    """
    稼働者マスタ
    仕様参照: 6.1
    """
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # 下請け（紹介者）関連
    introducer_supplier_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("suppliers.id"), nullable=True
    )
    introducer_worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )  # 非推奨（後方互換のため残す）

    # スタッフ資格・保有物
    smoking_area_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_p_shirt: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_best: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stores_training_done: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pioneer_training_done: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    p_shirt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=✗, 1=1枚, 2=2枚
    license_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "hiace_ok"/"at_only"/"none"

    # Relationships
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="worker")
    actuals: Mapped[list["Actual"]] = relationship(back_populates="worker")
    introducer_supplier: Mapped["Supplier"] = relationship(
        foreign_keys=[introducer_supplier_id]
    )


class WorkerAvailabilityPreference(Base, TimestampMixin):
    """稼働者ごとの基本スケジュール設定"""
    __tablename__ = "worker_availability_preferences"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False, unique=True
    )
    weekly_default_statuses: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    holiday_default_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    auto_apply_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    worker: Mapped["Worker"] = relationship()


class Supplier(Base, TimestampMixin, SoftDeleteMixin):
    """
    下請け（紹介者）マスタ
    仕様参照: DRV_PAYOUT_RULES.md
    
    稼働者（workers）と紹介者（suppliers）を分離して管理。
    紹介者への支払い（payout）はsupplier_id ベースで生成する。
    """
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # 支払条件
    payout_terms_days: Mapped[int] = mapped_column(
        Integer, default=70, nullable=False
    )  # 支払サイト（30/60/70日）
    
    # 単価設定（デフォルト）
    default_daily_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # 日額単価（例: 16,000円/日、多田さん派閥は16,500円/日）
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    workers: Mapped[list["Worker"]] = relationship(
        foreign_keys="[Worker.introducer_supplier_id]",
        back_populates="introducer_supplier"
    )


class Client(Base, TimestampMixin, SoftDeleteMixin):
    """
    クライアント（請求先）マスタ
    仕様参照: 6.1
    """
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="client")


class Site(Base, TimestampMixin, SoftDeleteMixin):
    """
    現場（稼働場所）マスタ
    仕様参照: 6.1
    """
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="site")


class ProjectType(Base, TimestampMixin, SoftDeleteMixin):
    """
    案件種別マスタ
    仕様参照: 6.1
    """
    __tablename__ = "project_types"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="project_type")


class Role(Base, TimestampMixin, SoftDeleteMixin):
    """
    役割マスタ（例: リーダー、スタッフ）
    仕様参照: 6.1
    """
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="role")
    actuals: Mapped[list["Actual"]] = relationship(back_populates="role")


class PriceSales(Base, TimestampMixin, SoftDeleteMixin):
    """
    売上単価マスタ
    仕様参照: 7.1, 7.2
    """
    __tablename__ = "price_sales"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 適用条件
    role_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("roles.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True  # FK追加はマイグレーションで
    )
    client_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("clients.id"), nullable=True
    )
    
    # 単価
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_type: Mapped[str] = mapped_column(
        String(20), default="hourly", nullable=False
    )  # hourly/daily/monthly
    
    # 有効期間
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    role: Mapped["Role"] = relationship()
    client: Mapped["Client"] = relationship()


class PriceOutsource(Base, TimestampMixin, SoftDeleteMixin):
    """
    外注単価マスタ
    仕様参照: 7.1, 7.2
    """
    __tablename__ = "price_outsource"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 適用条件
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    role_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("roles.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True  # FK追加はマイグレーションで
    )
    
    # 単価
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_type: Mapped[str] = mapped_column(
        String(20), default="hourly", nullable=False
    )
    
    # 有効期間
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    worker: Mapped["Worker"] = relationship()
    role: Mapped["Role"] = relationship()


class IncentiveRule(Base, TimestampMixin, SoftDeleteMixin):
    """
    インセンティブルール
    仕様参照: 18.2
    """
    __tablename__ = "incentive_rules"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 案件（NULLなら全案件共通）
    project_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True  # FK追加はマイグレーションで
    )
    
    # 条件
    condition_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 皆勤/紹介/売上達成等
    condition_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # 支給額
    incentive_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    
    # 計上先
    is_for_invoice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_for_payout: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # 有効期間
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PriceRule(Base, TimestampMixin, SoftDeleteMixin):
    """
    単価ルール（複合条件での単価決定）
    仕様参照: 7.2
    """
    __tablename__ = "price_rules"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    
    # 条件（JSON）
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # 単価
    sales_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    outsource_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    # 有効期間
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StaffNotice(Base, TimestampMixin, SoftDeleteMixin):
    """
    管理者→スタッフ通知
    - シフト確定通知・案件変更通知・一般通知を管理者が送信
    - target_type=all: 全稼働者
    - target_type=project: 特定案件アサイン済み稼働者
    - target_type=worker: 個別稼働者指定（target_worker_ids JSON）
    - send_email=True のとき個別メール送信
    """
    __tablename__ = "staff_notices"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notice_type: Mapped[str] = mapped_column(
        String(30), default=NoticeType.GENERAL.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(10), default="normal", nullable=False
    )  # normal | urgent
    target_type: Mapped[str] = mapped_column(
        String(20), default=NoticeTargetType.ALL.value, nullable=False
    )
    target_project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    # 個別指定の稼働者ID一覧（target_type=worker 時に使用）
    target_worker_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    send_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    reads: Mapped[list["StaffNoticeRead"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )


class StaffNoticeRead(Base, TimestampMixin):
    """
    スタッフ通知既読記録
    - 稼働者が通知を閲覧した記録
    """
    __tablename__ = "staff_notice_reads"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    notice_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("staff_notices.id"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    # 稼働者の返答（ok / ng / None=未回答）
    response: Mapped[str | None] = mapped_column(String(10), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )

    # Relationships
    notice: Mapped["StaffNotice"] = relationship(back_populates="reads")


class PushSubscription(Base, TimestampMixin):
    """
    Web Push サブスクリプション
    - 稼働者がブラウザで通知許可したときに登録
    - 1稼働者が複数端末を持てるよう worker_id + endpoint で一意
    """
    __tablename__ = "push_subscriptions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
