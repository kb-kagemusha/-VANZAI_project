"""Admin-only reviewed person-day pricing; callers never supply the computed total."""
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.order_billing_routes import admin, call
from src.services import order_billing_daily as service

Money=Annotated[Decimal,Field(ge=0,max_digits=15,decimal_places=2,allow_inf_nan=False)]
SignedMoney=Annotated[Decimal,Field(max_digits=15,decimal_places=2,allow_inf_nan=False)]


class RateBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    project_id:str=Field(min_length=1,max_length=26)
    base_rate:Money
    weekday_rates:dict[str,Money]=Field(default_factory=dict)
    revision:int=Field(ge=0)
    reason:str=Field(default="",max_length=2000)


class AdjustmentBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    amount:SignedMoney
    reason:str=Field(default="",max_length=2000)


class ConfirmBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    billing_month:str=Field(pattern=r"^[1-9]\d{3}(0[1-9]|1[0-2])$")
    source_digest:str=Field(min_length=64,max_length=64)
    rates_revision:int=Field(ge=1)
    expected_revision:int=Field(ge=0)
    adjustments:dict[str,AdjustmentBody]=Field(default_factory=dict)
    confirm_zero_days:bool=False
    reason:str=Field(default="",max_length=2000)
    incentive_amount:Money|None=None


def no_store(response:Response): response.headers["Cache-Control"]="no-store"


router=APIRouter(prefix="/api/order-billing/orders",tags=["Daily order billing"],dependencies=[Depends(admin),Depends(no_store)])


@router.get("/{version_id}/daily")
def state(version_id:str,db:Session=Depends(get_db)):
    return call(db,lambda:service.state(db,version_id))


@router.put("/{version_id}/daily/rates")
def save_rates(version_id:str,body:RateBody,db:Session=Depends(get_db),user=Depends(admin)):
    return call(db,lambda:service.save_setting(db,version_id,body.project_id,body.base_rate,body.weekday_rates,body.revision,body.reason,user))


@router.get("/{version_id}/daily/preview")
def preview(version_id:str,db:Session=Depends(get_db)):
    return call(db,lambda:service.preview(db,version_id))


@router.post("/{version_id}/daily/confirm")
def confirm(version_id:str,body:ConfirmBody,db:Session=Depends(get_db),user=Depends(admin)):
    return call(db,lambda:service.confirm(db,version_id,actor=user,**body.model_dump()))
