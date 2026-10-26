"""Operator invitation administration and verified LINE application."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.operator_staff_routes import ensure_admin
from src.domain.line_operator_config import operator_entry
from src.domain.line_registration_entry import registration_login_channel_id
from src.models.master import User
from src.models.master import RegistrationRequest
from src.models.operator_registration import OperatorRegistrationDetail
from src.services.line_id_token import verify_id_token, LineIdTokenError
from src.services.line_messaging import build_line_client
from src.services.operator_registration import OperatorRegistrationService
from src.services.order_request_service import OrderRequestError

def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["Operator registration"], dependencies=[Depends(no_store)])


class Submit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite: str = Field(min_length=20, max_length=100)
    id_token: str = Field(min_length=1, max_length=10000)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    staff_id: str | None = Field(default=None, max_length=26)
    profile_revision: int | None = Field(default=None, ge=1)


class Rejection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)


def run(db, action):
    try:
        result = action()
        db.commit()
        return result
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, exc.detail) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "登録・LINE連携の状態が変わりました。最新の状態を確認してください") from None


@router.get("/api/line/operator-registration/entry")
def entry(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return operator_entry()


@router.post("/api/line/operator-registration/submissions")
def submit(body: Submit, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not operator_entry()["enabled"]:
        raise HTTPException(403, "運営スタッフのLINE登録は準備中です")
    service = OperatorRegistrationService(db)
    def action():
        # Reject an invalid invitation before calling the external token verifier.
        service.invitation(body.invite)
        try:
            subject = verify_id_token(body.id_token, registration_login_channel_id())
        except LineIdTokenError as exc:
            raise OrderRequestError(401, exc.message) from None
        if len(subject) > 64:
            raise OrderRequestError(401, "本人確認に失敗しました")
        return service.submit(body.invite, subject, body.name, body.phone, build_line_client())
    return run(db, action)


@router.get("/api/operator-registration/settings")
def settings(user: User = Depends(get_current_active_user)):
    ensure_admin(user)
    return {"enabled": operator_entry()["enabled"]}


@router.post("/api/operator-registration/invitations", status_code=201)
def invite(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    return run(db, lambda: OperatorRegistrationService(db).issue(user))


@router.get("/api/operator-registration/invitations")
def invitations(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    rows = db.query(RegistrationRequest).join(OperatorRegistrationDetail, OperatorRegistrationDetail.request_id == RegistrationRequest.id).filter(
        RegistrationRequest.status == "link_issued", RegistrationRequest.deleted_at.is_(None), OperatorRegistrationDetail.revoked_at.is_(None)).order_by(RegistrationRequest.created_at.desc(), RegistrationRequest.id.desc()).limit(100).all()
    return {"items": [{"request_id": row.id, "expires_at": row.expires_at, "created_at": row.created_at} for row in rows]}


@router.post("/api/operator-registration/{request_id}/revoke")
def revoke(request_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    return run(db, lambda: OperatorRegistrationService(db).revoke(request_id, user))


@router.get("/api/operator-registration/{request_id}")
def review(request_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    try:
        return OperatorRegistrationService(db).view(request_id)
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from None


@router.post("/api/operator-registration/{request_id}/approve")
def approve(request_id: str, body: Approval, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    return run(db, lambda: OperatorRegistrationService(db).approve(request_id, user, body.staff_id, body.profile_revision))


@router.post("/api/operator-registration/{request_id}/reject")
def reject(request_id: str, body: Rejection, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ensure_admin(user)
    return run(db, lambda: OperatorRegistrationService(db).reject(request_id, user, body.reason))
