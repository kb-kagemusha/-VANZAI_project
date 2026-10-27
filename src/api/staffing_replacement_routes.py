"""Same operations and current role checks for admin JWT and LINE operator sessions."""
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.line_operator_routes import access as line_access, no_store
from src.api.order_staffing_routes import run, LimitsBody, DecisionsBody
from src.services import staffing_replacement as service, order_staffing
from src.services.order_request_service import OrderRequestError


class VacancyBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    entry_id:str=Field(min_length=1,max_length=26)
    guard:str=Field(min_length=64,max_length=64)
    reason:str=Field(min_length=1,max_length=1000)


class RecruitmentBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    worker_ids:list[str]=Field(min_length=1,max_length=80)
    deadline:datetime
    revision:int=Field(ge=0)


class CancelBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reason:str=Field(min_length=1,max_length=1000)
    revision:int=Field(ge=0)


class SendBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    version_id:str=Field(min_length=1,max_length=26)
    revision:int=Field(ge=0)


def admin_access(db:Session=Depends(get_db),user=Depends(get_current_active_user)):
    return db,None,user


def register(router,context_dependency):
    @router.get("/staffing-replacements/entries/{entry_id}")
    def preview(entry_id:str,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.preview(db,entry_id))

    @router.get("/staffing-replacements")
    def vacancies(day:date=Query(alias="date"),context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:{"items":service.list_vacancies(db,day)})

    @router.post("/staffing-replacements")
    def create(body:VacancyBody,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.create(db,body.entry_id,body.guard,body.reason,user),write=True)

    @router.get("/staffing-replacements/{vacancy_id}")
    def detail(vacancy_id:str,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.detail(db,vacancy_id))

    @router.get("/staffing-replacements/{vacancy_id}/candidates")
    def candidates(vacancy_id:str,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:{"items":service.candidates(db,vacancy_id)},write=True)

    @router.get("/staffing-replacements/{vacancy_id}/invitation")
    def invitation(vacancy_id:str,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.invitation_preview(db,vacancy_id))

    @router.post("/staffing-replacements/{vacancy_id}/recruit")
    def recruit(vacancy_id:str,body:RecruitmentBody,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.recruit(db,vacancy_id,body.worker_ids,body.deadline,body.revision,user),write=True)

    @router.post("/staffing-replacements/{vacancy_id}/cancel")
    def cancel(vacancy_id:str,body:CancelBody,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.cancel(db,vacancy_id,body.reason,body.revision,user),write=True)

    @router.post("/staffing-replacements/{vacancy_id}/send")
    def send(vacancy_id:str,body:SendBody,context=Depends(context_dependency)):
        db,_,user=context
        return run(db,user,lambda:service.send(db,vacancy_id,body.version_id,body.revision,user),write=True)


router=APIRouter(prefix="/api",tags=["Replacement staffing"],dependencies=[Depends(no_store)])
line_router=APIRouter(prefix="/api/line/operator",tags=["LINE replacement staffing"],dependencies=[Depends(no_store)])
register(router,admin_access)
register(line_router,line_access)


def line_write(db,user,version_id,action):
    def checked():
        from src.models.order_request import OrderRequestVersion
        from src.models.staffing_replacement import StaffingRecruitment
        version=db.get(OrderRequestVersion,version_id)
        if not version or not db.query(StaffingRecruitment.id).filter_by(series_id=version.series_id).first():
            raise OrderRequestError(403,"LINEでの人員変更は代替募集の画面から行ってください")
        return action()
    return run(db,user,checked,write=True)


@line_router.get("/order-staffing/{version_id}")
def line_staffing(version_id:str,context=Depends(line_access)):
    db,_,user=context
    return run(db,user,lambda:order_staffing.read(db,version_id))


@line_router.put("/order-staffing/{version_id}/limits")
def line_limits(version_id:str,body:LimitsBody,context=Depends(line_access)):
    db,_,user=context
    return line_write(db,user,version_id,lambda:order_staffing.save_limits(db,version_id,body.capacities,body.revision,user))


@line_router.post("/order-staffing/{version_id}/decisions")
def line_decide(version_id:str,body:DecisionsBody,context=Depends(line_access)):
    db,_,user=context
    result=line_write(db,user,version_id,lambda:order_staffing.decide(db,version_id,body.selected,body.close_dates,body.reason,body.revision,user))
    order_staffing.dispatch_notices(db,version_id,user)
    return result


@line_router.post("/order-staffing/{version_id}/notices/send")
def line_notices(version_id:str,context=Depends(line_access)):
    db,_,user=context
    line_write(db,user,version_id,lambda:order_staffing.current_version(db,version_id))
    order_staffing.dispatch_notices(db,version_id,user,retry_failed=True)
    return order_staffing.read(db,version_id)
