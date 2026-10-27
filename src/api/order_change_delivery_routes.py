"""変更版の送付漏れの確認と、既存LINE送付処理への導線。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.master import User
from src.models.enums import Permission
from src.services.auth import has_permission
from src.services.order_change_delivery import pending_changes
from src.services.order_request_service import OrderRequestService, OrderRequestError
from src.services.line_order import LineOrderService
from src.services.line_messaging import line_settings
from src.services import worker_schedule as ws

router = APIRouter()


@router.get("/change-delivery-pending")
def list_pending(kind: str = Query("formal", pattern="^(formal|test|all)$"), limit: int = Query(10, ge=1, le=50),
                 offset: int = Query(0, ge=0), user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not has_permission(user, Permission.ORDER_READ):
        raise HTTPException(403, "発注依頼書へのアクセス権限がありません")
    groups = pending_changes(db, kind=kind)
    return {"items": groups[offset:offset+limit], "total": len(groups), "limit": limit, "offset": offset,
        "pending_people": sum(len(g["recipients"]) for g in groups),
        "line_send_available": line_settings().configured}


@router.post("/change-delivery-pending/{delivery_id}/send")
def send_pending(delivery_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not has_permission(user, Permission.ORDER_WRITE):
        raise HTTPException(403, "依頼書を変更・送付する権限がありません")
    try:
        service = OrderRequestService(db)
        delivery = service.get_delivery(delivery_id)
        version = service.get_version(delivery.version_id)
        ws.lock_series(db, ws.ensure_series(db, version))
        matches = [r for g in pending_changes(db, kind="all") for r in g["recipients"] if r["delivery_id"] == delivery_id]
        if not matches or not matches[0]["can_send"]:
            raise OrderRequestError(409, "送付待ちの状態が変わっています。更新して確認してください。結果不明・送信中の自動再送はしません")
        LineOrderService(db).send_one(actor=user, delivery=delivery)
        db.commit()
        return {"delivery_id": delivery.id, "send_status": delivery.send_status}
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, exc.detail) from exc
