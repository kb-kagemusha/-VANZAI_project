"""会社情報（0.49.8、DEC-082）。全体管理者だけが閲覧・変更できる。

保存先は請求書の発行元設定と同じ行（order_billing_issuer）。変更は監査ログに残る。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.order_billing_routes import IssuerBody, call
from src.models.master import User
from src.services.order_billing import OrderBillingService
from src.services.order_request_service import OrderRequestError


def admin(user: User = Depends(get_current_active_user)):
    if user.role != "admin":
        raise HTTPException(403, "会社情報は全体管理者だけが閲覧・変更できます")
    return user


router = APIRouter(prefix="/api/company-profile", tags=["Company profile"], dependencies=[Depends(admin)])


@router.get("")
def get_company_profile(db: Session = Depends(get_db)):
    try:
        return OrderBillingService(db).issuer_snapshot()
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


@router.put("")
def update_company_profile(body: IssuerBody, user: User = Depends(admin), db: Session = Depends(get_db)):
    service = OrderBillingService(db)
    call(db, lambda: service.update_issuer(actor=user, **body.model_dump()))
    return service.issuer_snapshot()
