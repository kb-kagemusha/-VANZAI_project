from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.enums import Permission
from src.services.auth import has_permission
from src.services import order_staffing as service
from src.services.order_request_service import OrderRequestError

router = APIRouter(prefix="/api/order-staffing", tags=["Operator staffing"])


def run(db, user, action, *, write=False):
    required = Permission.ORDER_WRITE if write else Permission.ORDER_READ
    if not has_permission(user, required):
        raise HTTPException(403, "人員確定を操作する権限がありません")
    try:
        result = action()
        if write: db.commit()
        return result
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, exc.detail) from None


class LimitsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capacities: dict[str,StrictInt]
    revision: int = Field(ge=0)


class DecisionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected: dict[str,list[str]]
    close_dates: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=1000)
    revision: int = Field(ge=0)


@router.get("/{version_id}")
def read_staffing(version_id: str, response: Response, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    response.headers["Cache-Control"] = "no-store"
    return run(db,user,lambda:service.read(db,version_id))


@router.put("/{version_id}/limits")
def save_limits(version_id: str, body: LimitsBody, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return run(db,user,lambda:service.save_limits(db,version_id,body.capacities,body.revision,user),write=True)


@router.post("/{version_id}/decisions")
def decide_staffing(version_id: str, body: DecisionsBody, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    result = run(db,user,lambda:service.decide(db,version_id,body.selected,body.close_dates,body.reason,body.revision,user),write=True)
    service.dispatch_notices(db,version_id,user)
    return result


@router.post("/{version_id}/notices/send")
def send_notices(version_id: str, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    run(db,user,lambda:service.current_version(db,version_id),write=True)
    service.dispatch_notices(db,version_id,user,retry_failed=True)
    return service.read(db,version_id)
