"""
Transaction models
仕様参照: DESIGN_SPEC_v0.3 セクション6.1, 6.2, 6.3, 8.1, 9.4-9.6
"""
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, SoftDeleteMixin, generate_ulid
from src.models.enums import (
    AssignmentStatus,
    ActualStatus,
    ImportMode,
    ImportScopeType,
    ImportBatchStatus,
    RoundingMethod,
    BreakDeductionRule,
    TimeCalcMode,
    NightCalcMode,
    AuditAction,
    InvoiceStatus,
    PayoutStatus,
    ClosingStatus,
)

if TYPE_CHECKING:
    from src.models.master import Worker, Client, Site, ProjectType, Role


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """
    案件
    仕様参照: 6.1, 8.1
    """
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    
    # 関連
    client_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("clients.id"), nullable=False
    )
    site_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("sites.id"), nullable=True
    )
    project_type_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("project_types.id"), nullable=True
    )
    
    # 管理者
    primary_manager_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    secondary_manager_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    
    # 期間
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 時間計算設定（仕様8.1）
    rounding_unit_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    rounding_method: Mapped[str] = mapped_column(
        String(20), default=RoundingMethod.CEIL.value, nullable=False
    )
    break_deduction_rule: Mapped[str] = mapped_column(
        String(20), default=BreakDeductionRule.AUTO.value, nullable=False
    )
    time_calc_mode: Mapped[str] = mapped_column(
        String(30), default=TimeCalcMode.SYSTEM_FIRST.value, nullable=False
    )
    night_window_start: Mapped[time | None] = mapped_column(
        Time, default=time(22, 0), nullable=True
    )
    night_window_end: Mapped[time | None] = mapped_column(
        Time, default=time(5, 0), nullable=True
    )
    night_calc_mode: Mapped[str] = mapped_column(
        String(20), default=NightCalcMode.STORE_MINUTES.value, nullable=False
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="projects")
    site: Mapped["Site"] = relationship(back_populates="projects")
    project_type: Mapped["ProjectType"] = relationship(back_populates="projects")
    shift_slots: Mapped[list["ShiftSlot"]] = relationship(back_populates="project")
    actuals: Mapped[list["Actual"]] = relationship(back_populates="project")

    __table_args__ = (
        Index("ix_projects_client_id", "client_id"),
        Index("ix_projects_is_active", "is_active"),
    )


class ShiftSlot(Base, TimestampMixin, SoftDeleteMixin):
    """
    シフト枠
    仕様参照: 6.1
    """
    __tablename__ = "shift_slots"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=False
    )
    
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    
    # シフトラベル（早番/日勤/夜勤等）
    shift_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 必要人数
    required_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="shift_slots")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="shift_slot")

    __table_args__ = (
        Index("ix_shift_slots_project_date", "project_id", "work_date"),
        Index("ix_shift_slots_work_date", "work_date"),
    )


