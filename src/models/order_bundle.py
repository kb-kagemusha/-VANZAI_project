"""ダブルヘッダー：2件の発注依頼書を「束」でつなぐ（DEC-148）。

2件はそれぞれふつうの依頼書（番号・版・PDF・依頼元・請求）のまま。ここでは束ねる情報だけを持つ。
既存の表・列は変えない。物理削除はしない。
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, generate_ulid


class OrderRequestBundle(Base, TimestampMixin):
    """束。区分（正式／テスト）は2件と同じで、作成後は変えない。"""

    __tablename__ = "order_request_bundles"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # 移動に必要な時間（分）。作成時に設定の初期値を入れ、運営が束ごとに変えられる
    travel_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 移動時間の不足を確認して送るときの理由（確定時に固定）
    gap_ack_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_ack_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    gap_ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('formal', 'test')", name="ck_order_request_bundles_kind"),
        CheckConstraint("travel_minutes >= 0 AND travel_minutes <= 720", name="ck_order_request_bundles_travel"),
    )


class OrderRequestBundleLeg(Base):
    """束の1件目・2件目。1つの依頼書（系列）は1つの束にだけ入る。"""

    __tablename__ = "order_request_bundle_legs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    bundle_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_bundles.id"), nullable=False)
    leg_no: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_documents.id"), nullable=False, unique=True)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("bundle_id", "leg_no", name="uq_order_request_bundle_leg_no"),
        CheckConstraint("leg_no IN (1, 2)", name="ck_order_request_bundle_leg_no"),
    )


class OrderRequestBundleDelivery(Base):
    """送付先1人分の2つの送付行の組。返事はこの組で2件まとめて記録する。"""

    __tablename__ = "order_request_bundle_deliveries"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    bundle_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_bundles.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    first_delivery_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    second_delivery_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("bundle_id", "worker_id", name="uq_order_request_bundle_delivery_worker"),
        CheckConstraint("first_delivery_id <> second_delivery_id", name="ck_order_request_bundle_delivery_pair"),
        ForeignKeyConstraint(["first_delivery_id", "worker_id"], ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
                             name="fk_order_request_bundle_delivery_first"),
        ForeignKeyConstraint(["second_delivery_id", "worker_id"], ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
                             name="fk_order_request_bundle_delivery_second"),
    )


class OrderRequestBundleSetting(Base):
    """ダブルヘッダーの設定（1行だけ）。行が無いときは仮の初期値を使う。"""

    __tablename__ = "order_request_bundle_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_travel_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_order_request_bundle_settings_singleton"),
        CheckConstraint("default_travel_minutes >= 0 AND default_travel_minutes <= 720", name="ck_order_request_bundle_settings_travel"),
    )
