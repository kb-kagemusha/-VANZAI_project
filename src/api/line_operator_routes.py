"""LINE-only bearer purpose; never accepts an admin/worker JWT as operator identity."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.services.line_operator import LineOperatorService, OperatorError
from src.services import worker_schedule as ws
from src.services.audit import AuditService


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/line/operator", tags=["LINE operator"], dependencies=[Depends(no_store)])


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=1, max_length=10000)


def read_log(db, staff, user, view, allowed=True):
    AuditService(db).log("operator_portal_read" if allowed else "operator_portal_read_denied", target_type="vanzai_staff", target_id=staff.id, actor=user.id, actor_role=user.role, after_value={"view": view})
    db.commit()


def access(request: Request, db: Session = Depends(get_db)):
    value = request.headers.get("authorization", "")
    try:
        staff, user = LineOperatorService(db).authenticate(value[7:] if value.startswith("Bearer ") else "")
        return db, staff, user
    except OperatorError as exc:
        raise HTTPException(exc.status, exc.message) from None


@router.post("/session")
def session(body: SessionBody, db: Session = Depends(get_db)):
    try:
        result = LineOperatorService(db).issue(body.id_token)
        db.commit()
        return result
    except OperatorError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.message) from None


@router.get("/me")
def me(context=Depends(access)):
    db, staff, user = context
    result = LineOperatorService(db).me(staff, user)
    read_log(db, staff, user, "profile")
    return result


@router.get("/wake-status")
def wake(day: date | None = Query(None, alias="date"), context=Depends(access)):
    db, staff, user = context
    try:
        result = LineOperatorService(db).wake(user, day or ws.today_jst())
    except OperatorError as exc:
        read_log(db, staff, user, "wake", False)
        raise HTTPException(exc.status, exc.message) from None
    read_log(db, staff, user, "wake")
    return result


@router.get("/calendar")
def calendar(start: date, end: date, kind: str = Query("orders", pattern="^(orders|availability)$"), context=Depends(access)):
    db, staff, user = context
    try:
        result = LineOperatorService(db).calendar(user, start, end, kind)
    except OperatorError as exc:
        read_log(db, staff, user, "calendar:" + kind, False)
        raise HTTPException(exc.status, exc.message) from None
    read_log(db, staff, user, "calendar:" + kind)
    return result
