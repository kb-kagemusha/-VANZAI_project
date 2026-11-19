"""ダブルヘッダー（同じ日の2件を1件の依頼としてまとめて送る）の API。DEC-148。

2件の保存・確定は同じ取引で行い、片方だけ保存・確定されることはない。
1件ずつの依頼書の API（/api/order-requests）は、束に入った依頼書の下書き保存・確定・変更・個別送信を止める。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.order_request_routes import (
    OrderRequestUpdate,
    OrderRequestWrite,
    _call,
    _ensure,
    _ensure_write,
    _service,
    _version_out,
    apply_version_update,
)
from src.models.master import User
from src.models.order_bundle import OrderRequestBundleDelivery
from src.models.order_request import OrderRequestDocument
from src.services import order_bundle as bundles
from src.services.line_order import LineOrderService
from src.services.order_request_service import OrderRequestError

router = APIRouter(prefix="/api/order-request-bundles", tags=["Order Request Bundles"])


class BundleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    travel_minutes: int | None = Field(default=None, ge=0, le=720)
    legs: list[OrderRequestWrite] = Field(min_length=2, max_length=2)


class BundleLegUpdate(OrderRequestUpdate):
    version_id: str = Field(min_length=1, max_length=26)


class BundleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    travel_minutes: int | None = Field(default=None, ge=0, le=720)
    legs: list[BundleLegUpdate] = Field(min_length=2, max_length=2)


class BundleConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_reason: str | None = Field(default=None, max_length=500)


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_travel_minutes: int = Field(ge=0, le=720)
    revision: int = Field(ge=0)


def _out(db: Session, bundle) -> dict:
    data = bundles.bundle_out(db, bundle)
    data["versions"] = []
    for leg in data["legs"]:
        document = db.get(OrderRequestDocument, leg["document_id"])
        data["versions"].append(_version_out(db, document, bundles.latest_version(db, document.id)))
    return data


@router.get("/settings")
def get_settings(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure(current_user)
    return bundles.read_settings(db)


@router.put("/settings")
def put_settings(body: SettingsUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure_write(current_user)
    return _call(db, lambda: bundles.update_settings(db, minutes=body.default_travel_minutes, revision=body.revision, actor=current_user))


@router.post("")
def create_bundle(body: BundleCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure_write(current_user)
    legs = []
    for leg in body.legs:
        payload = leg.model_dump()
        if "internal_source" not in leg.model_fields_set:
            payload.pop("internal_source", None)
        legs.append(payload)
    bundle = _call(db, lambda: bundles.create(db, actor=current_user, legs=legs, travel_minutes=body.travel_minutes))
    return _out(db, bundle)


@router.get("/{bundle_id}")
def get_bundle(bundle_id: str, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure(current_user)
    return _out(db, _call(db, lambda: bundles.get(db, bundle_id)))


@router.patch("/{bundle_id}")
def update_bundle(bundle_id: str, body: BundleUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure_write(current_user)
    legs = []
    for leg in body.legs:
        fields = leg.model_dump(exclude_unset=True)
        fields["version_id"] = leg.version_id
        if fields.get("assign_tracker_self") is True:
            fields["tracker_user_id"] = current_user.id
        elif fields.get("assign_tracker_self") is False:
            fields["tracker_user_id"] = None
        fields.pop("assign_tracker_self", None)
        legs.append(fields)
    service = _service(db)
    bundle = _call(db, lambda: bundles.update(
        db, actor=current_user, bundle_id=bundle_id, legs=legs, travel_minutes=body.travel_minutes,
        apply_update=lambda version, fields: apply_version_update(service, version, fields, current_user),
    ))
    return _out(db, bundle)


@router.post("/{bundle_id}/confirm")
def confirm_bundle(bundle_id: str, body: BundleConfirm, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure_write(current_user)
    bundle = _call(db, lambda: bundles.confirm(db, actor=current_user, bundle_id=bundle_id, gap_reason=body.gap_reason))
    return _out(db, bundle)


@router.post("/{bundle_id}/pairs/{pair_id}/line-send")
def send_bundle_pair(bundle_id: str, pair_id: str, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _ensure_write(current_user)

    def action():
        pair = db.get(OrderRequestBundleDelivery, pair_id)
        if pair is None or pair.bundle_id != bundle_id:
            raise OrderRequestError(404, "送付先が見つかりません")
        bundles._gate_kind(bundles.get(db, bundle_id).kind)
        LineOrderService(db).send_bundle_pair(actor=current_user, pair=pair)
        return bundles.get(db, bundle_id)

    return _out(db, _call(db, action))
