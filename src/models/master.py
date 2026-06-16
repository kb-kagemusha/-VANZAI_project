"""
Master data models
仕様参照: DESIGN_SPEC_v0.3 セクション6.1（マスタ）, 7.1, 7.2（単価）
"""
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text, Boolean, ForeignKey, Numeric, Integer, Date, JSON, DateTime as SADateTime, CheckConstraint, Index
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
    vanzai_staff_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("vanzai_staff.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "worker_id IS NULL OR vanzai_staff_id IS NULL",
            name="ck_users_worker_or_vanzai_staff",
        ),
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
    furigana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sole_proprietor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_name_kana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_registration_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
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


class WorkerBankAccount(Base, TimestampMixin, SoftDeleteMixin):
    """稼働者の振込先口座履歴"""
    __tablename__ = "worker_bank_accounts"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    worker_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=False
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_name: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_holder_kana: Mapped[str] = mapped_column(String(200), nullable=False)
    transfer_destination_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    worker: Mapped["Worker"] = relationship()

    __table_args__ = (
        Index("ix_worker_bank_accounts_worker_id", "worker_id"),
        Index("ix_worker_bank_accounts_worker_primary", "worker_id", "is_primary"),
    )


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
    supplier_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
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


class SupplierBankAccount(Base, TimestampMixin, SoftDeleteMixin):
    """supplier の振込先口座履歴"""
    __tablename__ = "supplier_bank_accounts"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    supplier_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("suppliers.id"), nullable=False
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_name: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_holder_kana: Mapped[str] = mapped_column(String(200), nullable=False)
    transfer_destination_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supplier: Mapped["Supplier"] = relationship()

    __table_args__ = (
        Index("ix_supplier_bank_accounts_supplier_id", "supplier_id"),
        Index("ix_supplier_bank_accounts_supplier_primary", "supplier_id", "is_primary"),
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
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="client")
    client_staff_members: Mapped[list["ClientStaff"]] = relationship(back_populates="client")


class ClientStaff(Base, TimestampMixin, SoftDeleteMixin):
    """クライアント担当者"""
    __tablename__ = "client_staff"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    client_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("clients.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="client_staff_members")

    __table_args__ = (
        Index("ix_client_staff_client_id", "client_id"),
        Index("ix_client_staff_is_active", "is_active"),
    )


class VanzaiStaff(Base, TimestampMixin, SoftDeleteMixin):
    """VANZAI 側の担当者マスタ"""
    __tablename__ = "vanzai_staff"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    playing_manager_fee_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    playing_manager_fixed_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    linked_worker: Mapped["Worker"] = relationship(foreign_keys=[linked_worker_id])

    __table_args__ = (
        Index("ix_vanzai_staff_is_active", "is_active"),
        Index("ix_vanzai_staff_email", "email"),
        Index("ix_vanzai_staff_linked_worker_id", "linked_worker_id"),
    )


class RegistrationRequest(Base, TimestampMixin, SoftDeleteMixin):
    """登録申請ヘッダ"""
    __tablename__ = "registration_requests"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    public_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_target_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    superseded_by_request_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=True
    )
    submitted_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
    superseded_by_request: Mapped["RegistrationRequest | None"] = relationship(
        remote_side=[id],
        back_populates="superseded_requests",
    )
    superseded_requests: Mapped[list["RegistrationRequest"]] = relationship(
        back_populates="superseded_by_request"
    )
    worker_detail: Mapped["WorkerRegistrationRequestDetail | None"] = relationship(
        back_populates="request",
        uselist=False,
    )
    supplier_individual_detail: Mapped["SupplierIndividualRequestDetail | None"] = relationship(
        back_populates="request",
        uselist=False,
    )
    supplier_corporation_detail: Mapped["SupplierCorporationRequestDetail | None"] = relationship(
        back_populates="request",
        uselist=False,
    )
    introducer_identity_detail: Mapped["IntroducerIdentityRequestDetail | None"] = relationship(
        back_populates="request",
        uselist=False,
        foreign_keys="IntroducerIdentityRequestDetail.request_id",
    )
    files: Mapped[list["RegistrationRequestFile"]] = relationship(back_populates="request")

    __table_args__ = (
        Index("ix_registration_requests_status", "status"),
        Index("ix_registration_requests_request_type", "request_type"),
        Index("ix_registration_requests_source_type", "source_type"),
        Index("ix_registration_requests_expires_at", "expires_at"),
        Index("uq_registration_requests_public_token_hash", "public_token_hash", unique=True),
    )


class WorkerRegistrationRequestDetail(Base, TimestampMixin):
    """稼働者登録申請の生データ"""
    __tablename__ = "worker_registration_request_details"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False, unique=True
    )
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name_furigana: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name_furigana: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sole_proprietor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    route_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    introducer_supplier_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prefecture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact_name_kana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_holder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_registration_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_registration_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["RegistrationRequest"] = relationship(back_populates="worker_detail")


class SupplierIndividualRequestDetail(Base, TimestampMixin):
    """個人下請け登録申請の生データ"""
    __tablename__ = "supplier_individual_request_details"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False, unique=True
    )
    supplier_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_furigana: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prefecture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_holder_kana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_registration_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_registration_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["RegistrationRequest"] = relationship(back_populates="supplier_individual_detail")


class SupplierCorporationRequestDetail(Base, TimestampMixin):
    """法人下請け登録申請の生データ"""
    __tablename__ = "supplier_corporation_request_details"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False, unique=True
    )
    supplier_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_name_furigana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    representative_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    representative_name_furigana: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prefecture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_branch_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_holder_kana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_registration_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    invoice_registration_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["RegistrationRequest"] = relationship(back_populates="supplier_corporation_detail")


class IntroducerIdentityRequestDetail(Base, TimestampMixin):
    """紹介者本人確認申請の生データ"""
    __tablename__ = "introducer_identity_request_details"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False, unique=True
    )
    related_worker_request_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=True
    )
    related_supplier_request_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=True
    )
    subject_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subject_name_furigana: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submission_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["RegistrationRequest"] = relationship(
        back_populates="introducer_identity_detail",
        foreign_keys=[request_id],
    )
    related_worker_request: Mapped["RegistrationRequest | None"] = relationship(
        foreign_keys=[related_worker_request_id]
    )
    related_supplier_request: Mapped["RegistrationRequest | None"] = relationship(
        foreign_keys=[related_supplier_request_id]
    )


class RegistrationRequestFile(Base, TimestampMixin, SoftDeleteMixin):
    """登録申請添付ファイル"""
    __tablename__ = "registration_request_files"

    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=generate_ulid
    )
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_part: Mapped[str] = mapped_column(String(20), default="single", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scan_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(SADateTime(timezone=True), nullable=False)
    delete_after: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True), nullable=True)

    request: Mapped["RegistrationRequest"] = relationship(back_populates="files")

    __table_args__ = (
        Index("ix_registration_request_files_request_id", "request_id"),
        Index("ix_registration_request_files_document_type", "document_type"),
        Index("ix_registration_request_files_delete_after", "delete_after"),
    )


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
    category_level: Mapped[str] = mapped_column(String(20), default="minor", nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("project_types.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="project_type")
    parent: Mapped["ProjectType | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["ProjectType"]] = relationship(back_populates="parent")


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
    # プッシュ通知アクションボタン種別: null | "ok_ng" | "confirm"
    push_action_type: Mapped[str | None] = mapped_column(String(10), nullable=True)

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