class Assignment(Base, TimestampMixin, SoftDeleteMixin):
    """
    アサイン（シフト枠への稼働者割当）
    仕様参照: 6.1, 6.2, 10.2
    
    不変条件（6.3）:
    - canceled状態でactual.status=activeを残さない
    """
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    shift_slot_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("shift_slots.id"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.id"), nullable=False
    )
    
    # ステータス（仕様6.2）
    status: Mapped[str] = mapped_column(
        String(20),
        default=AssignmentStatus.TENTATIVE.value,
        nullable=False,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 個別単価上書き（仕様6.2, 7.2）
    locked_price_sales: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    locked_price_outsource: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    shift_slot: Mapped["ShiftSlot"] = relationship(back_populates="assignments")
    worker: Mapped["Worker"] = relationship(back_populates="assignments")
    role: Mapped["Role"] = relationship(back_populates="assignments")
    actuals: Mapped[list["Actual"]] = relationship(back_populates="assignment")

    __table_args__ = (
        # 同一枠に同一人物は1件（仕様より推定）
        UniqueConstraint("shift_slot_id", "worker_id", name="uq_assignment_slot_worker"),
        Index("ix_assignments_worker_id", "worker_id"),
        Index("ix_assignments_status", "status"),
    )


class ImportBatch(Base, TimestampMixin):
    """
    CSV取り込みバッチ
    仕様参照: 6.2, 9.4, 9.5, 9.6
    
    Decision: DEC-001（重複検知キー）
    """
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 提出者情報（仕様9.2）
    submitted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submit_channel: Mapped[str] = mapped_column(
        String(50), default="system_upload", nullable=False
    )
    
    # ファイル情報
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    
    # スコープ情報（仕様9.4, 9.5, DEC-001, DEC-002）
    project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    
    # 取り込みモード（仕様9.4）
    mode: Mapped[str] = mapped_column(
        String(30), default=ImportMode.REPLACE_SCOPE.value, nullable=False
    )
    scope_type: Mapped[str | None] = mapped_column(
        String(30), default=ImportScopeType.PROJECT_MONTH.value, nullable=True
    )
    
    # 結果カウント（仕様6.2）
    status: Mapped[str] = mapped_column(
        String(20), default=ImportBatchStatus.PROCESSING.value, nullable=False
    )
    count_success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    count_error: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    count_skip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    count_superseded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # エラー詳細（仕様6.2）
    errors_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # 警告フラグ（仕様9.6：部分ファイル事故検知）
    has_row_count_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_total_time_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    actuals: Mapped[list["Actual"]] = relationship(back_populates="import_batch")

    __table_args__ = (
        # 同一ファイル（hash）× 案件 × 期間 の二重取込防止（DEC-001）
        UniqueConstraint(
            "file_hash", "project_id", "period_key",
            name="uq_import_batch_hash_project_period"
        ),
        Index("ix_import_batches_project_period", "project_id", "period_key"),
        Index("ix_import_batches_status", "status"),
    )


class Actual(Base, TimestampMixin):
    """
    実績
    仕様参照: 6.1, 6.2, 6.3, 7.3, 8.2, 9.6
    
    不変条件（6.3）:
    - 必ずstatusを持ち、集計対象はstatus=activeのみ
    - assignmentがcanceledのままactual.status=activeを残さない
    """
    __tablename__ = "actuals"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 関連（仕様6.1, DEC-003: assignment_id NULLはアプリ層でエラー扱い）
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.id"), nullable=False
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("assignments.id"), nullable=True
    )
    import_batch_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("import_batches.id"), nullable=False
    )
    
    # 日付・期間キー（仕様9.5, DEC-002）
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    
    # ステータス（仕様6.2, 6.3）
    status: Mapped[str] = mapped_column(
        String(20), default=ActualStatus.ACTIVE.value, nullable=False
    )
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 時間（生データ）
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_minutes_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hours_input: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    # 計算結果（仕様6.2, 8.2 - スナップショット保存）
    calc_minutes_total: Mapped[int] = mapped_column(Integer, nullable=False)
    calc_minutes_break: Mapped[int] = mapped_column(Integer, nullable=False)
    calc_minutes_billable: Mapped[int] = mapped_column(Integer, nullable=False)
    calc_minutes_night: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # 計算ルール記録（仕様6.2 - 再現性担保）
    calc_rounding_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calc_rounding_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    calc_break_rule: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # 適用単価スナップショット（仕様6.2, 7.3 - 必須）
    applied_price_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    applied_price_outsource: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    
    # 外部参照キー（仕様6.2, 9.4 upsert_by_external_key用）
    external_row_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 差分確認フラグ（仕様8.2, 8.3）
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="actuals")
    worker: Mapped["Worker"] = relationship(back_populates="actuals")
    role: Mapped["Role"] = relationship(back_populates="actuals")
    assignment: Mapped["Assignment"] = relationship(back_populates="actuals")
    import_batch: Mapped["ImportBatch"] = relationship(back_populates="actuals")

    __table_args__ = (
        # 集計用インデックス
        Index("ix_actuals_status", "status"),
        Index("ix_actuals_project_date", "project_id", "work_date"),
        Index("ix_actuals_project_period", "project_id", "period_key"),
        Index("ix_actuals_project_date_worker", "project_id", "work_date", "worker_id"),
        Index("ix_actuals_worker_period", "worker_id", "period_key"),
        Index("ix_actuals_import_batch", "import_batch_id"),
        # 外部キーでのupsert用（使用時のみ）
        Index("ix_actuals_external_key", "external_row_key"),
    )


class AuditLog(Base):
    """
    監査ログ
    仕様参照: 6.1, 16章
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # アクション
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # 対象
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    
    # 実行者
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 詳細
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # 日時
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


class Invoice(Base, TimestampMixin, SoftDeleteMixin):
    """
    請求書
    仕様参照: 6.2, 11章
    """
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 請求先
    client_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("clients.id"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    
    # 期間
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    billing_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # ステータス
    status: Mapped[str] = mapped_column(
        String(20), default=InvoiceStatus.PREPARING.value, nullable=False
    )
    
    # 版管理（仕様11.1）
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_invoice_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("invoices.id"), nullable=True
    )
    
    # 金額サマリ
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # PDF保存先
    pdf_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 発行日時
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    from src.models.master import Client
    client: Mapped["Client"] = relationship()
    project: Mapped["Project"] = relationship()
    parent_invoice: Mapped["Invoice"] = relationship(remote_side=[id])
    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice")

    __table_args__ = (
        Index("ix_invoices_client_period", "client_id", "period_key"),
        Index("ix_invoices_project_period", "project_id", "period_key"),
        Index("ix_invoices_status", "status"),
    )


class InvoiceLine(Base, TimestampMixin):
    """
    請求書明細
    仕様参照: 6.2, 11章
    """
    __tablename__ = "invoice_lines"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    invoice_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("invoices.id"), nullable=False
    )
    
    # 明細
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    line_type: Mapped[str] = mapped_column(
        String(20), default="actual", nullable=False
    )  # actual/expense/incentive
    
    # 実績参照
    actual_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("actuals.id"), nullable=True
    )
    
    # 経費参照（仕様17.3）
    expense_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("expenses.id"), nullable=True
    )
    
    # インセンティブ参照（仕様18.4）
    incentive_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("incentives.id"), nullable=True
    )
    
    # スナップショット（仕様6.3）
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)  # hours/days
    
    # 金額
    line_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    
    # 訂正フラグ（仕様11.2）
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
    actual: Mapped["Actual"] = relationship()

    __table_args__ = (
        Index("ix_invoice_lines_invoice", "invoice_id"),
        Index("ix_invoice_lines_actual", "actual_id"),
    )


class Payout(Base, TimestampMixin, SoftDeleteMixin):
    """
    支払明細（稼働者/下請けへの支払）
    仕様参照: 6.2, 11章, DRV_PAYOUT_RULES.md
    
    稼働者向け支払: worker_id を設定、supplier_id は NULL
    下請け向け支払: supplier_id を設定、worker_id は NULL
    """
    __tablename__ = "payouts"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 支払先（worker または supplier のいずれか）
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("suppliers.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    
    # 期間
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # ステータス
    status: Mapped[str] = mapped_column(
        String(20), default=PayoutStatus.PREPARING.value, nullable=False
    )
    
    # 版管理
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_payout_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("payouts.id"), nullable=True
    )
    
    # 金額サマリ
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # 承認・支払日時
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    from src.models.master import Worker, Supplier
    worker: Mapped["Worker"] = relationship(foreign_keys=[worker_id])
    supplier: Mapped["Supplier"] = relationship(foreign_keys=[supplier_id])
    project: Mapped["Project"] = relationship()
    parent_payout: Mapped["Payout"] = relationship(remote_side=[id])
    lines: Mapped[list["PayoutLine"]] = relationship(back_populates="payout")

    __table_args__ = (
        Index("ix_payouts_worker_period", "worker_id", "period_key"),
        Index("ix_payouts_supplier_period", "supplier_id", "period_key"),
        Index("ix_payouts_project_period", "project_id", "period_key"),
        Index("ix_payouts_status", "status"),
    )


class PayoutLine(Base, TimestampMixin):
    """
    支払明細行
    仕様参照: 6.2, 11章
    """
    __tablename__ = "payout_lines"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    payout_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("payouts.id"), nullable=False
    )
    
    # 明細
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 行タイプ (actual/expense/incentive) 仕様参照: 18.4
    line_type: Mapped[str] = mapped_column(
        String(20), default="actual", nullable=False
    )  # actual/expense/incentive
    
    # 実績参照
    actual_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("actuals.id"), nullable=True
    )
    
    # 経費参照 (仕様参照: 17.3)
    expense_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("expenses.id"), nullable=True
    )
    
    # インセンティブ参照 (仕様参照: 18.4)
    incentive_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("incentives.id"), nullable=True
    )
    
    # スナップショット
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # 金額
    line_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # 訂正フラグ
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    payout: Mapped["Payout"] = relationship(back_populates="lines")
    actual: Mapped["Actual"] = relationship()

    __table_args__ = (
        Index("ix_payout_lines_payout", "payout_id"),
        Index("ix_payout_lines_actual", "actual_id"),
    )


class Closing(Base, TimestampMixin):
    """
    締め管理
    仕様参照: 12章
    """
    __tablename__ = "closings"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 対象
    project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)
    
    # ステータス
    status: Mapped[str] = mapped_column(
        String(20), default=ClosingStatus.OPEN.value, nullable=False
    )
    
    # 締め日時
    soft_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    soft_closed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    hard_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hard_closed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 解除履歴（仕様12.2）
    release_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_released_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 再締め期限（仕様12.2）
    reclose_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship()
    
    # Properties
    @property
    def is_soft_closed(self) -> bool:
        """Soft Close状態かどうか"""
        return self.status == ClosingStatus.SOFT_CLOSED
    
    @property
    def is_hard_closed(self) -> bool:
        """Hard Close状態かどうか"""
        return self.status == ClosingStatus.HARD_CLOSED

    __table_args__ = (
        UniqueConstraint("project_id", "period_key", name="uq_closing_project_period"),
        Index("ix_closings_period", "period_key"),
        Index("ix_closings_status", "status"),
    )


class Expense(Base, TimestampMixin):
    """
    経費精算
    仕様参照: 17章
    """
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 関連
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=False
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    
    # 経費情報
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # 交通費/材料費/その他
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_file_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # 承認
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 計上先
    target_invoice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_payout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_invoice_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("invoices.id"), nullable=True
    )
    target_payout_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("payouts.id"), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship()
    worker: Mapped["Worker | None"] = relationship()

    __table_args__ = (
        Index("ix_expenses_project_id", "project_id"),
        Index("ix_expenses_worker_id", "worker_id"),
        Index("ix_expenses_status", "status"),
        Index("ix_expenses_expense_date", "expense_date"),
    )


class Incentive(Base, TimestampMixin):
    """
    インセンティブ支給
    仕様参照: 18章
    """
    __tablename__ = "incentives"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    
    # 関連
    incentive_rule_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("incentive_rules.id"), nullable=True
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("projects.id"), nullable=True
    )
    
    # 期間
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    
    # インセンティブ情報
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 承認
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # 計上先
    target_invoice_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("invoices.id"), nullable=True
    )
    target_payout_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("payouts.id"), nullable=True
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    worker: Mapped["Worker"] = relationship()
    project: Mapped["Project | None"] = relationship()

    __table_args__ = (
        Index("ix_incentives_worker_id", "worker_id"),
        Index("ix_incentives_project_id", "project_id"),
        Index("ix_incentives_period_key", "period_key"),
        Index("ix_incentives_status", "status"),
    )
